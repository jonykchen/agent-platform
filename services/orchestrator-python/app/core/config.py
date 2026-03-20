"""核心配置 - Pydantic Settings"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """应用主配置"""

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # ====== 环境 ======
    environment: str = Field(default="local", description="local/dev/test/staging/prod")
    debug: bool = Field(default=False)
    app_name: str = "orchestrator"
    app_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000

    # ====== 模型网关地址 ======
    model_gateway_url: str = "http://localhost:8001"
    tool_bus_grpc_addr: str = "localhost:50051"

    # ====== 数据库 [SECRET] ======
    database_url: str = Field(
        default="postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform",
        description="[SECRET] PostgreSQL 异步连接 URL",
    )
    database_pool_size: int = 20

    # ====== Redis [SECRET] ======
    redis_url: str = Field(
        default="redis://:dev_password@localhost:6379/0",
        description="[SECRET] Redis 连接 URL",
    )

    # ====== LLM API Keys [SECRET] ======
    qwen_api_key: str = Field(default="", description="[SECRET] 通义千问 API Key")
    glm_api_key: str = Field(default="", description="[SECRET] 智谱 GLM API Key")
    kimi_api_key: str = Field(default="", description="[SECRET] Moonshot Kimi API Key")
    deepseek_api_key: str = Field(default="", description="[SECRET] DeepSeek API Key")

    # ====== JWT [SECRET] ======
    jwt_secret: str = Field(
        default="dev-only-change-me-in-production-min-32-chars!!!",
        description="[SECRET] JWT 签名密钥（生产必须 ≥ 32 字符）",
    )
    jwt_algorithm: str = "HS256"
    jwt_expiry_seconds: int = 86400  # 24h

    # ====== OpenTelemetry ======
    otel_enabled: bool = True
    otlp_endpoint: str = "http://localhost:4317"

    # ====== Agent 配置 ======
    max_agent_steps: int = 10
    agent_total_timeout_s: int = 300
    model_call_timeout_s: int = 30
    tool_call_timeout_s: int = 15

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        if info.data.get("environment") == "prod" and len(v) < 32:
            raise ValueError("Production JWT secret must be at least 32 characters")
        return v


@lru_cache
def get_config() -> AppConfig:
    """获取配置单例"""
    return AppConfig()


# 全局配置实例
config = get_config()
