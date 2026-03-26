"""基础设施层

提供底层服务连接和资源管理：
- database: PostgreSQL 异步连接池
- grpc_client: gRPC 客户端连接池
"""

from app.infrastructure.database import (
    init_database_pool,
    close_database_pool,
    get_database_pool,
    get_connection,
    transaction,
    execute_query,
    fetch_one,
    fetch_all,
    fetch_val,
    execute_many,
    check_database_health,
)

from app.infrastructure.grpc_client import (
    init_grpc_client,
    close_grpc_client,
    get_grpc_channel,
    get_stub,
    call_tool_bus,
    check_grpc_health,
)

__all__ = [
    # Database
    "init_database_pool",
    "close_database_pool",
    "get_database_pool",
    "get_connection",
    "transaction",
    "execute_query",
    "fetch_one",
    "fetch_all",
    "fetch_val",
    "execute_many",
    "check_database_health",
    # gRPC
    "init_grpc_client",
    "close_grpc_client",
    "get_grpc_channel",
    "get_stub",
    "call_tool_bus",
    "check_grpc_health",
]
