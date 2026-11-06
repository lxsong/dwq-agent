"""
Qdrant 快速入门示例

演示最小化的集合创建、向量写入和相似度查询流程，便于理解 Qdrant 的基本数据模型
运行方式：uv run python -m examples.qdrant_quickstart_demo
"""

import asyncio

from qdrant_client import AsyncQdrantClient, models

QDRANT_URL = "http://192.168.56.121:6333"
COLLECTION_NAME = "quickstart_demo"
# 演示用 4 维短向量；正式项目中将使用 app_config.qdrant.embedding_size (1024维)
VECTOR_SIZE = 4


async def recreate_collection(client: AsyncQdrantClient):
    """第一步：删除旧集合并重新创建，确保示例脚本可以重复运行"""
    if await client.collection_exists(COLLECTION_NAME):
        await client.delete_collection(COLLECTION_NAME)

    # 创建集合：必须显式声明向量维度(size)与距离计算方式(distance)
    await client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=VECTOR_SIZE,
            distance=models.Distance.COSINE,
        ),
    )
    print(f"1. 已创建集合：{COLLECTION_NAME}")


async def add_vectors(client: AsyncQdrantClient):
    """
    第二步：使用 upsert 批量写入示例向量点
    注意：upsert = update + insert（若 id 已存在则覆盖更新，不存在则新增）
    每个 PointStruct 包含唯一 id、向量 vector 以及附带的业务字典 payload
    """
    await client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=1,
                vector=[0.05, 0.61, 0.76, 0.74],
                payload={"name": "订单分析", "type": "report"},
            ),
            models.PointStruct(
                id=2,
                vector=[0.19, 0.81, 0.75, 0.11],
                payload={"name": "销量趋势", "type": "metric"},
            ),
            models.PointStruct(
                id=3,
                vector=[0.36, 0.55, 0.47, 0.94],
                payload={"name": "区域销售额", "type": "dimension"},
            ),
        ],
    )
    print("2. 已写入 3 个向量点。")


async def run_query(client: AsyncQdrantClient):
    """
    第三步：执行向量相似度查询 (query_points)
    传入查询向量 query_vector，Qdrant 会按余弦相似度从高到低返回最相近的 top-K 个点
    """
    query_vector = [0.2, 0.1, 0.9, 0.7]
    result = await client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=3,              # 最多返回前 3 条最相似结果
        with_payload=True,    # 将点上挂载的业务 payload 一起带回（默认即为 True）
    )

    print(f"3. 查询向量：{query_vector}")
    print("4. 查询结果（按余弦相似度 score 降序排列）：")
    for i, point in enumerate(result.points, start=1):
        print(
            f"   {i}) id={point.id}, score={point.score:.4f}, payload={point.payload}"
        )


async def main():
    """串联整个 quickstart 异步流程，并在结束时确保关闭网络连接"""
    client = AsyncQdrantClient(url=QDRANT_URL)

    try:
        await recreate_collection(client)
        await add_vectors(client)
        await run_query(client)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())