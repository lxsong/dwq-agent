"""
日志初始化

集中管理项目的日志输出行为，包括统一日志格式 注入 request_id 以及按配置输出到控制台和文件
业务代码只需要导入这里的 logger，就可以使用同一套日志能力
"""

import sys
from pathlib import Path

from loguru import logger

from app.conf.app_config import app_config
from app.core.context import request_id_ctx_var

# 1. 定义统一日志格式模板：展示毫秒级时间、对齐的日志级别、request_id、模块:函数:行号 以及日志消息
log_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<magenta>request_id - {extra[request_id]}</magenta> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def inject_request_id(record):
    """钩子函数：在每条日志写出前，自动把当前协程上下文中的 request_id 注入到 record['extra'] 字典"""
    request_id = request_id_ctx_var.get()
    record["extra"]["request_id"] = request_id


# 2. 先移除 Loguru 自带的默认控制台处理器（否则后面再 add 会导致每条日志在控制台重复打印两遍，且默认格式不含 extra[request_id] 会报错）
logger.remove()

# 3. 通过 patch 挂载钩子函数，生成具备自动注入 request_id 能力的全局 logger
logger = logger.patch(inject_request_id)

# 4. 根据 app_config.yaml 配置决定是否开启控制台日志通道
if app_config.logging.console.enable:
    logger.add(
        sink=sys.stdout,
        level=app_config.logging.console.level,
        format=log_format,
    )

# 5. 根据 app_config.yaml 配置决定是否开启文件日志通道，并自动创建 logs 目录
if app_config.logging.file.enable:
    path = Path(app_config.logging.file.path)
    path.mkdir(parents=True, exist_ok=True)
    logger.add(
        sink=path / "app.log",
        level=app_config.logging.file.level,
        format=log_format,
        rotation=app_config.logging.file.rotation,    # 如 "10 MB"：单文件满 10MB 自动切分
        retention=app_config.logging.file.retention,  # 如 "7 days"：自动清理超过 7 天的旧日志
        encoding="utf-8",
    )