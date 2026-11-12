"""
电商问数 Agent 状态定义（第 12 章合并上下文版）
"""

from typing import TypedDict

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo


class MetricInfoState(TypedDict):
    """面向 SQL 生成提示词的指标信息（剔除内部 id）"""

    name: str
    description: str
    # 指标依赖的底层字段 id 列表，提示模型不要脱离业务口径随意计算
    relevant_columns: list[str]
    alias: list[str]


class ColumnInfoState(TypedDict):
    """表上下文中的字段信息（剔除内部 id 与 table_id）"""

    name: str
    type: str
    role: str
    # 字段真实样例值（含 ES 召回并回填进来的真实过滤值），辅助模型写对 WHERE 条件
    examples: list
    description: str
    alias: list[str]


class TableInfoState(TypedDict):
    """SQL 生成阶段真正传给模型的表结构上下文（表下嵌套字段列表）"""

    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]

class DateInfoState(TypedDict):
    """SQL 生成阶段使用的当前日期上下文"""

    date: str     # 格式 YYYY-MM-DD，如 "2026-04-27"
    weekday: str  # 英文星期名称，如 "Monday"
    quarter: str  # 当前季度，如 "Q2"


class DBInfoState(TypedDict):
    """SQL 生成阶段使用的数据库环境信息"""

    dialect: str  # 数据库方言名称，如 "mysql"
    version: str  # 数据库具体版本号，如 "8.0.45"


class DataAgentState(TypedDict):
    """一次问数链路中的核心共享状态"""

    query: str                                # 用户输入的查询
    keywords: list[str]                       # 抽取的关键词
    retrieved_column_infos: list[ColumnInfo]  # 检索到的字段信息
    retrieved_metric_infos: list[MetricInfo]  # 检索到的指标信息
    retrieved_value_infos: list[ValueInfo]    # 检索到的取值信息

    table_infos: list[TableInfoState]         # 合并和补齐后的表结构上下文
    metric_infos: list[MetricInfoState]       # 合并后的指标上下文

    date_info: DateInfoState  # 当前日期、星期和季度信息
    db_info: DBInfoState      # 数仓数据库方言和版本信息

    error: str | None                         # 校验 SQL 时出现的错误信息