"""Model Gateway 配置"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """应用配置"""

    environment: str = "local"
    debug: bool = False
    port: int = 8001

    # Redis
    redis_url: str = "redis://:dev_password@localhost:6379/1"

    # 提供商配置
    qwen_api_key: str = Field(default="", description="[SECRET] Qwen API Key")
    qwen_base_url: str = "https://dashscope.aliyuncs.com/api/v1"

    glm_api_key: str = Field(default="", description="[SECRET] GLM API Key")
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"

    kimi_api_key: str = Field(default="", description="[SECRET] Kimi API Key")
    kimi_base_url: str = "https://api.moonshot.cn/v1"

    deepseek_api_key: str = Field(default="", description="[SECRET] DeepSeek API Key")
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # 熔断配置
    circuit_breaker_threshold: int = 10
    circuit_breaker_timeout_s: int = 30

    # 超时配置
    request_timeout_s: int = 30

    @lru_cache
    def get_config(self) -> "AppConfig":
        return self


config = AppConfig()
