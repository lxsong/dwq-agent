"""
问数查询服务

负责把 API 层传入的自然语言问题转换成一次 LangGraph 工作流执行：
创建初始 State、组装 Runtime Context、消费 graph.astream 的流式输出，
并统一包装成 SSE 文本返回给路由层。
"""

import json

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class QueryService:
    """封装一次问数查询所需的业务编排逻辑"""

    def __init__(
        self,
        meta_mysql_repository: MetaMySQLRepository,
        embedding_client: HuggingFaceEndpointEmbeddings,
        dw_mysql_repository: DWMySQLRepository,
        column_qdrant_repository: ColumnQdrantRepository,
        metric_qdrant_repository: MetricQdrantRepository,
        value_es_repository: ValueESRepository,
    ):
        # 1. 保存由 FastAPI 依赖注入层 (dependencies.py) 组装并传入的 6 个外部工具依赖
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository

    async def query(self, query: str):
        """执行一次问数工作流，并作为异步生成器逐段 yield 产出 SSE 消息"""

        # 2. 初始化可变业务状态 State（仅传入用户原始提问 query，其余字段由图节点逐步写入）
        state = DataAgentState(query=query)

        # 3. 组装只读运行时工具上下文 Context（供图节点通过 runtime.context['...'] 读取）
        context = DataAgentContext(
            column_qdrant_repository=self.column_qdrant_repository,
            embedding_client=self.embedding_client,
            metric_qdrant_repository=self.metric_qdrant_repository,
            value_es_repository=self.value_es_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository,
        )
        try:
            # 4. 启动 LangGraph 异步流式执行，stream_mode="custom" 专门接收各节点 writer(...) 写出的字典
            async for chunk in graph.astream(
                input=state, context=context, stream_mode="custom"
            ):
                # 5. 将节点写出的 Python dict 序列化为 JSON 字符串，并包裹进 SSE 标准帧 (data: ...\n\n)
                # ensure_ascii=False 保留中文不转义；default=str 兜底处理 Decimal/date 等非标准 JSON 类型！
                yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            # 6. 流式中途异常兜底：包装为 type="error" 的 SSE 消息通知前端
            error = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error, ensure_ascii=False, default=str)}\n\n"