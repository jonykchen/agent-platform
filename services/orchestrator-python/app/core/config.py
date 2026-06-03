"""核心配置 - Pydantic Settings

【核心概念】配置管理的最佳实践
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

在企业级应用中，配置管理需要解决以下问题：
1. 多环境支持：local/dev/test/staging/prod
2. 敏感信息保护：API Key、密码等不能硬编码
3. 类型安全：配置值的类型检查
4. 默认值管理：合理的默认值 + 必填项校验

【技术选型】为什么使用 Pydantic Settings？
┌─────────────────────────────────────────────────────────────────────────┐
│  方案              │  优点                    │  缺点                  │
├────────────────────┼──────────────────────────┼────────────────────────┤
│  os.getenv()       │  简单直接                │  无类型检查、无默认值  │
│  python-dotenv     │  支持 .env 文件          │  无类型转换、无验证    │
│  Dynaconf          │  功能丰富                │  依赖重、学习曲线      │
│  ✓ Pydantic Settings│  类型安全+验证+环境变量  │  需要 Pydantic V2      │
└─────────────────────────────────────────────────────────────────────────┘

Pydantic Settings 的优势：
- 自动从环境变量读取（支持嵌套：DB__HOST → db.host）
- 类型转换：环境变量 "123" → int 123
- 验证器：@field_validator 支持复杂校验逻辑
- .env 文件支持：开发时使用 .env.local

【安全原则】
- [SECRET] 标记敏感配置，生产环境必须通过环境变量注入
- 默认值使用开发密码，生产环境启动时会校验
- JWT 密钥生产环境强制 ≥ 32 字符

【配置加载顺序】（优先级从高到低）
1. 环境变量（生产推荐）
2. .env.local 文件（开发使用）
3. 代码中的默认值

【参考】
- Pydantic Settings 文档: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- 12-Factor App 配置原则: https://12factor.net/config
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """应用主配置

    【Pydantic Settings 使用要点】

    1. 环境变量映射规则：
       - 环境变量名大写：DATABASE_URL → database_url
       - 嵌套使用双下划线：REDIS__URL → redis.url

    2. 类型转换示例：
       - DATABASE_POOL_SIZE=20  → int 20
       - DEBUG=true              → bool True
       - ALLOWED_ORIGINS=["a","b"] → list ["a", "b"]

    3. 敏感配置标记：
       - Field(description="[SECRET]") 标记敏感信息
       - 日志输出时自动脱敏（见 logging.py）

    4. 验证器使用：
       @field_validator("field_name")
       @classmethod
       def validate_field(cls, v, info):
           if condition:
               raise ValueError("message")
           return v
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Pydantic Settings 配置
    # ─────────────────────────────────────────────────────────────────────────
    model_config = SettingsConfigDict(
        # 环境变量文件（开发时使用，生产环境通过环境变量注入）
        env_file=".env.local",
        env_file_encoding="utf-8",
        # 嵌套分隔符：REDIS__URL → redis.url
        env_nested_delimiter="__",
        # 忽略未定义的环境变量（避免警告）
        extra="ignore",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 环境配置 - 控制应用运行模式
    # ─────────────────────────────────────────────────────────────────────────

    # 环境：local（本地开发）/ dev（开发环境）/ test（测试）/ staging（预发）/ prod（生产）
    # 不同环境有不同的配置校验规则（如 prod JWT 密钥必须 ≥ 32 字符）
    environment: str = Field(default="local", description="local/dev/test/staging/prod")

    # 调试模式：开启后增加日志详细度，禁用某些安全检查
    # 生产环境必须为 False
    debug: bool = Field(default=False)

    # 应用标识：用于日志和监控区分多个服务
    app_name: str = "orchestrator"
    app_version: str = "1.0.0"

    # 服务监听配置
    host: str = "0.0.0.0"  # 监听所有网卡
    port: int = 8000

    # ─────────────────────────────────────────────────────────────────────────
    # 服务依赖地址 - 内部服务通信
    # ─────────────────────────────────────────────────────────────────────────

    # 模型网关地址 - 提供 LLM API 调用的统一入口
    # 模型网关负责：多提供商路由、熔断、成本追踪
    model_gateway_url: str = "http://localhost:8002"

    # 知识库服务地址 - 提供 RAG 检索
    knowledge_service_url: str = "http://localhost:8003"

    # ToolBus gRPC 地址 - 工具执行服务
    # 使用 gRPC 而非 HTTP 的原因：更高效的二进制传输、强类型约束
    tool_bus_grpc_addr: str = "localhost:50051"

    # ─────────────────────────────────────────────────────────────────────────
    # 数据库配置 [SECRET] - PostgreSQL 异步连接
    # ─────────────────────────────────────────────────────────────────────────

    # 使用 asyncpg 驱动而非 psycopg2 的原因：
    # - asyncpg 是纯 Python 实现，性能更好
    # - 完全支持 asyncio，不需要线程池
    # - 连接池管理更高效
    database_url: str = Field(
        default="postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform",
        description="[SECRET] PostgreSQL 异步连接 URL",
    )
    database_pool_size: int = 20  # 连接池大小，根据并发量调整

    # ─────────────────────────────────────────────────────────────────────────
    # Redis 配置 [SECRET] - 缓存和会话存储
    # ─────────────────────────────────────────────────────────────────────────

    # Redis 用途：
    # - Feature Flag 存储
    # - Session 历史
    # - Checkpoint 暂存
    # - 分布式锁
    redis_url: str = Field(
        default="redis://:dev_password@localhost:6379/0",
        description="[SECRET] Redis 连接 URL",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # LLM API Keys [SECRET] - 国内主流模型提供商
    # ─────────────────────────────────────────────────────────────────────────

    # 技术选型：使用国内模型而非 OpenAI 的原因
    # - 数据合规：部分行业数据不能出境
    # - 成本控制：国内模型价格更低
    # - 网络稳定：国内 CDN 加速，延迟更低
    # - 语言适配：中文语境优化更好

    # 通义千问（阿里云）- 主力模型
    qwen_api_key: str = Field(default="", description="[SECRET] 通义千问 API Key")

    # 智谱 GLM（清华系）- 备选模型
    glm_api_key: str = Field(default="", description="[SECRET] 智谱 GLM API Key")

    # Moonshot Kimi - 长文本能力强
    kimi_api_key: str = Field(default="", description="[SECRET] Moonshot Kimi API Key")

    # DeepSeek - 代码能力强，成本低
    deepseek_api_key: str = Field(default="", description="[SECRET] DeepSeek API Key")

    # ─────────────────────────────────────────────────────────────────────────
    # JWT 配置 [SECRET] - 认证令牌
    # ─────────────────────────────────────────────────────────────────────────

    # JWT 认证流程：
    # 1. 用户登录 → Gateway 生成 JWT
    # 2. 请求携带 JWT → 各服务校验
    # 3. JWT 过期 → 刷新令牌或重新登录
    jwt_secret: str = Field(
        default="dev-only-change-me-in-production-min-32-chars!!!",
        description="[SECRET] JWT 签名密钥（生产必须 ≥ 32 字符）",
    )
    jwt_algorithm: str = "HS256"  # HMAC-SHA256，性能好、兼容性强
    jwt_expiry_seconds: int = 86400  # 24 小时，平衡安全与用户体验

    # ─────────────────────────────────────────────────────────────────────────
    # OpenTelemetry 配置 - 分布式追踪
    # ─────────────────────────────────────────────────────────────────────────

    # OpenTelemetry 用于：
    # - 全链路追踪（request_id 关联）
    # - 性能分析（P99 延迟）
    # - 错误定位（异常堆栈）
    otel_enabled: bool = True
    otlp_endpoint: str = "http://localhost:4317"  # OTLP gRPC 端点

    # ─────────────────────────────────────────────────────────────────────────
    # Agent 执行配置 - 控制推理循环
    # ─────────────────────────────────────────────────────────────────────────

    # 默认模型配置
    default_model: str = "qwen-max"
    default_temperature: float = 0.7
    default_max_tokens: int = 2000

    # ReAct 模式的循环限制
    max_agent_steps: int = 10  # 最大推理步数，防止无限循环

    # 上下文窗口限制 - 【S-AGENT-03】防止 token 超限
    max_context_window_tokens: int = Field(default=128000, description="模型上下文窗口上限")
    context_response_reserved_tokens: int = Field(default=8000, description="响应预留 token 数")

    # 总超时时间 - 包含所有步骤
    agent_total_timeout_s: int = 300  # 5 分钟

    # 单次调用超时
    model_call_timeout_s: int = 30  # LLM 调用通常 5-30 秒
    tool_call_timeout_s: int = 15   # 工具调用通常较快

    # ─────────────────────────────────────────────────────────────────────────
    # 熔断器配置 - 故障隔离
    # ─────────────────────────────────────────────────────────────────────────

    circuit_failure_threshold: int = Field(default=5, description="熔断器失败阈值")
    circuit_recovery_timeout: int = Field(default=30, description="熔断器恢复超时（秒）")

    # ─────────────────────────────────────────────────────────────────────────
    # 重试配置 - 临时故障恢复
    # ─────────────────────────────────────────────────────────────────────────

    # 使用指数退避重试而非固定间隔的原因：
    # - 避免重试风暴：所有失败请求同时重试会加剧故障
    # - 给服务恢复时间：逐渐增加间隔
    retry_max_attempts: int = Field(default=3, description="最大重试次数")
    retry_min_wait: float = Field(default=1.0, description="最小等待时间（秒）")
    retry_max_wait: float = Field(default=10.0, description="最大等待时间（秒）")

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP 连接池配置 - 性能优化
    # ─────────────────────────────────────────────────────────────────────────

    # 使用 httpx 而非 requests 的原因：
    # - httpx 是异步 HTTP 客户端，与 FastAPI 配合更好
    # - 支持 HTTP/2，性能更高
    # - 连接池管理更精细
    http_max_connections: int = Field(default=100, description="HTTP 最大连接数")
    http_max_keepalive: int = Field(default=20, description="HTTP 最大 keepalive 连接数")
    http_keepalive_expiry: float = Field(default=30.0, description="HTTP keepalive 过期时间（秒）")

    # ─────────────────────────────────────────────────────────────────────────
    # 缓存配置 - 减少重复计算
    # ─────────────────────────────────────────────────────────────────────────

    # 多级缓存策略：
    # - L1 本地内存缓存（最快，容量小）
    # - L2 Redis 缓存（共享，容量大）
    cache_local_maxsize: int = Field(default=1000, description="本地缓存最大条数")
    cache_default_ttl: int = Field(default=600, description="默认缓存 TTL（秒）")
    cache_rag_ttl: int = Field(default=600, description="RAG 结果缓存 TTL（秒）")
    cache_tool_schema_ttl: int = Field(default=3600, description="工具 Schema 缓存 TTL（秒）")
    cache_model_list_ttl: int = Field(default=300, description="模型列表缓存 TTL（秒）")

    # ─────────────────────────────────────────────────────────────────────────
    # 并发限制 - 保护系统资源
    # ─────────────────────────────────────────────────────────────────────────

    # 使用信号量限制并发而非直接限制的原因：
    # - 信号量可动态调整
    # - 支持等待队列
    # - 与 asyncio 配合良好
    max_concurrent_requests: int = Field(default=50, description="最大并发请求数")
    max_concurrent_model_calls: int = Field(default=20, description="最大并发模型调用数")
    max_concurrent_tool_calls: int = Field(default=30, description="最大并发工具调用数")

    # ─────────────────────────────────────────────────────────────────────────
    # 摘要生成配置 - 对话历史压缩
    # ─────────────────────────────────────────────────────────────────────────

    # 摘要生成策略：
    # 1. 当对话超过 trigger_turns 时触发摘要
    # 2. 对早期对话（保留 preserve_turns 之前的）生成摘要
    # 3. 用摘要替换早期对话，节省 token
    # 效果：原本 20 轮对话约 5000 tokens，摘要后约 500 tokens

    summary_enabled: bool = Field(default=True, description="是否启用摘要生成")
    summary_trigger_turns: int = Field(default=10, description="摘要触发阈值（对话轮数）")
    summary_turns: int = Field(default=5, description="每次摘要的对话轮数")
    summary_preserve_turns: int = Field(default=3, description="保留的最近轮数（不参与摘要）")
    summary_max_length: int = Field(default=500, description="摘要最大长度（字符）")

    # ─────────────────────────────────────────────────────────────────────────
    # 长时记忆配置 - 跨会话记忆存储
    # ─────────────────────────────────────────────────────────────────────────

    # 长时记忆作用：
    # 1. 存储用户历史对话到向量数据库
    # 2. 新会话时检索相关历史记忆
    # 3. 支持用户画像和偏好学习
    # 技术实现：PostgreSQL pgvector + 语义检索 + 时间衰减

    long_term_memory_enabled: bool = Field(default=True, description="是否启用长时记忆")
    embedding_service_url: str = Field(default="http://localhost:8001", description="Embedding 服务地址")
    memory_retrieve_top_k: int = Field(default=5, description="检索相关记忆数量")
    memory_decay_factor: float = Field(default=0.95, description="记忆时间衰减系数（每天）")
    embedding_dim: int = Field(default=1536, description="向量维度（与 embedding 模型匹配）")

    # ─────────────────────────────────────────────────────────────────────────
    # 配额限制配置 - 防止资源滥用
    # ─────────────────────────────────────────────────────────────────────────

    # 配额设计原则：
    # 1. 租户级限制：防止单个租户占用过多资源
    # 2. 用户级限制：防止单个用户滥用
    # 3. Token 配额：控制 LLM 成本

    quota_tenant_requests_per_minute: int = Field(
        default=100,
        description="租户每分钟请求限制",
    )
    quota_user_requests_per_hour: int = Field(
        default=500,
        description="用户每小时请求限制",
    )
    quota_tenant_tokens_per_day: int = Field(
        default=100000,
        description="租户每日 Token 配额",
    )
    quota_concurrent_requests: int = Field(
        default=10,
        description="租户并发请求数限制",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # OpenTelemetry 采样配置
    # ─────────────────────────────────────────────────────────────────────────

    otel_sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="OTel 采样率（生产环境建议 0.1，开发环境 1.0）",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # gRPC 服务端配置 - Gateway 调用入口
    # ─────────────────────────────────────────────────────────────────────────

    # gRPC 服务端配置
    # Gateway Java 通过 gRPC 调用 Orchestrator，需要启动 gRPC 服务端
    grpc_enabled: bool = Field(default=True, description="是否启用 gRPC 服务端")
    grpc_port: int = Field(default=50051, description="gRPC 服务端口")
    grpc_max_message_size: int = Field(default=16 * 1024 * 1024, description="gRPC 最大消息大小（字节）")
    grpc_keepalive_time_ms: int = Field(default=30000, description="gRPC Keepalive 时间（毫秒）")
    grpc_keepalive_timeout_ms: int = Field(default=10000, description="gRPC Keepalive 超时（毫秒）")

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
