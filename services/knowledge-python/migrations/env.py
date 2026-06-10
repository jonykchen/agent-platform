"""Alembic 迁移环境 - Knowledge Service

从应用配置读取数据库 URL（DATABASE_URL），将 asyncpg 驱动转换为同步驱动
（psycopg）以供 alembic 迁移使用。迁移均为原生 SQL（op.execute），无需
SQLAlchemy ORM 模型。
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

# 显式以 UTF-8 读取日志配置，避免 Windows 默认 GBK 解码中文注释报错
if config.config_file_name is not None:
    fileConfig(config.config_file_name, encoding="utf-8")


def _resolve_database_url() -> str:
    """从应用配置解析同步数据库 URL（alembic 需同步驱动）"""
    try:
        from app.core.config import config as app_config

        url = app_config.database_url
    except Exception:
        import os

        url = os.environ.get(
            "DATABASE_URL",
            "postgresql://app_user:dev_password@localhost:5432/agent_platform",
        )
    # alembic 使用同步驱动：去掉 +asyncpg，改用 psycopg（v3）
    return url.replace("+asyncpg", "+psycopg")


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 而不连接数据库"""
    context.configure(
        url=_resolve_database_url(),
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移"""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _resolve_database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
