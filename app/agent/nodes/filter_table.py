"""
表信息过滤节点

负责在合并后的候选表结构中筛选出当前问题真正需要的表和字段
这里让大模型只返回“保留哪些表和字段”的选择结果，真正的结构裁剪仍由程序完成
"""

import sys
from pathlib import Path

# 支持直接作为脚本运行 (python app/agent/nodes/filter_table.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import ColumnInfoState, DataAgentState, TableInfoState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """根据用户问题裁剪候选表结构上下文"""

    writer = runtime.stream_writer
    step = "过滤表信息"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        query = state["query"]
        table_infos: list[TableInfoState] = state["table_infos"]

        # 1. 加载 filter_table_info 提示词，输入变量为 query 和 YAML 格式的 table_infos
        prompt = PromptTemplate(
            template=load_prompt("filter_table_info"),
            input_variables=["query", "table_infos"],
        )
        # 2. 模型输出为 {"表名": ["字段1", "字段2"]} 格式的 JSON 对象
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result: dict[str, list[str]] = await chain.ainvoke(
            {
                "query": query,
                "table_infos": yaml.dump(
                    table_infos, allow_unicode=True, sort_keys=False
                ),
            }
        )

        # 3. 模型只负责做选择，程序根据选择结果从原始 TableInfoState 中安全裁剪
        # 注意：新建 filtered_table_infos 列表存放保留项，切勿在遍历原列表时直接 remove 元素！
        filtered_table_infos: list[TableInfoState] = []
        for table_info in table_infos:
            if table_info["name"] in result:
                table_info["columns"] = [
                    column_info
                    for column_info in table_info["columns"]
                    if column_info["name"] in result[table_info["name"]]
                ]
                filtered_table_infos.append(table_info)

        logger.info(
            f"过滤后的表信息：{[filtered_table_info['name'] for filtered_table_info in filtered_table_infos]}"
        )
        writer({"type": "progress", "step": step, "status": "success"})
        return {"table_infos": filtered_table_infos}

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
                            name="order_quantity",
                            type="int",
                            role="measure",
                            examples=[1, 5, 12],
                            description="订单中商品的购买数量。",
                            alias=["销量", "购买数量", "件数"],
                        ),
                        ColumnInfoState(
                            name="customer_id",
                            type="varchar(20)",
                            role="foreign_key",
                            examples=["C001", "C005"],
                            description="关联客户维度的外键。",
                            alias=["客户ID", "用户ID"],
                        ),
                        ColumnInfoState(
                            name="date_id",
                            type="int",
                            role="foreign_key",
                            examples=[20250101, 20250102],
                            description="关联时间维度的外键。",
                            alias=["日期", "下单日期"],
                        ),
                        ColumnInfoState(
                            name="order_id",
                            type="varchar(30)",
                            role="primary_key",
                            examples=["ORD20250101001"],
                            description="订单唯一标识。",
                            alias=["订单ID"],
                        ),
                        ColumnInfoState(
                            name="product_id",
                            type="varchar(20)",
                            role="foreign_key",
                            examples=["P001", "P003"],
                            description="关联商品维度的外键。",
                            alias=["商品ID", "产品ID"],
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
                            name="province",
                            type="varchar(50)",
                            role="dimension",
                            examples=["广东省", "北京市"],
                            description="订单所属的省份名称。",
                            alias=["省份", "省"],
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
                TableInfoState(
                    name="dim_product",
                    role="dim",
                    description="商品维度表，记录商品名称、品牌和所属品类。",
                    columns=[
                        ColumnInfoState(
                            name="category",
                            type="varchar(50)",
                            role="dimension",
                            examples=["手机数码", "家用电器"],
                            description="商品所属品类。",
                            alias=["商品类别", "品类"],
                        ),
                        ColumnInfoState(
                            name="product_id",
                            type="varchar(20)",
                            role="primary_key",
                            examples=["P001", "P002"],
                            description="商品唯一标识。",
                            alias=["商品ID", "产品ID"],
                        ),
                    ],
                ),
            ],
            "metric_infos": [],
            "error": None,
        }
        print("=== 1. 输入 State ===")
        pprint(input_state)

        # 2. 模拟 runtime (filter_table 仅需 stream_writer，不依赖外部数据库/向量库仓储)
        runtime = Runtime[DataAgentContext](
            stream_writer=lambda msg: print(f"[stream] {msg}")
        )

        # 3. 直接调用 filter_table 函数
        print("\n=== 2. 执行 filter_table 节点 ===")
        node_result = await filter_table(input_state, runtime)
        print("\n节点返回值 (更新增量 keys):", list(node_result.keys()))
        print("过滤后保留的表及字段:")
        for t in node_result["table_infos"]:
            print(f"  - {t['name']}: {[c['name'] for c in t['columns']]}")

        # 4. 查看更新后的输出 state 结构
        output_state = {**input_state, **node_result}
        print("\n=== 3. 输出 State (更新后) ===")
        pprint(output_state)

    asyncio.run(main())
