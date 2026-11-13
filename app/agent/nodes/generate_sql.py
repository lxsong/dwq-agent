"""
SQL 生成节点

负责根据用户问题和前面整理出的表结构 指标 日期 数据库环境生成候选 SQL。
本节点只生成 SQL，不做校验和执行，后续会交给 validate_sql 和 run_sql 继续处理。
"""

import sys
from pathlib import Path

# 支持直接作为脚本运行 (python app/agent/nodes/generate_sql.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import (
    ColumnInfoState,
    DataAgentState,
    DateInfoState,
    DBInfoState,
    MetricInfoState,
    TableInfoState,
)
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def generate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """基于已检索和过滤的上下文生成候选 SQL"""

    writer = runtime.stream_writer
    step = "生成SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 1. 从 state 取出前置节点准备好的五大上下文
        table_infos = state["table_infos"]
        metric_infos = state["metric_infos"]
        date_info = state["date_info"]
        db_info = state["db_info"]
        query = state["query"]

        # 2. 构造 PromptTemplate 并使用 StrOutputParser 提取纯文本字符串
        prompt = PromptTemplate(
            template=load_prompt("generate_sql"),
            input_variables=[
                "table_infos",
                "metric_infos",
                "date_info",
                "db_info",
                "query",
            ],
        )
        # 注意：前面扩词和过滤节点用的是 JsonOutputParser，而生成 SQL 只需要纯文本，所以用 StrOutputParser()
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

        # 3. 将四份结构化字典/列表统一转为可读性极佳的 YAML 字符串后调用大模型
        result = await chain.ainvoke(
            {
                "table_infos": yaml.dump(
                    table_infos, allow_unicode=True, sort_keys=False
                ),
                "metric_infos": yaml.dump(
                    metric_infos, allow_unicode=True, sort_keys=False
                ),
                "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
                "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
                "query": query,
            }
        )
        logger.info(f"生成的SQL：{result}")
        writer({"type": "progress", "step": step, "status": "success"})
        writer({"type": "sql", "sql": result})
        return {"sql": result}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise


if __name__ == "__main__":
    import asyncio
    from pprint import pprint

    async def main():
        # 1. 模拟输入 state (承接 add_extra_context 节点的输出)
        input_state: DataAgentState = {
            "query": "帮我统计一下华北地区的销售总额",
            "keywords": ["销售总额", "帮我统计一下华北地区的销售总额", "统计", "华北地区"],
            "retrieved_column_infos": [],
            "retrieved_metric_infos": [],
            "retrieved_value_infos": [],
            "table_infos": [
                TableInfoState(
                    name="fact_order",
                    role="fact",
                    description="订单事实表，记录订单数量和金额等核心指标。",
                    columns=[
                        ColumnInfoState(
                            name="order_amount",
                            type="float",
                            role="measure",
                            examples=[8999.0, 6999.0],
                            description="订单金额。",
                            alias=["销售额", "订单金额", "收入"],
                        ),
                        ColumnInfoState(
                            name="region_id",
                            type="varchar(20)",
                            role="foreign_key",
                            examples=["R001", "R005"],
                            description="关联地区维度的外键。",
                            alias=["地区ID", "区域ID"],
                        ),
                    ],
                ),
                TableInfoState(
                    name="dim_region",
                    role="dim",
                    description="地区维度表，用于描述订单发生的地理区域信息。",
                    columns=[
                        ColumnInfoState(
                            name="region_name",
                            type="varchar(50)",
                            role="dimension",
                            examples=["华南", "华东", "西南", "华北"],
                            description="订单所属的大区名称，如华东、华南等。",
                            alias=["地区", "区域", "大区"],
                        ),
                        ColumnInfoState(
                            name="region_id",
                            type="varchar(20)",
                            role="primary_key",
                            examples=["R001", "R002"],
                            description="地区唯一标识。",
                            alias=["地区ID", "区域ID"],
                        ),
                    ],
                ),
            ],
            "metric_infos": [
                MetricInfoState(
                    name="GMV",
                    description="全称Gross Merchandise Value，表示所有订单的成交金额总和。",
                    relevant_columns=["fact_order.order_amount"],
                    alias=["成交总额", "订单总额"],
                ),
            ],
            "date_info": DateInfoState(
                date="2026-11-12", weekday="Thursday", quarter="Q4"
            ),
            "db_info": DBInfoState(dialect="mysql", version="8.0.46"),
            "sql": "",
            "error": None,
        }
        print("=== 1. 输入 State ===")
        pprint(input_state)

        # 2. 模拟 runtime (generate_sql 仅需 stream_writer，大模型实例由模块内直接导入)
        runtime = Runtime[DataAgentContext](
            stream_writer=lambda msg: print(f"[stream] {msg}")
        )

        # 3. 直接调用 generate_sql 函数
        print("\n=== 2. 执行 generate_sql 节点 ===")
        node_result = await generate_sql(input_state, runtime)
        print("\n节点返回值 (更新增量 keys):", list(node_result.keys()))
        print("生成的 SQL:\n" + node_result["sql"])

        # 4. 查看更新后的输出 state 结构
        output_state = {**input_state, **node_result}
        print("\n=== 3. 输出 State (更新后) ===")
        pprint(output_state)

    asyncio.run(main())