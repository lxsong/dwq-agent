"""
SQL 校验节点

负责在真正执行查询前，用数据库解析一次生成的 SQL
校验结果不在这里决定流程走向，而是通过 state["error"] 交给 graph.py 的条件边判断
"""

import sys
from pathlib import Path

# 支持直接作为脚本运行 (python app/agent/nodes/validate_sql.py)
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
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """校验 SQL，并返回 error 字段控制后续条件分支"""

    writer = runtime.stream_writer
    step = "校验SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 读取 generate_sql 写入状态的候选 SQL
        sql = state["sql"]
        dw_mysql_repository: DWMySQLRepository = runtime.context["dw_mysql_repository"]

        # 【内层 try...except：捕获业务层面的 SQL 语法/字段错误】
        try:
            await dw_mysql_repository.validate(sql)
            writer({"type": "progress", "step": step, "status": "success"})
            logger.info("SQL语法正确")
            # 校验通过：将 error 置为 None，后续条件边将路由至 run_sql
            return {"error": None}
        except Exception as e:
            # ⚠️ 关键设计：发现 SQL 语法错误时，绝不能向上 raise 中断图执行！
            # 而是标记当前“校验SQL”节点本身执行成功 (status="success")，
            # 并将数据库原生报错信息写入 state["error"]，交由条件边路由至 correct_sql 节点自愈修复！
            logger.info(f"SQL语法错误：{str(e)}")
            writer({"type": "progress", "step": step, "status": "success"})
            return {"error": str(e)}

    # 【外层 try...except：捕获系统级崩溃（如 state 缺键、Runtime 上下文丢失）】
    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise


if __name__ == "__main__":
    import asyncio
    from pprint import pprint

    from app.clients.mysql_client_manager import dw_mysql_client_manager

    async def run_case(title: str, input_state: DataAgentState):
        """使用独立数据库会话执行单次校验场景并打印输入输出 State"""
        print(f"\n==================== {title} ====================")
        print("--- 1. 输入 State ---")
        pprint(input_state)

        async with dw_mysql_client_manager.session_factory() as session:
            dw_mysql_repository = DWMySQLRepository(session)
            runtime = Runtime[DataAgentContext](
                context={
                    "dw_mysql_repository": dw_mysql_repository,
                },  # type: ignore
                stream_writer=lambda msg: print(f"[stream] {msg}"),
            )

            print("\n--- 2. 执行 validate_sql 节点 ---")
            node_result = await validate_sql(input_state, runtime)
            print("节点返回值 (更新增量 keys):", list(node_result.keys()))
            print("校验结果 error:", node_result["error"])

            output_state = {**input_state, **node_result}
            print("\n--- 3. 输出 State (更新后) ---")
            pprint(output_state)

    async def main():
        # 1. 构造承接 generate_sql 节点输出的基础 state
        base_state: DataAgentState = {
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
            "sql": "SELECT SUM(f.order_amount) AS 销售总额 FROM fact_order f INNER JOIN dim_region d ON f.region_id = d.region_id WHERE d.region_name = '华北';",
            "error": None,
        }

        # 2. 初始化数仓 MySQL 客户端，分别测试校验通过与校验失败两种路径
        dw_mysql_client_manager.init()

        # 场景 1：SQL 语法和字段均正确 -> 返回 error=None
        await run_case("场景 1：SQL 校验通过 (error=None)", {**base_state})

        # 场景 2：模拟字段名错误 -> 返回数据库原生报错信息写入 error
        invalid_state: DataAgentState = {
            **base_state,
            "sql": "SELECT SUM(f.not_exist_amount) AS 销售总额 FROM fact_order f INNER JOIN dim_region d ON f.region_id = d.region_id WHERE d.region_name = '华北';",
        }
        await run_case("场景 2：SQL 字段错误 (error=报错信息)", invalid_state)

    asyncio.run(main())