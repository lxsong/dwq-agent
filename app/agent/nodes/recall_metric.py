"""
指标召回节点

负责根据用户问题从指标向量知识库中召回候选指标
它帮助 Agent 把“销售额 转化率 客单价”等业务表达映射到已定义指标
实现路径和字段召回类似：关键词扩展 -> Embedding -> Qdrant 相似度检索 -> MetricInfo 去重
"""

import sys
from pathlib import Path

# 支持直接作为脚本运行 (python app/agent/nodes/recall_metric.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.entities.metric_info import MetricInfo
from app.prompt.prompt_loader import load_prompt


async def recall_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """召回和用户问题语义相关的业务指标"""

    writer = runtime.stream_writer
    step = "召回指标信息"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        query = state["query"]
        keywords = state["keywords"]
        embedding_client = runtime.context["embedding_client"]
        metric_qdrant_repository = runtime.context["metric_qdrant_repository"]

        # 1. 用 LLM 把用户问法扩展成“指标概念”列表，例如“销售总额”可扩展出“GMV”、“成交额”
        prompt = PromptTemplate(
            template=load_prompt("extend_keywords_for_metric_recall"),
            input_variables=["query"],
        )
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"query": query})

        # 2. 第一级去重：合并通用关键词与指标扩展词
        keywords = set(keywords + result)

        # 3. 第二级去重：用指标 id (如 GMV) 做唯一键去重
        metric_info_map: dict[str, MetricInfo] = {}
        for keyword in keywords:
            embedding = await embedding_client.aembed_query(keyword)
            current_metric_infos: list[
                MetricInfo
            ] = await metric_qdrant_repository.search(embedding)
            for metric_info in current_metric_infos:
                if metric_info.id not in metric_info_map:
                    metric_info_map[metric_info.id] = metric_info

        retrieved_metric_infos: list[MetricInfo] = list(metric_info_map.values())
        logger.info(f"检索到指标信息：{list(metric_info_map.keys())}")

        writer({"type": "progress", "step": step, "status": "success"})
        return {"retrieved_metric_infos": retrieved_metric_infos}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise


if __name__ == "__main__":
    import asyncio
    from pprint import pprint

    from app.clients.embedding_client_manager import embedding_client_manager
    from app.clients.qdrant_client_manager import qdrant_client_manager
    from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

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
                "metric_qdrant_repository": MetricQdrantRepository(qdrant_client_manager.client),
                "embedding_client": embedding_client_manager.client,
            },  # type: ignore
            stream_writer=lambda msg: print(f"[stream] {msg}"),
        )

        try:
            # 3. 直接调用 recall_metric 函数
            print("\n=== 2. 执行 recall_metric 节点 ===")
            node_result = await recall_metric(input_state, runtime)
            print("\n节点返回值 (更新增量 keys):", list(node_result.keys()))
            metrics = node_result["retrieved_metric_infos"]
            print(f"召回指标数量: {len(metrics)}")
            print("召回指标 ID 列表:", [m.id for m in metrics])

            # 4. 查看更新后的输出 state 结构
            output_state = {**input_state, **node_result}
            print("\n=== 3. 输出 State (更新后) ===")
            pprint(output_state)
        finally:
            await qdrant_client_manager.close()

    asyncio.run(main())
