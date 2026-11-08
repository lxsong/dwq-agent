"""
字段取值 ES 仓储

把字段真实取值组织成 Elasticsearch 全文索引，并提供索引创建 批量写入和关键词检索能力

Service 层负责决定哪些字段需要同步
Repository 只关心索引是否存在 ValueInfo 如何写进 ES 以及如何按关键词召回
"""

from dataclasses import asdict

from elasticsearch import AsyncElasticsearch

from app.entities.value_info import ValueInfo


class ValueESRepository:
    """负责字段取值全文索引的创建 写入和基础检索"""

    index_name = "value_index"
    # 显式定义 Mapping：id 和 column_id 用 keyword 精确存储；value 用 text + ik_max_word 支持中文全文检索
    index_mappings = {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "value": {
                "type": "text",
                "analyzer": "ik_max_word",
                "search_analyzer": "ik_max_word",
            },
            "column_id": {"type": "keyword"},
        },
    }

    def __init__(self, client: AsyncElasticsearch):
        self.client = client

    async def ensure_index(self):
        """幂等确保字段取值索引已经创建好"""
        if not await self.client.indices.exists(index=self.index_name):
            await self.client.indices.create(
                index=self.index_name, mappings=self.index_mappings
            )

    async def index(self, value_infos: list[ValueInfo], batch_size=20):
        """分批写入字段取值（每批20条），避免单次 bulk 请求体过大"""
        if not value_infos:
            return

        for i in range(0, len(value_infos), batch_size):
            batch_value_infos = value_infos[i : i + batch_size]
            batch_operations = []
            for value_info in batch_value_infos:
                # 奇数行（操作描述）：显式指定 _id = value_info.id（如 dim_region.region_name.华北）
                # 这样重复运行构建脚本时，相同的值会直接幂等覆盖，绝不会在 ES 里产生重复文档！
                batch_operations.append(
                    {"index": {"_index": self.index_name, "_id": value_info.id}}
                )
                # 偶数行（文档本体）：写入 ValueInfo 转换后的字典
                batch_operations.append(asdict(value_info))
            await self.client.bulk(operations=batch_operations)

    async def search(
        self, keyword: str, score_threshold: float = 0.6, limit: int = 20
    ) -> list[ValueInfo]:
        """按关键词全文检索字段取值，过滤低分噪音后直接还原为 ValueInfo 实体列表"""
        resp = await self.client.search(
            index=self.index_name,
            query={"match": {"value": keyword}},
            size=limit,
            min_score=score_threshold,  # 过滤 BM25 得分低于 0.6 的弱相关匹配
        )
        return [ValueInfo(**hit["_source"]) for hit in resp["hits"]["hits"]]