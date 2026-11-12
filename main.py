"""
FastAPI 应用入口
"""

from fastapi import FastAPI

from app.api.routers.query_router import query_router

# 1. 创建 FastAPI 核心应用实例
app = FastAPI()

# 2. 将 query_router 挂载到主应用上（若漏掉这行，/api/query 路由不会生效）
app.include_router(query_router)