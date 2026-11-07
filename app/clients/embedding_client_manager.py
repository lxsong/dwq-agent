"""
Embedding 客户端管理器

负责按配置初始化 Embedding 服务客户端，并为字段、指标和用户问题的向量化
提供统一访问入口
"""

import asyncio
from typing import Optional

from huggingface_hub import AsyncInferenceClient, InferenceClient
from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.conf.app_config import EmbeddingConfig, app_config


class EmbeddingClientManager:
    """管理 Embedding 服务客户端的初始化与复用"""

    def __init__(self, config: EmbeddingConfig):
        # 1. 延迟初始化：模块导入阶段不立即创建客户端连接
        self.client: Optional[HuggingFaceEndpointEmbeddings] = None
        # 2. 保存 app_config.embedding 配置 (host='localhost', port=8081, model='BAAI/bge-large-zh-v1.5')
        self.config = config

    def _get_url(self) -> str:
        """拼接本地 TEI Embedding 服务基础地址，如 http://localhost:8081"""
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        """显式初始化客户端，避免模块导入时立即建立外部连接"""
        # 第一步：使用模型名称 (BAAI/bge-large-zh-v1.5) 实例化 LangChain 包装器
        self.client = HuggingFaceEndpointEmbeddings(model=self.config.model)
        # 第二步：拼接 TEI 服务的实际推理端点路径 http://localhost:8081/embed
        endpoint_url = f"{self._get_url()}/embed"
        # 第三步：【核心技巧】显式替换底层同步与异步推理客户端，将其指向本地 TEI 容器端点！
        self.client.client = InferenceClient(model=endpoint_url)
        self.client.async_client = AsyncInferenceClient(model=endpoint_url)


# 模块级全局单例，供整个项目复用同一套 Embedding 客户端管理器
embedding_client_manager = EmbeddingClientManager(app_config.embedding)


if __name__ == "__main__":
    # 本地独立调试入口：初始化客户端并测试异步向量化
    embedding_client_manager.init()
    client = embedding_client_manager.client

    async def test():
        """执行一次最小化向量化调用，验证本地 TEI 服务是否可用"""
        text = "What is deep learning?"
        query_result = await client.aembed_query(text)
        print(f"向量维度: {len(query_result)}")
        print(f"前 3 维数值: {query_result[:3]}")

    asyncio.run(test())