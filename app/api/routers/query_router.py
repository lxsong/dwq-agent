"""
问数查询接口路由（第 15 章最小流式验证版）
"""

import asyncio

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from app.api.schemas.query_schema import QuerySchema

# 创建查询专属的路由器实例，后续由 main.py 统一挂载到 FastAPI app 上
query_router = APIRouter()


async def fake_streamer():
    """模拟问数智能体分步骤产出的异步生成器 (Async Generator)"""
    for i in range(10):
        # 暂停 1 秒模拟节点执行耗时，方便肉眼观察逐条流式返回效果
        await asyncio.sleep(1)
        # 每次 yield 产出一个符合 SSE 协议格式的字符串片段 (data: 开头，\n\n 结尾)
        yield f"data: step:{i}\n\n"


@query_router.post("/api/query")
async def query_handler(query: QuerySchema):
    """接收用户自然语言问题，并以 SSE 流式协议持续返回执行进度"""
    # StreamingResponse 接收异步生成器 fake_streamer()，
    # 每当生成器内部 yield 一次，FastAPI 就立即将该段文本通过 HTTP 分块传输 (Chunked) 刷给客户端！
    return StreamingResponse(
        fake_streamer(),
        media_type="text/event-stream",
    )