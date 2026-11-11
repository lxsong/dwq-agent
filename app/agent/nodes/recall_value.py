"""
字段取值召回节点

负责从字段值全文索引中召回候选取值
当用户问题里出现店铺名 类目名 地区名等业务值时，这一步可以帮助定位真实字段和值
实现路径和字段/指标召回不同：关键词扩展 -> Elasticsearch 全文检索 -> ValueInfo 去重
"""

import sys
from pathlib import Path

# 支持直接作为脚本运行 (python app/agent/nodes/recall_value.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.entities.value_info import ValueInfo
from app.prompt.prompt_loader import load_prompt


async def recall_value(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """召回和用户问题相关的字段真实取值"""

    writer = runtime.stream_writer
    step = "召回字段取值"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        query = state["query"]
        keywords = state["keywords"]
        # 字段取值关注字面文本与分词命中，直接取 Elasticsearch 仓储，无需 embedding_client
        value_es_repository = runtime.context["value_es_repository"]

        # 1. 用 LLM 把用户问法扩展成“可能出现在字段值里的词”
        # 例如“华北地区”可补充出“华北”，避免 SQL WHERE 条件值和数据库真实存储值不一致
        prompt = PromptTemplate(
            template=load_prompt("extend_keywords_for_value_recall"),
            input_variables=["query"],
        )
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"query": query})

        # 2. 第一级去重：合并通用关键词与取值扩展词
        keywords = set(keywords + result)

        # 3. 第二级去重：用 ValueInfo.id (如 dim_region.region_name.华北) 做唯一键去重
        value_infos_map: dict[str, ValueInfo] = {}
        for keyword in keywords:
            current_value_infos: list[ValueInfo] = await value_es_repository.search(
                keyword
            )
            for current_value_info in current_value_infos:
                if current_value_info.id not in value_infos_map:
                    value_infos_map[current_value_info.id] = current_value_info

        retrieved_value_infos: list[ValueInfo] = list(value_infos_map.values())
        logger.info(f"检索到字段取值：{list(value_infos_map.keys())}")

        writer({"type": "progress", "step": step, "status": "success"})
        return {"retrieved_value_infos": retrieved_value_infos}
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise


if __name__ == "__main__":
    import asyncio
    from pprint import pprint

    from app.clients.es_client_manager import es_client_manager
    from app.repositories.es.value_es_repository import ValueESRepository

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
        es_client_manager.init()

        runtime = Runtime[DataAgentContext](
            context={
                "value_es_repository": ValueESRepository(es_client_manager.client),
            },  # type: ignore
            stream_writer=lambda msg: print(f"[stream] {msg}"),
        )

        try:
            # 3. 直接调用 recall_value 函数
            print("\n=== 2. 执行 recall_value 节点 ===")
            node_result = await recall_value(input_state, runtime)
            print("\n节点返回值 (更新增量 keys):", list(node_result.keys()))
            values = node_result["retrieved_value_infos"]
            print(f"召回字段取值数量: {len(values)}")
            print("召回字段取值 ID 列表:", [v.id for v in values])

            # 4. 查看更新后的输出 state 结构
            output_state = {**input_state, **node_result}
            print("\n=== 3. 输出 State (更新后) ===")
            pprint(output_state)
        finally:
            await es_client_manager.close()

    asyncio.run(main())
