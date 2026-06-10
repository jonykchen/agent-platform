"""Model Gateway 配置 - Pydantic Settings

【核心概念】配置管理的最佳实践
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Model Gateway 作为模型统一入口，配置管理需要解决：
1. 多提供商支持：通义千问、GLM、Kimi、DeepSeek 等国内模型
2. 敏感信息保护：API Key 不能硬编码，必须通过环境变量注入
3. 熔断机制配置：防止单个提供商故障影响整体服务
4. 超时控制：模型调用耗时差异大，需要合理配置

【技术选型】为什么使用 Pydantic Settings？
┌─────────────────────────────────────────────────────────────────────────┐
│  方案              │  优点                    │  缺点                  │
├────────────────────┼──────────────────────────┼────────────────────────┤
│  os.getenv()       │  简单直接                │  无类型检查、无默认值  │
│  python-dotenv     │  支持 .env 文件          │  无类型转换、无验证    │
│  configparser      │  标准 INI 格式           │  不支持环境变量覆盖    │
│  Dynaconf          │  功能丰富                │  依赖重、学习曲线      │
│  ✓ Pydantic Settings│  类型安全+验证+环境变量  │  需要 Pydantic V2      │
└─────────────────────────────────────────────────────────────────────────┘

Pydantic Settings 的优势：
- 自动从环境变量读取（支持嵌套：REDIS__URL → redis.url）
- 类型转换：环境变量 "123" → int 123
- 验证器：@field_validator 支持复杂校验逻辑
- .env 文件支持：开发时使用 .env.local

【安全原则】
- [SECRET] 标记敏感配置，生产环境必须通过环境变量注入
- 默认值使用开发密码，生产环境启动时会校验
- API Key 为空时服务降级，不会硬编码真实密钥

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

from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Model Gateway 应用配置

    【Pydantic Settings 使用要点】

    1. 环境变量映射规则：
       - 环境变量名大写：QWEN_API_KEY → qwen_api_key
       - 嵌套使用双下划线：REDIS__URL → redis.url

    2. 类型转换示例：
       - PORT=8001          → int 8001
       - DEBUG=true         → bool True
       - TIMEOUT_S=30       → int 30

    3. 敏感配置标记：
       - Field(description="[SECRET]") 标记敏感信息
       - 日志输出时自动脱敏
    """

    # ─────────────────────────────────────────────────────────────────────────
    # 环境配置 - 控制应用运行模式
    # ─────────────────────────────────────────────────────────────────────────

    # 运行环境：local（本地开发）/ dev（开发环境）/ test（测试）/ staging（预发）/ prod（生产）
    # 不同环境有不同的日志级别和监控配置
    environment: str = Field(default="local", description="local/dev/test/staging/prod")

    # 调试模式：开启后增加日志详细度，输出完整的请求/响应
    # 生产环境必须为 False
    debug: bool = Field(default=False, description="调试模式，生产环境必须关闭")

    # 服务端口：Model Gateway 默认 8002
    # 与其他服务端口分配：
    # - Gateway (Java): 8080
    # - Orchestrator (Python): 8001
    # - Model Gateway (Python): 8002  ← 本服务
    # - Knowledge (Python): 8003
    # - Tool Bus (Java): 8083
    # - Governance (Java): 8082
    port: int = Field(default=8002, description="HTTP 服务端口")

    # ─────────────────────────────────────────────────────────────────────────
    # Redis 配置 [SECRET] - 缓存和熔断状态存储
    # ─────────────────────────────────────────────────────────────────────────

    # Redis 在 Model Gateway 的用途：
    # 1. 熔断器状态存储：记录各提供商的熔断状态
    # 2. 速率限制计数：防止短时间内大量请求
    # 3. 响应缓存：相同请求的响应缓存（可选）
    redis_url: str = Field(
        default="redis://:dev_password@localhost:6379/1",
        description="[SECRET] Redis 连接 URL",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 模型提供商配置 [SECRET] - 国内主流 LLM
    # ─────────────────────────────────────────────────────────────────────────

    # 技术选型：使用国内模型而非 OpenAI 的原因
    # - 数据合规：部分行业数据不能出境
    # - 成本控制：国内模型价格更低（约为 OpenAI 的 1/10）
    # - 网络稳定：国内 CDN 加速，延迟更低（100-300ms vs 500-2000ms）
    # - 语言适配：中文语境优化更好

    # 通义千问（阿里云）- 主力模型
    # 优势：中文能力强、价格适中、稳定性好
    # 适用场景：通用对话、文本生成、代码辅助
    # 定价：约 ¥0.02/千tokens（2024年）
    qwen_api_key: str = Field(default="", description="[SECRET] 通义千问 API Key")
    qwen_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1",
        description="通义千问 API 端点",
    )

    # 智谱 GLM（清华系）- 备选模型
    # 优势：学术背景强、推理能力好、开源生态完善
    # 适用场景：知识问答、推理任务、代码生成
    glm_api_key: str = Field(default="", description="[SECRET] 智谱 GLM API Key")
    glm_base_url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4",
        description="智谱 GLM API 端点",
    )

    # Moonshot Kimi - 长文本能力强
    # 优势：支持超长上下文（200K tokens）、联网搜索
    # 适用场景：长文档处理、信息检索、网页摘要
    kimi_api_key: str = Field(default="", description="[SECRET] Moonshot Kimi API Key")
    kimi_base_url: str = Field(
        default="https://api.moonshot.cn/v1",
        description="Moonshot Kimi API 端点",
    )

    # DeepSeek - 代码能力强，成本低
    # 优势：代码生成能力强、价格极低、推理能力好
    # 适用场景：代码生成、技术问答、数据分析
    # 定价：约 ¥0.001/千tokens（2024年），性价比最高
    deepseek_api_key: str = Field(default="", description="[SECRET] DeepSeek API Key")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="DeepSeek API 端点",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 熔断配置 - 故障隔离
    # ─────────────────────────────────────────────────────────────────────────

    # 【熔断器工作原理】
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │                         熔断器状态机                                │
    # │                                                                     │
    # │   CLOSED ──(失败次数 ≥ threshold)──► OPEN ──(timeout后)──► HALF_OPEN│
    # │     ▲                               │                      │       │
    # │     │                               │                      │       │
    # │     └──────────(成功)───────────────┘◄────(失败)────────────┘       │
    # │                                                                     │
    # │  CLOSED: 正常状态，请求正常转发                                      │
    # │  OPEN: 熔断状态，直接返回错误，不发送请求                            │
    # │  HALF_OPEN: 探测状态，放行少量请求测试是否恢复                       │
    # └─────────────────────────────────────────────────────────────────────┘

    # 熔断触发阈值：连续失败多少次后触发熔断
    # 推荐值：10 次（平衡敏感度和误触发）
    # - 设置过低（如 3）：网络抖动可能误触发
    # - 设置过高（如 50）：故障发现延迟，影响用户体验
    circuit_breaker_threshold: int = Field(
        default=10,
        description="熔断器触发阈值（连续失败次数）",
    )

    # 熔断恢复超时：熔断状态持续多久后尝试恢复
    # 推荐值：30 秒（给提供商恢复时间）
    # - 设置过短（如 5 秒）：可能过早尝试，浪费请求
    # - 设置过长（如 300 秒）：提供商已恢复但服务仍不可用
    circuit_breaker_timeout_s: int = Field(
        default=30,
        description="熔断器恢复超时（秒）",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 超时配置 - 请求超时控制
    # ─────────────────────────────────────────────────────────────────────────

    # 模型调用超时：单次 LLM API 调用的最大等待时间
    # 推荐值：30 秒
    # - 普通对话：通常 2-10 秒
    # - 长文本生成：可能需要 20-30 秒
    # - 流式响应：首 token 通常 < 5 秒
    # 注意：超时设置过短会导致正常请求被截断，过长会增加用户等待
    request_timeout_s: int = Field(
        default=30,
        description="HTTP 请求超时（秒）",
    )

    # 模型调用超时别名（与 Provider 中 model_call_timeout_s 引用对齐）
    model_call_timeout_s: int = Field(
        default=30,
        description="单次模型调用超时（秒）",
    )

    # 流式调用超时：流式响应允许更长的总时长（首 token 后持续输出）
    stream_timeout_s: int = Field(
        default=120,
        description="流式响应总超时（秒）",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Embedding 配置 - 向量化服务
    # ─────────────────────────────────────────────────────────────────────────

    # 默认 embedding 模型（通义千问 text-embedding-v3）
    # 用于知识库 RAG 与 Orchestrator 长时记忆的向量化
    embedding_model: str = Field(
        default="text-embedding-v3",
        description="默认 embedding 模型名称",
    )

    # 向量维度：text-embedding-v3 默认 1024，需与数据库 vector(dim) 一致
    embedding_dimension: int = Field(
        default=1024,
        description="embedding 向量维度",
    )

    # 单次 embedding 批量上限（DashScope text-embedding-v3 上限为 10）
    embedding_max_batch: int = Field(
        default=10,
        description="单次 embedding 请求的最大文本条数",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 分布式限流配置 - 防止单租户/单 Provider 流量打爆
    # ─────────────────────────────────────────────────────────────────────────

    # 是否启用分布式限流（基于 Redis 滑动窗口）
    rate_limit_enabled: bool = Field(
        default=True,
        description="是否启用分布式限流",
    )

    # 默认每分钟请求数上限（租户未配置专属策略时使用）
    rate_limit_default_rpm: int = Field(
        default=120,
        description="默认每租户每分钟请求数上限（RPM）",
    )

    # 限流窗口（秒）
    rate_limit_window_s: int = Field(
        default=60,
        description="限流滑动窗口大小（秒）",
    )

    # 限流失败时是否放行（fail-open）：Redis 故障时默认放行，避免限流组件自身成为单点
    rate_limit_fail_open: bool = Field(
        default=True,
        description="限流后端故障时是否放行（fail-open）",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 内容安全过滤配置
    # ─────────────────────────────────────────────────────────────────────────

    # 是否启用内容过滤
    content_filter_enabled: bool = Field(
        default=True,
        description="是否启用内容安全过滤",
    )

    # 内容过滤词库文件路径（JSON，格式 {category: [words]}）。为空则使用内置基础词表。
    content_filter_blocklist_path: str = Field(
        default="",
        description="内容过滤词库文件路径（JSON），支持动态加载",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 缓存配置
    # ─────────────────────────────────────────────────────────────────────────

    cache_default_ttl: int = Field(default=600, description="响应缓存 TTL（秒）")
    cache_max_temperature: float = Field(default=0.3, description="可缓存请求的最大 temperature")

    @lru_cache
    def get_config(self) -> AppConfig:
        """获取配置单例

        使用 lru_cache 确保全局只有一个配置实例，
        避免重复解析环境变量和 .env 文件。
        """
        return self


# 全局配置实例
config = AppConfig()
