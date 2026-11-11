"""
问数 Agent 状态定义
"""

from typing import TypedDict

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo


class DataAgentState(TypedDict):
    """一次问数链路中的核心共享状态"""

    query: str                                # 用户输入的原始自然语言问题
    keywords: list[str]                       # extract_keywords 节点抽取出的关键词列表
    retrieved_column_infos: list[ColumnInfo]  # recall_column 节点召回的候选字段实体列表
    retrieved_metric_infos: list[MetricInfo]  # recall_metric 节点召回的候选指标实体列表
    retrieved_value_infos: list[ValueInfo]    # recall_value 节点召回的候选取值实体列表
    error: str | None                         # 校验 SQL 时出现的错误信息