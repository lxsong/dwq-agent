"""
指标信息过滤节点

负责从合并后的候选指标中筛选出当前问题真正需要的指标
过滤后的指标会进入 SQL 生成上下文，帮助模型遵循正确的业务口径
"""

import sys
from pathlib import Path

# 支持直接作为脚本运行 (python app/agent/nodes/filter_metric.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, MetricInfoState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def filter_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """根据用户问题裁剪候选指标上下文"""

    writer = runtime.stream_writer
    step = "过滤指标信息"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        query = state["query"]
        metric_infos: list[MetricInfoState] = state["metric_infos"]

        # 1. 将候选指标转为 YAML 交给模型，模型只需返回被选中的指标名称列表，如 ["GMV"]
        prompt = PromptTemplate(
            template=load_prompt("filter_metric_info"),
            input_variables=["query", "metric_infos"],
        )
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result: list[str] = await chain.ainvoke(
            {
                "query": query,
                "metric_infos": yaml.dump(
                    metric_infos, allow_unicode=True, sort_keys=False
                ),
            }
        )

        # 2. 用模型返回的指标名称列表过滤原始 MetricInfoState 列表，保留完整口径描述与依赖字段
        filtered_metric_infos = [
            metric_info for metric_info in metric_infos if metric_info["name"] in result
        ]

        logger.info(
            f"过滤后的指标信息：{[filtered_metric_info['name'] for filtered_metric_info in filtered_metric_infos]}"
        )

        writer({"type": "progress", "step": step, "status": "success"})
        return {"metric_infos": filtered_metric_infos}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise


if __name__ == "__main__":
    import asyncio
    from pprint import pprint

    async def main():
        # 1. 模拟输入 state (承接 merge_retrieved_info 节点的输出)
        input_state: DataAgentState = {
            "query": "帮我统计一下华北地区的销售总额",
            "keywords": ["销售总额", "帮我统计一下华北地区的销售总额", "统计", "华北地区"],
            "retrieved_column_infos": [],
            "retrieved_metric_infos": [],
            "retrieved_value_infos": [],
            "table_infos": [],
            "metric_infos": [
                MetricInfoState(
                    name="GMV",
                    description="全称Gross Merchandise Value，表示所有订单的成交金额总和。",
                    relevant_columns=["fact_order.order_amount"],
                    alias=["成交总额", "订单总额"],
                ),
                MetricInfoState(
                    name="AOV",
                    description="全称Average Order Value，表示所有订单的成交金额平均值。",
                    relevant_columns=["fact_order.order_quantity"],
                    alias=["平均单价", "平均订单金额"],
                ),
            ],
            "error": None,
        }
        print("=== 1. 输入 State ===")
        pprint(input_state)

        # 2. 模拟 runtime (filter_metric 仅需 stream_writer，不依赖外部数据库/向量库仓储)
        runtime = Runtime[DataAgentContext](
            stream_writer=lambda msg: print(f"[stream] {msg}")
        )

        # 3. 直接调用 filter_metric 函数
        print("\n=== 2. 执行 filter_metric 节点 ===")
        node_result = await filter_metric(input_state, runtime)
        print("\n节点返回值 (更新增量 keys):", list(node_result.keys()))
        print("过滤后保留的指标:", [m["name"] for m in node_result["metric_infos"]])

        # 4. 查看更新后的输出 state 结构
        output_state = {**input_state, **node_result}
        print("\n=== 3. 输出 State (更新后) ===")
        pprint(output_state)

    asyncio.run(main())
