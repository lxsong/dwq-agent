"""
Qdrant 客户端管理器

统一创建和管理 Qdrant 异步客户端
主要用于保存字段和指标的向量索引，支撑后续问数流程中的语义召回
"""

import asyncio
import random
from typing import Optional

from qdrant_client import AsyncQdrantClient, models

from app.conf.app_config import QdrantConfig, app_config


class QdrantClientManager:
    """管理 Qdrant 客户端的初始化与关闭"""

    def __init__(self, qdrant_config: QdrantConfig):
        # 1. 注入第 4 章加载好的强类型配置对象 (包含 host, port, embedding_size)
        self.qdrant_config = qdrant_config
        # 2. 【核心设计】延迟初始化 (Lazy Init)：在 __init__ 中仅声明类型，不立即发起网络连接
        self.client: Optional[AsyncQdrantClient] = None

    def _get_url(self) -> str:
        """根据配置拼接 Qdrant 服务 HTTP 地址，如 http://localhost:6333"""
        return f"http://{self.qdrant_config.host}:{self.qdrant_config.port}"

    def init(self):
        """
        显式初始化 Qdrant 异步客户端
        在 FastAPI lifespan 启动阶段或离线脚本开头统一调用
        """
        self.client = AsyncQdrantClient(url=self._get_url())

    async def close(self):
        """在应用或脚本退出时统一关闭底层连接池"""
        await self.client.close()


# 创建全局单例管理器对象，后续全项目所有模块均导入此实例复用同一个客户端
qdrant_client_manager = QdrantClientManager(app_config.qdrant)


if __name__ == "__main__":
    # 本地独立调试入口：先显式调用 init() 初始化客户端
    qdrant_client_manager.init()

    async def test():
        """执行一次集合创建、100个随机向量写入与带阈值检索，验证封装链路"""
        client = qdrant_client_manager.client
        try:
            # 1. 幂等检查：如果集合不存在，再创建集合（防止重复运行报错）
            if not await client.collection_exists("my_collection"):
                await client.create_collection(
                    collection_name="my_collection",
                    vectors_config=models.VectorParams(
                        size=10,
                        distance=models.Distance.COSINE,
                    ),
                )

            # 2. 批量 upsert 100 个 10 维随机向量点
            await client.upsert(
                collection_name="my_collection",
                points=[
                    models.PointStruct(
                        id=i,
                        vector=[random.random() for _ in range(10)],
                    )
                    for i in range(100)
                ],
            )

            # 3. 相似度检索：limit=10 限制最多返回 10 条，score_threshold=0.8 过滤低相关度噪音
            res = await client.query_points(
                collection_name="my_collection",
                query=[random.random() for _ in range(10)],  # type: ignore
                limit=10,
                score_threshold=0.8,
            )

            print(res)
        finally:
            # 4. 调试结束关闭客户端连接
            await qdrant_client_manager.close()

    asyncio.run(test())