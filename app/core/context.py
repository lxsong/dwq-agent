"""
请求上下文

用于保存和传递一次请求或一次脚本执行过程中的上下文变量，
当前先维护 request_id，后续日志模块会从这里读取 request_id 并注入到每条日志中
"""

from contextvars import ContextVar

# 使用 ContextVar 而不是普通全局变量，让并发协程之间的 request_id 互不干扰
# 设置 default="1" 是为了兼容不经过 FastAPI 中间件的本地离线脚本（如 build_meta_knowledge.py）
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="1")