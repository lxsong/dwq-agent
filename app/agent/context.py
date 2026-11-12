"""
电商问数 Agent 运行上下文
"""

from typing import TypedDict

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class DataAgentContext(TypedDict):
    """LangGraph Runtime 中传递的无状态外部依赖工具容器"""

    # 字段向量仓储，负责从 Qdrant column_info_collection 检索候选字段
    column_qdrant_repository: ColumnQdrantRepository
    # Embedding 客户端，字段召回和指标召回都会复用它将关键词转为 1024 维向量
    embedding_client: HuggingFaceEndpointEmbeddings
    # 指标向量仓储，负责从 Qdrant metric_info_collection 检索候选指标
    metric_qdrant_repository: MetricQdrantRepository
    # 字段取值全文检索仓储，负责从 Elasticsearch value_index 检索真实字段值
    value_es_repository: ValueESRepository
    # 元数据仓储，负责在召回结果合并时补齐字段 表 主外键等结构信息
    meta_mysql_repository: MetaMySQLRepository
    # 数仓仓储，负责查询数据库方言/版本及后续 SQL 执行
    dw_mysql_repository: DWMySQLRepository