"""
SQL 执行节点

负责执行最终 SQL，并记录查询结果。
它是当前 SQL 闭环的结束节点，执行完成后流程进入 END。
"""

import sys
from pathlib import Path

# 支持直接作为脚本运行 (python app/agent/nodes/run_sql.py)
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


async def run_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """执行 SQL 并产出最终问数结果"""

    writer = runtime.stream_writer
    step = "执行SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 1. 这里拿到的可能是 generate_sql 直接通过校验的 SQL，也可能是 correct_sql 修复覆盖后的 SQL
        sql = state["sql"]
        dw_mysql_repository = runtime.context["dw_mysql_repository"]

        # 2. 调用数仓仓储执行查询，返回 list[dict] 格式结果
        result = await dw_mysql_repository.run(sql)
        logger.info(f"SQL执行结果：{result}")

        # 3. 先写出当前节点执行成功进度，再写出 type="result" 的最终数据事件供前端渲染表格！
        writer({"type": "progress", "step": step, "status": "success"})
        writer({"type": "result", "data": result})

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
        # 1. 模拟输入 state (承接 validate_sql 校验通过后的输出)
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
            "sql": "SELECT SUM(f.order_amount) AS `销售总额` FROM fact_order f INNER JOIN dim_region d ON f.region_id = d.region_id WHERE d.region_name = '华北';",
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

            # 3. 直接调用 run_sql 函数
            print("\n=== 2. 执行 run_sql 节点 ===")
            node_result = await run_sql(input_state, runtime)
            print("\n节点返回值:", node_result)

            # 4. 查看更新后的输出 state 结构 (run_sql 通过 stream_writer 输出结果，不更新 state 字段)
            output_state = {**input_state, **(node_result or {})}
            print("\n=== 3. 输出 State (更新后) ===")
            pprint(output_state)

    asyncio.run(main())