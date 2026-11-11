"""
字段召回节点

负责根据关键词从字段向量知识库中召回候选字段
它解决的是“用户问题可能对应哪些数据库字段”的问题
本章的主线是：关键词扩展 -> Embedding -> Qdrant 相似度检索 -> ColumnInfo 去重
"""

import sys
from pathlib import Path

# 支持直接作为脚本运行 (python app/agent/nodes/recall_column.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.entities.column_info import ColumnInfo
from app.prompt.prompt_loader import load_prompt


async def recall_column(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """召回和用户问题语义相关的字段元数据"""

    writer = runtime.stream_writer
    step = "召回字段信息"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 1. 从 state 读取业务数据，从 runtime.context 获取外部工具
        keywords = state["keywords"]
        query = state["query"]
        column_qdrant_repository = runtime.context["column_qdrant_repository"]
        embedding_client = runtime.context["embedding_client"]

        # 2. 使用 LCEL 管道调用大模型，将用户问法扩展为“字段语义概念”列表
        prompt = PromptTemplate(
            template=load_prompt("extend_keywords_for_column_recall"),
            input_variables=["query"],
        )
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"query": query})

        # 3. 【第一级去重】合并 Jieba 通用关键词与 LLM 字段扩展词，用 set 去重防止重复检索同一词
        keywords = set(keywords + result)

        # 4. 【第二级去重】以字段业务主键 column_info.id (如 fact_order.order_amount) 为唯一键去重
        # 因为：(1) 多个不同关键词可能命中同一字段；(2) 第 9 章一拆多策略下同一字段的多个 Point 也可能同时被命中！
        column_info_map: dict[str, ColumnInfo] = {}
        for keyword in keywords:
            # 查询词必须先转成向量，才能和第 9 章写入 Qdrant 的字段向量做相似度检索
            embedding = await embedding_client.aembed_query(keyword)
            current_column_infos: list[ColumnInfo] = await column_qdrant_repository.search(embedding)
            for column_info in current_column_infos:
                if column_info.id not in column_info_map:
                    column_info_map[column_info.id] = column_info

        # 5. 将去重后的 ColumnInfo 实体列表写回 state
        retrieved_column_infos: list[ColumnInfo] = list(column_info_map.values())
        logger.info(f"检索到字段信息：{list(column_info_map.keys())}")

        writer({"type": "progress", "step": step, "status": "success"})
        return {"retrieved_column_infos": retrieved_column_infos}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise


if __name__ == "__main__":
    import asyncio
    from pprint import pprint

    from app.clients.embedding_client_manager import embedding_client_manager
    from app.clients.qdrant_client_manager import qdrant_client_manager
    from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository

    async def main():
        # 1. 模拟输入 state (承接 extract_keywords 节点的输出状态)
        input_state: DataAgentState = {
            "query": "帮我统计一下华北地区的销售总额",
            "keywords": ["销售总额", "帮我统计一下华北地区的销售总额", "统计", "华北地区"],
            "retrieved_column_infos": [],
            "retrieved_metric_infos": [],
            "retrieved_value_infos": [],
            "error": None,
        }
        print("=== 1. 输入 State ===")
        pprint(input_state)

        # 2. 初始化外部客户端并组装模拟 runtime
        qdrant_client_manager.init()
        embedding_client_manager.init()

        runtime = Runtime[DataAgentContext](
            context={
                "column_qdrant_repository": ColumnQdrantRepository(qdrant_client_manager.client),
                "embedding_client": embedding_client_manager.client,
            },  # type: ignore
            stream_writer=lambda msg: print(f"[stream] {msg}"),
        )

        try:
            # 3. 直接调用 recall_column 函数
            print("\n=== 2. 执行 recall_column 节点 ===")
            node_result = await recall_column(input_state, runtime)
            print("\n节点返回值 (更新增量 keys):", list(node_result.keys()))
            print(f"召回字段数量: {len(node_result['retrieved_column_infos'])}")
            print("召回字段 ID 列表:", [c.id for c in node_result["retrieved_column_infos"]])

            # 4. 查看更新后的输出 state 结构
            output_state = {**input_state, **node_result}
            print("\n=== 3. 输出 State (更新后) ===")
            pprint(output_state)
        finally:
            await qdrant_client_manager.close()

    asyncio.run(main())

