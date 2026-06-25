"""Model Gateway Service 主入口

【核心概念】Model Gateway 在整体架构中的位置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Model Gateway 是 Agent 平台的模型统一网关，位于架构的中间层：

┌─────────────────────────────────────────────────────────────────────────────┐
│                            请求流向（从上到下）                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    Gateway (Java)          API 入口，鉴权、限流、路由                       │
│           │                                                                 │
│           ▼                                                                 │
│    Orchestrator (Python)   Agent 编排，LangGraph 状态机                     │
│           │                                                                 │
│           ▼                                                                 │
│  ┌────────────────────┐                                                     │
│  │  Model Gateway ★   │  ← 当前服务：模型统一网关                           │
│  └────────────────────┘                                                     │
│           │                                                                 │
│           ▼                                                                 │
│    ┌──────────────────────────────────────────────────────┐                 │
│    │                  LLM Providers                        │                │
│    │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │                │
│    │  │  Qwen   │  │  GLM    │  │ Moonshot│  │  DeepSeek│  │                │
│    │  │ (阿里)  │  │ (智谱)  │  │ (月之暗面)│ │ (深度求索)│  │                │
│    │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │                │
│    └──────────────────────────────────────────────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

【核心职责】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Model Gateway 承担以下职责：

┌─────────────────────────────────────────────────────────────────────────────┐
│  职责              │  说明                                                 │
├────────────────────┼───────────────────────────────────────────────────────┤
│  统一接口          │  提供 OpenAI 兼容的 API，屏蔽底层差异                  │
│  模型路由          │  智能选择最优模型，支持 Fallback 机制                   │
│  熔断保护          │  防止级联故障，自动隔离故障节点                        │
│  租户隔离          │  支持租户级路由策略（主模型、备用模型、预算）            │
│  成本控制          │  Token 计费、预算限制、成本统计                        │
│  可观测性          │  延迟监控、成功率、成本分析                            │
└────────────────────┴───────────────────────────────────────────────────────┘

【设计原则】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. OpenAI 兼容：请求/响应格式与 OpenAI API 一致，方便集成
2. 高可用：主备 Fallback 机制，自动切换故障节点
3. 多租户：租户级策略配置，支持个性化需求
4. 可扩展：Provider 抽象，新模型接入只需实现接口

【技术选型】对比分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│  框架        │  优点                      │  缺点                    │
├──────────────┼────────────────────────────┼──────────────────────────┤
│  Flask       │  成熟稳定、生态丰富         │  同步阻塞、不支持 async  │
│              │  学习曲线平缓              │  无自动文档生成          │
├──────────────┼────────────────────────────┼──────────────────────────┤
│  Django      │  全功能框架、Admin 后台     │  过于重型、学习曲线陡峭  │
│              │  ORM 强大                  │  异步支持有限            │
├──────────────┼────────────────────────────┼──────────────────────────┤
│  ✓ FastAPI   │  原生异步、高性能          │  相对年轻（生态较小）    │
│              │  自动文档（Swagger/ReDoc） │  部分插件不如 Flask 成熟 │
│              │  类型提示 + Pydantic       │                          │
│              │  性能接近 Go/Java          │                          │
├──────────────┼────────────────────────────┼──────────────────────────┤
│  Starlette   │  轻量异步、FastAPI 底层     │  功能较少、需手动配置    │
│              │  性能最优                  │  无自动文档              │
└──────────────┴────────────────────────────┴──────────────────────────┘

【选择 FastAPI 的原因】
1. 异步原生：与 httpx、Redis async 完美配合
2. 自动文档：开发调试效率提升
3. 类型安全：Pydantic 模型验证，IDE 友好
4. 性能优秀：实测 QPS 接近 Go/Java 水平

【生命周期管理】lifespan vs on_event
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│  方式              │  示例                              │  推荐度           │
├────────────────────┼────────────────────────────────────┼──────────────────┤
│  @app.on_event     │  @app.on_event("startup")          │  ⚠ 已废弃        │
│                    │  async def startup(): ...          │                  │
│                    │                                    │                  │
│                    │  缺点：                            │                  │
│                    │  - 无法获取 app 实例               │                  │
│                    │  - 不支持依赖注入                  │                  │
│                    │  - 测试时难以 mock                 │                  │
├────────────────────┼────────────────────────────────────┼──────────────────┤
│  ✓ lifespan        │  @asynccontextmanager              │  ✅ 推荐         │
│                    │  async def lifespan(app):          │                  │
│                    │      # startup                     │                  │
│                    │      yield                         │                  │
│                    │      # shutdown                    │                  │
│                    │                                    │                  │
│                    │  优点：                            │                  │
│                    │  - 可访问 app 实例                  │                  │
│                    │  - 资源管理清晰（上下文管理器）     │                  │
│                    │  - 测试友好                        │                  │
│                    │  - 官方推荐                        │                  │
└────────────────────┴────────────────────────────────────┴──────────────────┘

【参考】
- FastAPI 生命周期: https://fastapi.tiangolo.com/advanced/events/
- ASGI 规范: https://asgi.readthedocs.io/
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api.v1 import chat, embeddings, models
from app.core.config import config
from app.core.logging import setup_logging
from app.core.rate_limiter import init_rate_limiter
from app.core.redis_client import close_redis, set_redis
from app.router.model_router import get_model_router

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════════════════
# 全局组件 - 生命周期管理
# ═══════════════════════════════════════════════════════════════════════════

# 使用模块级变量而非类单例的原因：
# - 简单直接，无需引入额外依赖
# - 测试时可直接替换模块变量
# - FastAPI lifespan 天然支持这种模式
#
# 全局组件列表：
# - redis_client: Redis 连接，用于缓存和租户策略存储
#
# 注意：Provider 不在此注册，由 ModelRouter 管理

redis_client: Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    【ASGI 生命周期事件】
    使用 async context manager 管理资源：
    - yield 前：startup 事件，初始化资源
    - yield 后：shutdown 事件，释放资源

    【启动流程】初始化顺序很重要
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ┌─────────────────────────────────────────────────────────────────────┐
    │                        Startup 流程                                  │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │  Step 1: 日志系统初始化                                              │
    │           │                                                         │
    │           │  设置 structlog，配置 JSON 格式输出                      │
    │           │  后续日志才能正常记录                                    │
    │           │                                                         │
    │           ▼                                                         │
    │  Step 2: Redis 连接初始化                                           │
    │           │                                                         │
    │           │  用于：缓存、租户策略、熔断器状态                         │
    │           │  连接池配置：max_connections=100                         │
    │           │                                                         │
    │           ▼                                                         │
    │  Step 3: Provider 注册                                              │
    │           │                                                         │
    │           ├──────────────────────────────────────────────────────┐  │
    │           │  注册 Qwen Provider (主力模型)                        │  │
    │           │  - 条件：config.qwen_api_key 存在                    │  │
    │           │  - 模型：qwen-max, qwen-plus, qwen-turbo, qwen-long  │  │
    │           │  - 创建熔断器：failure_threshold=10, timeout=30s     │  │
    │           └──────────────────────────────────────────────────────┘  │
    │           │                                                         │
    │           ├──────────────────────────────────────────────────────┐  │
    │           │  预留其他 Provider 注册位                             │  │
    │           │  - GLM (智谱)、Moonshot (月之暗面)、DeepSeek (深度求索) │
    │           │  - 实现方式：from app.providers.xxx import XXXProvider │
    │           └──────────────────────────────────────────────────────┘  │
    │           │                                                         │
    │           ▼                                                         │
    │  Step 4: 健康检查就绪                                               │
    │           │                                                         │
    │           │  Model Router 汇总可用模型列表                           │
    │           │  日志输出：providers=[{name, available, supported}]     │
    │           │                                                         │
    │           ▼                                                         │
    │        ┌─────────────┐                                              │
    │        │  yield      │  ← 应用进入运行态，处理请求                   │
    │        └─────────────┘                                              │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

    【关闭流程】资源释放顺序（与初始化相反）
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ┌─────────────────────────────────────────────────────────────────────┐
    │                        Shutdown 流程                                 │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │  Step 1: 停止接收新请求                                             │
    │           │  （ASGI 服务器处理）                                     │
    │           │                                                         │
    │           ▼                                                         │
    │  Step 2: 等待进行中的请求完成                                        │
    │           │  （优雅关闭超时由 ASGI 服务器配置）                       │
    │           │                                                         │
    │           ▼                                                         │
    │  Step 3: 关闭 Redis 连接                                            │
    │           │                                                         │
    │           │  await redis_client.close()                             │
    │           │  - 释放连接池资源                                        │
    │           │  - 等待进行中的命令完成                                   │
    │           │                                                         │
    │           ▼                                                         │
    │  Step 4: Provider 资源释放                                          │
    │           │                                                         │
    │           │  （当前实现：无显式释放，由 GC 回收                       │
    │           │   未来可添加：httpx.AsyncClient.aclose()）               │
    │           │                                                         │
    │           ▼                                                         │
    │        ┌─────────────┐                                              │
    │        │  结束       │                                              │
    │        └─────────────┘                                              │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

    【注意事项】
    - Redis 连接必须在所有 Provider 之前初始化（租户策略依赖）
    - 熔断器状态存储在内存中，重启后重置
    - 关闭顺序必须与初始化顺序相反，避免依赖问题
    """
    global redis_client

    # ═════════════════════════════════════════════════════════════════════════
    # Startup: 初始化资源
    # ═════════════════════════════════════════════════════════════════════════

    # ─────────────────────────────────────────────────────────────────────
    # 1. 日志初始化（必须最先）
    # ─────────────────────────────────────────────────────────────────────
    # 设置 structlog：
    # - 开发环境：控制台彩色输出
    # - 生产环境：JSON 格式（便于 ELK 收集）
    setup_logging(config.environment, config.debug)

    logger.info(
        "Model Gateway starting",
        environment=config.environment,
        version="1.0.0",
    )

    # ─────────────────────────────────────────────────────────────────────
    # 2. Redis 连接初始化
    # ─────────────────────────────────────────────────────────────────────
    # 用途：
    # - 租户路由策略存储：key=model_policy:{tenant_id}
    # - 响应缓存：key=model_cache:{request_hash}
    # - 熔断器状态持久化（可选）
    #
    # 连接池配置（在 config.redis_url 中指定）：
    # - max_connections: 100
    # - socket_timeout: 5s
    # - socket_connect_timeout: 5s
    redis_client = Redis.from_url(config.redis_url)
    # 注册为全局单例：model_router 租户策略加载、response_cache 等组件统一复用
    # 此连接池，避免各处 Redis.from_url 反复建连导致连接泄漏。
    set_redis(redis_client)
    logger.info("Redis connected", url=config.redis_url.split("@")[-1])  # 脱敏

    # 初始化分布式限流器（共用同一 Redis 连接）
    if getattr(config, "rate_limit_enabled", True):
        init_rate_limiter(redis_client)
        logger.info(
            "Rate limiter initialized",
            default_rpm=getattr(config, "rate_limit_default_rpm", 120),
            window_s=getattr(config, "rate_limit_window_s", 60),
        )

    # ─────────────────────────────────────────────────────────────────────
    # 3. Provider 注册
    # ─────────────────────────────────────────────────────────────────────
    # ModelRouter 是全局单例，管理所有 Provider 和熔断器
    model_router = get_model_router()

    # ─────────────────────────────────────────────────────────────────────
    # 3.1 注册 Qwen 提供商（主力模型）
    # ─────────────────────────────────────────────────────────────────────
    # Qwen 是阿里的通义千问系列，本项目的主力模型：
    # - qwen-max: 最强能力，32K 上下文
    # - qwen-plus: 性价比高，32K 上下文
    # - qwen-turbo: 速度最快，8K 上下文
    # - qwen-long: 长文本处理，1M 上下文
    #
    # 注册时会自动创建熔断器：
    # - failure_threshold: 10 次连续失败后熔断
    # - timeout_seconds: 30 秒后尝试恢复
    if config.qwen_api_key:
        from app.providers.qwen import QwenProvider

        qwen_provider = QwenProvider(
            api_key=config.qwen_api_key,
            base_url=config.qwen_base_url,
        )
        model_router.register_provider("qwen", qwen_provider)
        logger.info(
            "Qwen provider registered",
            models=qwen_provider.supported_models,
            base_url=config.qwen_base_url,
        )
    else:
        logger.warning(
            "Qwen provider skipped",
            reason="QWEN_API_KEY not configured",
        )

    # ─────────────────────────────────────────────────────────────────────
    # 3.2 注册其他提供商（多 Provider 故障转移）
    # ─────────────────────────────────────────────────────────────────────
    # 各 Provider 仅在配置了对应 API Key 时注册（密钥走环境变量，禁止硬编码）。
    # 注册多个 Provider 后，ModelRouter 可在某 Provider 熔断/不可用时自动
    # 故障转移到备用 Provider，避免单点导致 AllProvidersDownError。
    if config.deepseek_api_key:
        from app.providers.deepseek import DeepSeekProvider

        deepseek_provider = DeepSeekProvider(
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
        )
        model_router.register_provider("deepseek", deepseek_provider)
        logger.info(
            "DeepSeek provider registered",
            models=deepseek_provider.supported_models,
            base_url=config.deepseek_base_url,
        )
    else:
        logger.warning("DeepSeek provider skipped", reason="DEEPSEEK_API_KEY not configured")

    if config.glm_api_key:
        from app.providers.glm import GLMProvider

        glm_provider = GLMProvider(
            api_key=config.glm_api_key,
            base_url=config.glm_base_url,
        )
        model_router.register_provider("glm", glm_provider)
        logger.info(
            "GLM provider registered",
            models=glm_provider.supported_models,
            base_url=config.glm_base_url,
        )
    else:
        logger.warning("GLM provider skipped", reason="GLM_API_KEY not configured")

    # ─────────────────────────────────────────────────────────────────────
    # 4. 启动完成
    # ─────────────────────────────────────────────────────────────────────
    logger.info(
        "Model Gateway initialized",
        providers=model_router.list_available_models(),
        default_policy=model_router._default_policy,
    )

    # ─────────────────────────────────────────────────────────────────────
    # Runtime: 处理请求
    # ─────────────────────────────────────────────────────────────────────
    yield

    # ═════════════════════════════════════════════════════════════════════════
    # Shutdown: 释放资源
    # ═════════════════════════════════════════════════════════════════════════

    # ─────────────────────────────────────────────────────────────────────
    # 1. 关闭 Redis 连接
    # ─────────────────────────────────────────────────────────────────────
    # Redis.close() 会：
    # - 释放连接池中的所有连接
    # - 等待进行中的命令完成（最多 5s）
    # - 不会断开正在使用的连接（由 ASGI 服务器处理）
    # 通过全局单例统一关闭（与 set_redis 注册的实例一致），释放连接池
    await close_redis()
    redis_client = None
    logger.info("Redis connection closed")

    # ─────────────────────────────────────────────────────────────────────
    # 2. Provider 资源释放
    # ─────────────────────────────────────────────────────────────────────
    # 当前实现：无显式释放
    # - httpx.AsyncClient 在 Provider 中是局部变量，请求结束后自动释放
    # - 熔断器状态是内存数据，重启后重置
    #
    # 未来优化：如果 Provider 使用共享的 httpx.AsyncClient，需要显式关闭
    # for provider in model_router._providers.values():
    #     if hasattr(provider, 'close'):
    #         await provider.close()

    logger.info("Model Gateway shutting down")


def create_app() -> FastAPI:
    """创建 FastAPI 应用

    【工厂函数模式】
    使用工厂函数而非全局 app 对象的原因：
    - 测试时可以创建多个独立实例
    - 支持多环境配置（dev/test/prod 不同 app）
    - 延迟初始化，避免导入时副作用

    【中间件顺序】重要！执行顺序从下到上
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  请求流 → CORS → 路由处理器                                             │
    │                                                                         │
    │  Model Gateway 中间件较少，未来可扩展：                                   │
    │  - RateLimitMiddleware: 速率限制（推荐添加）                             │
    │  - AuthenticationMiddleware: API Key 验证（推荐添加）                   │
    │  - TracingMiddleware: 分布式追踪（可选）                                 │
    │  - MetricsMiddleware: Prometheus 指标（可选）                           │
    └─────────────────────────────────────────────────────────────────────────┘

    【CORS 配置说明】
    当前配置允许所有来源（allow_origins=["*"]），适用于：
    - 开发环境
    - 内部服务（不对外暴露）

    生产环境应该改为具体域名列表：
    allow_origins=[
        "https://app.example.com",
        "https://admin.example.com",
    ]

    Returns:
        配置好的 FastAPI 应用实例
    """
    app = FastAPI(
        title="Model Gateway",
        description="模型统一网关服务 - OpenAI 兼容接口",
        version="1.0.0",
        lifespan=lifespan,  # 使用新的生命周期管理方式
        docs_url="/docs",  # Swagger UI
        redoc_url="/redoc",  # ReDoc
    )

    # ─────────────────────────────────────────────────────────────────────
    # 中间件注册（注意顺序！后添加的先执行）
    # ─────────────────────────────────────────────────────────────────────

    # CORS 中间件 - 处理跨域请求
    # 注意：allow_origins=["*"] + allow_credentials=True 是不安全配置
    # 生产环境应通过 CORS_ALLOWED_ORIGINS 环境变量指定具体域名
    from app.core.config import config as app_config

    cors_origins = app_config.cors_allowed_origins
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o.strip() for o in cors_origins.split(",")],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # 未配置 CORS 域名时，允许所有来源但不发送凭证（安全降级）
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ─────────────────────────────────────────────────────────────────────
    # 路由注册
    # ─────────────────────────────────────────────────────────────────────

    # OpenAI 兼容的 Models API
    # GET /v1/models - 列出可用模型
    # GET /v1/models/{model} - 获取模型详情
    app.include_router(models.router, prefix="/v1", tags=["models"])

    # OpenAI 兼容的 Chat Completions API
    # POST /v1/chat/completions - 对话补全
    app.include_router(chat.router, prefix="/v1", tags=["chat"])

    # OpenAI 兼容的 Embeddings API
    # POST /v1/embeddings - 文本向量化（供 Knowledge RAG / 长时记忆调用）
    app.include_router(embeddings.router, prefix="/v1", tags=["embeddings"])

    # Prometheus 指标端点
    @app.get("/metrics", tags=["observability"])
    async def metrics():
        """暴露 Prometheus 指标供抓取。"""
        from fastapi import Response
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # 健康检查端点（容器 healthcheck + K8s liveness/readiness 探针）
    @app.get("/health", tags=["health"])
    async def health():
        """存活探针：进程可响应即健康"""
        return {"status": "ok", "service": "model-gateway"}

    @app.get("/ready", tags=["health"])
    async def ready():
        """就绪探针：至少注册了一个可用 Provider 才就绪"""
        router = get_model_router()
        provider_count = len(getattr(router, "_providers", {}))
        if provider_count == 0:
            from fastapi import Response

            return Response(
                content='{"status":"not_ready","reason":"no_providers"}',
                media_type="application/json",
                status_code=503,
            )
        return {"status": "ready", "providers": provider_count}

    return app


# ═══════════════════════════════════════════════════════════════════════════
# 应用实例 - 模块导入时创建
# ═══════════════════════════════════════════════════════════════════════════

# 使用 uvicorn 启动：
#   uvicorn app.main:app --host 0.0.0.0 --port 8002
#
# 开发模式（自动重载）：
#   uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
#
# 生产模式（多 worker）：
#   uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 4
app = create_app()
