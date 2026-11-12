"""
数仓 MySQL 仓储

这一层对应文档里的 DW Repository，职责是到真实数仓中补齐配置文件里
没有显式维护的信息，例如字段类型和字段示例值。Service 层只关心
“需要哪些信息”，具体怎样查数仓由仓储层统一封装
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class DWMySQLRepository:
    """负责查询数仓真实表结构和字段样例值"""

    def __init__(self, session: AsyncSession):
        # 注入绑定到 dw 库的请求/任务级 AsyncSession
        self.session = session

    async def get_column_types(self, table_name: str) -> dict[str, str]:
        """查询整张表的字段类型，作为 ColumnInfo.type 的真实来源"""
        sql = f"show columns from {table_name}"
        result = await self.session.execute(text(sql))
        # mappings().fetchall() 将结果行转为字典形态，提取 Field(列名) -> Type(物理类型)
        result_dict = result.mappings().fetchall()
        return {row["Field"]: row["Type"] for row in result_dict}

    async def get_column_values(
        self, table_name: str, column_name: str, limit: int = 10
    ) -> list:
        """抽样查询字段去重示例值，供元数据入库和后续 ES 检索链路复用"""
        sql = f"select distinct {column_name} from {table_name} limit {limit}"
        result = await self.session.execute(text(sql))
        # row[0] 取出单列查询结果中的实际字段值，组装为纯 Python list
        return [row[0] for row in result.fetchall()]

    async def get_db_info(self) -> dict[str, str]:
        """读取当前数仓数据库的方言和版本，供 SQL 生成提示词使用"""

        # 1. 执行 SELECT version() 查询数据库真实版本号，使用 scalar() 直接提取单行单列标量值
        sql = "select version()"
        result = await self.session.execute(text(sql))
        version = result.scalar()

        # 2. 从 SQLAlchemy Session 绑定的 Engine 中直接读取当前数据库方言名称（如 "mysql"）
        dialect = self.session.bind.dialect.name
        return {"dialect": dialect, "version": version}