"""
额外上下文补全节点

负责在 SQL 生成前补齐不来自召回结果、但模型必须知道的运行环境信息
当前包括日期信息和数据库方言/版本，后续可继续扩展权限、租户、时区等上下文
"""

import sys
from datetime import date
from pathlib import Path

# 支持直接作为脚本运行 (python app/agent/nodes/add_extra_context.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import (
    ColumnInfoState,
    DataAgentState,
    DateInfoState,
    DBInfoState,
    MetricInfoState,
    TableInfoState,
)
from app.core.log import logger


async def add_extra_context(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """补齐 SQL 生成所需的日期和数据库环境信息"""

    writer = runtime.stream_writer
    step = "添加额外上下文"
    writer({"type": "progress", "step": step, "status": "running"})
    try:
        dw_mysql_repository = runtime.context["dw_mysql_repository"]

        # 1. 计算当前日期信息，帮助模型处理“今天、本月、本季度、最近N天”等相对时间表达
        today = date.today()
        date_str = today.strftime("%Y-%m-%d")
        weekday = today.strftime("%A")
        # 季度计算公式：(月份 - 1) // 3 + 1，确保 1~3月为 Q1，4~6月为 Q2，7~9月为 Q3，10~12月为 Q4
        quarter = f"Q{(today.month - 1) // 3 + 1}"
        date_info = DateInfoState(date=date_str, weekday=weekday, quarter=quarter)

        # 2. 查询数仓方言和版本，影响函数名、日期运算、limit 语法等 SQL 细节
        db = await dw_mysql_repository.get_db_info()
        db_info = DBInfoState(**db)
        logger.info(f"数据库信息：{db_info}")
        logger.info(f"日期信息：{date_info}")

        writer({"type": "progress", "step": step, "status": "success"})
        return {"date_info": date_info, "db_info": db_info}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise


if __name__ == "__main__":
    import asyncio
    from pprint import pprint

    from app.clients.mysql_client_manager import dw_mysql_client_manager
    from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository

    async def main():
        # 1. 模拟输入 state (承接 filter_table 与 filter_metric 节点的输出)
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
            "date_info": DateInfoState(date="", weekday="", quarter=""),
            "db_info": DBInfoState(dialect="", version=""),
            "error": None,
        }
        print("=== 1. 输入 State ===")
        pprint(input_state)

        # 2. 初始化数仓 MySQL 客户端并组装模拟 runtime
        dw_mysql_client_manager.init()
        async with dw_mysql_client_manager.session_factory() as session:
            dw_mysql_repository = DWMySQLRepository(session)
            runtime = Runtime[DataAgentContext](
                context={
                    "dw_mysql_repository": dw_mysql_repository,
                },  # type: ignore
                stream_writer=lambda msg: print(f"[stream] {msg}"),
            )

            # 3. 直接调用 add_extra_context 函数
            print("\n=== 2. 执行 add_extra_context 节点 ===")
            node_result = await add_extra_context(input_state, runtime)
            print("\n节点返回值 (更新增量 keys):", list(node_result.keys()))
            print("date_info:", node_result["date_info"])
            print("db_info:", node_result["db_info"])

            # 4. 查看更新后的输出 state 结构
            output_state = {**input_state, **node_result}
            print("\n=== 3. 输出 State (更新后) ===")
            pprint(output_state)

    asyncio.run(main())
