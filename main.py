"""
FastAPI 应用入口

负责创建后端应用实例，注册应用生命周期函数，并把各业务模块中的 router
挂载到同一个 app 上。HTTP 请求会先进入这里创建的 app，再按路由分发到
具体的接口处理函数。
"""

import uuid

from fastapi import FastAPI, Request

from app.api.lifespan import lifespan
from app.api.routers.query_router import query_router
from app.core.context import request_id_ctx_var

# 1. 创建 FastAPI 应用并注册 lifespan 生命周期管理
app = FastAPI(lifespan=lifespan)

# 2. 挂载查询路由
app.include_router(query_router)


# 3. 注册全局 HTTP 中间件：拦截每一个进入系统的 HTTP 请求
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    # 【请求进入路由处理之前】
    # 生成全局唯一的 UUID 作为本次请求的追踪标识，并写入当前协程的 ContextVar 中
    request_id = uuid.uuid4()
    request_id_ctx_var.set(request_id)

    # 将请求继续传递给后续的路由处理函数 (如 query_handler)
    response = await call_next(request)

    # 【路由生成响应之后】返回响应给客户端
    return response