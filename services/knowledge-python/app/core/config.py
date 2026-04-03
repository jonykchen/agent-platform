"""Knowledge Service 配置"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """知识库服务配置"""

    environment: str = "local"
    debug: bool = False
    port: int = 8003

    # 数据库配置
    database_url: str = Field(
        default="postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform",
        description="[SECRET] PostgreSQL 连接 URL",
    )
    database_pool_size: int = 10

    # Redis
    redis_url: str = "redis://:dev_password@localhost:6379/2"

    # Embedding 服务配置 - 指向 model-gateway
    embedding_service_url: str = "http://localhost:8002"
    embedding_model: str = "text-embedding-ada-002"
    embedding_dimension: int = 1536
    embedding_batch_size: int = 100

    # 文档处理配置
    chunk_size: int = 500  # 每个块的字符数
    chunk_overlap: int = 50  # 块之间的重叠字符数
    max_file_size_mb: int = 50  # 最大文件大小

    # 检索配置
    default_top_k: int = 10
    max_top_k: int = 100
    rerank_top_k: int = 20  # 重排序前的候选数量

    # 存储配置
    storage_type: str = "local"  # local / s3 / oss
    storage_path: str = "./uploads"

    @lru_cache
    def get_config(self) -> "AppConfig":
        return self


config = AppConfig()
