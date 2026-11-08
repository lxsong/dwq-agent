"""
字段取值业务实体

该对象用于承接字段值同步链路中的结构化结果，和表、字段、指标实体保持
一致的业务层表达方式
"""

from dataclasses import dataclass


@dataclass
class ValueInfo:
    """字段具体取值及其所属字段的业务表达"""

    id: str         # 取值唯一标识，格式为 "表名.字段名.真实取值"（如 dim_region.region_name.华北）
    value: str      # 字段中的真实字符串值（如 华北），在 ES 中配置为 text + ik_max_word 分词
    column_id: str  # 该取值所属的字段 ID（如 dim_region.region_name），用于命中后挂回对应字段