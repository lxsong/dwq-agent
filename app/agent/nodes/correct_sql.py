"""
SQL 修正节点

负责在 SQL 校验失败后，结合原问题 原 SQL 数据库错误和完整上下文做最小必要修正
只有 validate_sql 写入错误信息时，LangGraph 才会进入这个分支
"""

import sys
from pathlib import Path

# 支持直接作为脚本运行 (python app/agent/nodes/correct_sql.py)
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


async def correct_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """根据校验错误修正 SQL"""

    writer = runtime.stream_writer
    step = "校正SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 1. 校正 SQL 仍然需要完整上下文，避免模型只根据报错修语法却改丢业务语义或再次盲猜字段名
        table_infos = state["table_infos"]
        metric_infos = state["metric_infos"]
        date_info = state["date_info"]
        db_info = state["db_info"]
        query = state["query"]

        # 2. sql 是待修正的候选 SQL，error 是数据库 explain 返回的具体错误信息
        sql = state["sql"]
        error = state["error"]

        prompt = PromptTemplate(
            template=load_prompt("correct_sql"),
            input_variables=[
                "table_infos",
                "metric_infos",
                "date_info",
                "db_info",
                "query",
                "sql",
                "error",
            ],
        )
        # 3. 修正后的输出仍然是一条纯 SQL 文本，返回 {"sql": result} 覆盖 state["sql"]
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

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
                "sql": sql,
                "error": error,
            }
        )

        logger.info(f"校正后的SQL：{result}")
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
        # 1. 模拟输入 state (承接 validate_sql 校验失败场景的输出)
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
            "sql": "SELECT SUM(f.not_exist_amount) AS 销售总额 FROM fact_order f INNER JOIN dim_region d ON f.region_id = d.region_id WHERE d.region_name = '华北';",
            "error": (
                '(asyncmy.errors.OperationalError) (1054, "Unknown column '
                '\'f.not_exist_amount\' in \'field list\'")\n'
                "[SQL: explain SELECT SUM(f.not_exist_amount) AS 销售总额 FROM "
                "fact_order f INNER JOIN dim_region d ON f.region_id = d.region_id "
                "WHERE d.region_name = '华北';]"
            ),
        }
        print("=== 1. 输入 State ===")
        pprint(input_state)

        # 2. 模拟 runtime (correct_sql 仅需 stream_writer，大模型实例由模块内直接导入)
        runtime = Runtime[DataAgentContext](
            stream_writer=lambda msg: print(f"[stream] {msg}")
        )

        # 3. 直接调用 correct_sql 函数
        print("\n=== 2. 执行 correct_sql 节点 ===")
        node_result = await correct_sql(input_state, runtime)
        print("\n节点返回值 (更新增量 keys):", list(node_result.keys()))
        print("校正后的 SQL:\n" + node_result["sql"])

        # 4. 查看更新后的输出 state 结构
        output_state = {**input_state, **node_result}
        print("\n=== 3. 输出 State (更新后) ===")
        pprint(output_state)

    asyncio.run(main())