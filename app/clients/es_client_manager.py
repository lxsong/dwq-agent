"""
Elasticsearch 客户端管理器

统一创建和管理 Elasticsearch 异步客户端，
主要服务于字段真实取值的全文索引构建和检索
"""

import asyncio
from typing import Optional

from elasticsearch import AsyncElasticsearch

from app.conf.app_config import ESConfig, app_config


class ESClientManager:
    """管理 Elasticsearch 客户端的生命周期"""

    def __init__(self, es_config: ESConfig):
        # 1. 保存从 app_config.es 传入的配置对象 (包含 host, port, index_name)
        self.es_config = es_config
        # 2. 延迟初始化：仅声明类型，在 init() 中真正实例化
        self.client: Optional[AsyncElasticsearch] = None

    def _get_url(self) -> str:
        """拼接 Elasticsearch 服务 HTTP 地址，如 http://localhost:9200"""
        return f"http://{self.es_config.host}:{self.es_config.port}"

    def init(self):
        """
        初始化异步 Elasticsearch 客户端
        注意：hosts 参数之所以接收列表 list[str]，是因为生产环境中 ES 常以多节点集群部署，
        客户端支持传入多个节点地址做负载均衡与故障转移；本地教学环境为单节点，传入单元素列表即可。
        """
        self.client = AsyncElasticsearch(hosts=[self._get_url()])

    async def close(self):
        """关闭底层 aiohttp 异步连接池"""
        await self.client.close()


# 创建全局单例的 ES 客户端管理器对象
es_client_manager = ESClientManager(app_config.es)

if __name__ == "__main__":
    # 本地独立调试入口
    es_client_manager.init()

    async def test():
        """执行一次索引幂等创建、bulk 批量写入与 match 全文查询，验证 ES 异步接入链路"""
        client = es_client_manager.client

        try:
            # 1. 幂等创建索引：先检查 my-books 是否存在，已存在则跳过，避免重复运行脚本报 400 错误
            if not await client.indices.exists(index="my-books"):
                await client.indices.create(
                    index="my-books",
                    mappings={
                        "dynamic": False,  # 关闭动态映射，严格约束字段结构
                        "properties": {
                            "name": {"type": "text"},
                            "author": {"type": "text"},
                            "release_date": {"type": "date", "format": "yyyy-MM-dd"},
                            "page_count": {"type": "integer"},
                        },
                    },
                )

            # 2. 批量写入文档：采用“操作说明行 + 数据本体行”交替出现的格式
            # refresh="wait_for" 或默认写入后，ES 会建立倒排索引
            await client.bulk(
                operations=[
                    {"index": {"_index": "my-books"}},
                    {
                        "name": "Revelation Space",
                        "author": "Alastair Reynolds",
                        "release_date": "2000-03-15",
                        "page_count": 585,
                    },
                    {"index": {"_index": "my-books"}},
                    {
                        "name": "1984",
                        "author": "George Orwell",
                        "release_date": "1985-06-01",
                        "page_count": 328,
                    },
                    {"index": {"_index": "my-books"}},
                    {
                        "name": "Fahrenheit 451",
                        "author": "Ray Bradbury",
                        "release_date": "1953-10-15",
                        "page_count": 227,
                    },
                    {"index": {"_index": "my-books"}},
                    {
                        "name": "Brave New World",
                        "author": "Aldous Huxley",
                        "release_date": "1932-06-01",
                        "page_count": 268,
                    },
                    {"index": {"_index": "my-books"}},
                    {
                        "name": "The Handmaids Tale",
                        "author": "Margaret Atwood",
                        "release_date": "1985-06-01",
                        "page_count": 311,
                    },
                ],
                refresh=True,  # 测试脚本中加上 refresh=True 可确保写入后立即可被 search 查到
            )

            # 3. 执行 match 全文检索：在 name 字段中搜索包含 "brave" 词项的书籍（不区分大小写）
            resp = await client.search(
                index="my-books",
                query={"match": {"name": "brave"}},
            )

            print(resp)
        finally:
            # 4. 无论成功还是抛异常，均确保关闭底层连接，消除 Unclosed client session 警告
            await es_client_manager.close()

    asyncio.run(test())