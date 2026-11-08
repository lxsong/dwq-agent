"""
电商问数 Agent 图编排

使用 LangGraph 把问数智能体的各个节点串成一条可观测的执行链路
整体流程先抽取用户问题关键词，再并行召回字段 字段取值和指标信息，
随后合并召回结果 过滤候选表和指标 补充额外上下文，最后生成 校验 修正并执行 SQL
"""

import asyncio

from langgraph.constants import END, START
from langgraph.graph import StateGraph

from app.agent.context import DataAgentContext
from app.agent.nodes.add_extra_context import add_extra_context
from app.agent.nodes.correct_sql import correct_sql
from app.agent.nodes.extract_keywords import extract_keywords
from app.agent.nodes.filter_metric import filter_metric
from app.agent.nodes.filter_table import filter_table
from app.agent.nodes.generate_sql import generate_sql
from app.agent.nodes.merge_retrieved_info import merge_retrieved_info
from app.agent.nodes.recall_column import recall_column
from app.agent.nodes.recall_metric import recall_metric
from app.agent.nodes.recall_value import recall_value
from app.agent.nodes.run_sql import run_sql
from app.agent.nodes.validate_sql import validate_sql
from app.agent.state import DataAgentState

# 1. 声明整张图使用的共享状态结构 (DataAgentState) 和运行时上下文结构 (DataAgentContext)
graph_builder = StateGraph(state_schema=DataAgentState, context_schema=DataAgentContext)

# 2. 注册 12 个业务节点：建议节点注册名称与函数名保持严格一致，便于排查日志与对照流程图
graph_builder.add_node("extract_keywords", extract_keywords)
graph_builder.add_node("recall_column", recall_column)
graph_builder.add_node("recall_value", recall_value)
graph_builder.add_node("recall_metric", recall_metric)
graph_builder.add_node("merge_retrieved_info", merge_retrieved_info)
graph_builder.add_node("filter_metric", filter_metric)
graph_builder.add_node("filter_table", filter_table)
graph_builder.add_node("add_extra_context", add_extra_context)
graph_builder.add_node("generate_sql", generate_sql)
graph_builder.add_node("validate_sql", validate_sql)
graph_builder.add_node("correct_sql", correct_sql)
graph_builder.add_node("run_sql", run_sql)

# 3. 连接起点：从 START 进入第一个节点 extract_keywords
graph_builder.add_edge(START, "extract_keywords")

# 4. 第一次并行扇出 (Fan-out)：关键词抽取后，同时启动字段、字段取值、指标三路召回
graph_builder.add_edge("extract_keywords", "recall_column")
graph_builder.add_edge("extract_keywords", "recall_value")
graph_builder.add_edge("extract_keywords", "recall_metric")

# 5. 第一次汇聚 (Fan-in)：等待三路召回全部完成后，统一进入 merge_retrieved_info 合并节点
graph_builder.add_edge("recall_column", "merge_retrieved_info")
graph_builder.add_edge("recall_value", "merge_retrieved_info")
graph_builder.add_edge("recall_metric", "merge_retrieved_info")

# 6. 第二次并行扇出 (Fan-out)：合并后的候选信息同时进入表过滤和指标过滤两条支路
graph_builder.add_edge("merge_retrieved_info", "filter_table")
graph_builder.add_edge("merge_retrieved_info", "filter_metric")

# 7. 第二次汇聚 (Fan-in) 与串行推进：表和指标都过滤完成后，补充额外上下文 -> 生成 SQL -> 校验 SQL
graph_builder.add_edge("filter_table", "add_extra_context")
graph_builder.add_edge("filter_metric", "add_extra_context")
graph_builder.add_edge("add_extra_context", "generate_sql")
graph_builder.add_edge("generate_sql", "validate_sql")

# 8. 条件边路由：validate_sql 校验通过 (error is None) 直接去 run_sql；校验失败则先去 correct_sql 修正
graph_builder.add_conditional_edges(
    source="validate_sql",
    path=lambda state: "run_sql" if state["error"] is None else "correct_sql",
    path_map={"run_sql": "run_sql", "correct_sql": "correct_sql"},
)
graph_builder.add_edge("correct_sql", "run_sql")
graph_builder.add_edge("run_sql", END)

# 9. 编译生成对外可执行的图实例 graph
graph = graph_builder.compile()


if __name__ == "__main__":
    # 技巧1：打印自动生成的 Mermaid 图语法，检查节点连线是否有误
    print("=== 1. 导出 LangGraph Mermaid 拓扑图语法 ===")
    print(graph.get_graph().draw_mermaid())

    async def test():
        """技巧2：测试正常分支 (error=None) 与 异常自愈分支 (error='模拟报错') 的流式输出"""
        context = DataAgentContext()

        print("\n=== 2. 测试路径 A：SQL 校验通过 (validate_sql -> run_sql) ===")
        state_ok = DataAgentState(query="统计华北地区的销售总额", error=None)
        async for chunk in graph.astream(
            input=state_ok, context=context, stream_mode="custom"
        ):
            print("  ->", chunk)

        print("\n=== 3. 测试路径 B：SQL 校验失败触发修正 (validate_sql -> correct_sql -> run_sql) ===")
        state_err = DataAgentState(query="统计华北地区的销售总额", error="Unknown column 'region'")
        async for chunk in graph.astream(
            input=state_err, context=context, stream_mode="custom"
        ):
            print("  ->", chunk)

    asyncio.run(test())