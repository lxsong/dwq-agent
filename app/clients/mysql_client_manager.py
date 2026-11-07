"""
MySQL 客户端管理器

统一创建和管理项目中的异步 MySQL 客户端，当前项目会同时连接两套 MySQL
一套是保存结构化元数据的 meta 数据库，一套是模拟教学数仓的 dw 数据库
模块对外提供可复用的客户端管理器和 session 工厂
方便脚本入口 服务层和仓储层按统一方式访问数据库
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.conf.app_config import DBConfig, app_config


class MySQLClientManager:
    """管理 MySQL AsyncEngine 连接池和 AsyncSession 工厂"""

    def __init__(self, config: DBConfig):
        # 1. Engine 是数据库连接层核心对象，底层维护连接池（延迟至 init() 初始化）
        self.engine: AsyncEngine | None = None
        # 2. session_factory 用于按请求/按任务创建独立的 AsyncSession
        self.session_factory = None
        # 3. 保存传入的数据库配置（可能是 app_config.db_meta 或 app_config.db_dw）
        self.config = config

    def _get_url(self) -> str:
        """
        拼接 SQLAlchemy 异步 MySQL 连接地址 (DSN)
        格式协议头 mysql+asyncmy 表示：数据库方言为 mysql，底层异步驱动为 asyncmy
        charset=utf8mb4 确保完整支持中文与 Emoji 字符
        """
        return (
            f"mysql+asyncmy://{self.config.user}:{self.config.password}"
            f"@{self.config.host}:{self.config.port}/{self.config.database}?charset=utf8mb4"
        )

    def init(self):
        """初始化异步 Engine 连接池和 Session 工厂"""
        # 创建异步 Engine：pool_size=10 维持10个常驻连接，pool_pre_ping=True 开启取连接前的存活探针
        self.engine = create_async_engine(
            self._get_url(), pool_size=10, pool_pre_ping=True
        )
        # 基于 Engine 创建异步 Session 工厂
        self.session_factory = async_sessionmaker(
            self.engine, autoflush=True, expire_on_commit=False
        )

    async def close(self):
        """应用退出时优雅释放连接池中的所有物理连接"""
        await self.engine.dispose()


# 实例化两套全局管理器：一套连 meta 元数据库，一套连 dw 教学数仓
meta_mysql_client_manager = MySQLClientManager(app_config.db_meta)
dw_mysql_client_manager = MySQLClientManager(app_config.db_dw)

if __name__ == "__main__":
    # 本地独立调试：初始化 dw 数仓连接池并查询 fact_order 前 10 条数据
    dw_mysql_client_manager.init()

    async def test():
        """执行一次简单查询，验证 MySQL 异步连接池与 RowMapping 结果结构"""
        try:
            async with dw_mysql_client_manager.session_factory() as session:
                sql = "select * from fact_order limit 10"
                result = await session.execute(text(sql))
                # mappings().fetchall() 会将每一行结果包装为类似字典的 RowMapping 对象
                rows = result.mappings().fetchall()
                print(f"结果集类型: {type(rows)}")
                print(f"单行对象类型: {type(rows[0])}")
                print(f"第一条订单号 order_id: {rows[0]['order_id']}")
        finally:
            await dw_mysql_client_manager.close()

    asyncio.run(test())