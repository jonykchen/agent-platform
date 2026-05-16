"""核心模块 - 应用基础设施层

【模块架构】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    ┌─────────────────────────────────┐
                    │           API Layer              │
                    │   (FastAPI Endpoints, Routes)   │
                    └─────────────────┬───────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CORE MODULE                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   config     │  │  exceptions  │  │   logging    │  │   tracing    │     │
│  │   配置管理    │  │   异常体系    │  │   日志系统    │  │   链路追踪    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ prompt_guard │  │ output_guard │  │sensitive_   │  │  resilience  │     │
│  │   提示词防护  │  │   输出防护    │  │  filter      │  │   熔断重试    │     │
│  │  (S-AGENT-01)│  │  (S-AGENT-05)│  │   日志脱敏    │  │   容错机制    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │token_counter │  │   context_   │  │    cache     │  │   shutdown   │     │
│  │  Token 计数  │  │   manager    │  │   多级缓存    │  │   优雅停机    │     │
│  │              │  │  上下文截断  │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                       │
│  │quota_manager │  │health_       │  │ step_buffer  │                       │
│  │  配额管理    │  │  checker     │  │   步骤缓冲    │                       │
│  │              │  │   健康检查    │  │              │                       │
│  └──────────────┘  └──────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │        External Services         │
                    │   (Database, Redis, Model API)  │
                    └─────────────────────────────────┘

【子模块职责】
┌────────────────────┬──────────────────────────────────────────────────────────────┐
│ 子模块              │ 职责描述                                                      │
├────────────────────┼──────────────────────────────────────────────────────────────┤
│ config             │ Pydantic Settings 配置管理，支持环境变量、.env 文件            │
│ constants          │ 全局常量定义，包括错误码、默认值、超时配置                      │
│ exceptions         │ 统一异常体系，错误码分类：10xxx(通用) 20xxx(Agent) 30xxx(Model) │
│ logging            │ JSON 结构化日志，自动脱敏，request_id 关联                     │
│ tracing            │ OpenTelemetry 分布式追踪配置                                   │
│ prompt_guard       │ Prompt 注入防护（S-AGENT-01），检测恶意指令                    │
│ output_guard       │ 输出泄露防护（S-AGENT-05），阻断敏感信息输出                    │
│ sensitive_filter   │ 日志敏感信息脱敏：手机号、身份证、API Key                      │
│ resilience         │ 熔断器 + 重试策略，保护下游服务                                │
│ token_counter      │ Token 精确计数，支持 tiktoken 和估算                          │
│ context_manager    │ 上下文截断策略，滑动窗口防止 token 超限                        │
│ cache              │ 多级缓存：L1 本地内存 + L2 Redis                              │
│ shutdown           │ 优雅停机，处理进行中的请求                                      │
│ quota_manager      │ 租户配额管理，频率限制                                          │
│ health_checker     │ 依赖服务健康检查，K8s Readiness/Liveness 探针                  │
│ step_buffer        │ 步骤结果缓冲，支持流式响应                                      │
│ metrics            │ Prometheus 指标采集                                            │
│ feature_flags      │ 功能开关管理                                                   │
└────────────────────┴──────────────────────────────────────────────────────────────┘

【核心组件】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. config - 配置单例
   - 使用 Pydantic Settings 实现 12-Factor App 配置原则
   - 支持环境变量覆盖，生产环境强制校验（如 JWT 密钥长度）

2. exceptions - 异常体系
   - BasePlatformException 为所有业务异常基类
   - 双消息机制：message（技术）+ user_message（用户友好）
   - 跨服务错误码对齐（与 Java 服务共享 proto 定义）

3. resilience - 容错机制
   - 熔断器：CircuitBreaker（失败阈值 + 恢复超时）
   - 重试策略：指数退避 + 抖动（防止重试风暴）
   - 线程安全：asyncio.Lock 保护状态转换

4. prompt_guard / output_guard - 安全防护
   - Prompt 注入检测（角色劫持、指令注入）
   - 输出敏感信息检测（API Key、内部 IP）

【使用示例】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
# 获取配置
from app.core import config

print(config.environment)      # "local"
print(config.model_gateway_url)  # "http://localhost:8002"

# 使用日志
from app.core import get_logger, setup_logging

setup_logging()  # 应用启动时调用
logger = get_logger(__name__)
logger.info("request_received", request_id="req_abc", user_id="user_123")

# 抛出异常
from app.core.exceptions import InvalidRequestError, MaxStepsExceededError

raise InvalidRequestError("订单号格式错误", details={"order_id": "xxx"})
raise MaxStepsExceededError(max_steps=10)

# 使用熔断器
from app.core.resilience import tool_bus_circuit

if tool_bus_circuit.is_open:
    raise ServiceUnavailableError("tool-bus")

# 使用上下文管理器（防止 token 超限）
from app.core.context_manager import context_manager

truncated_messages = context_manager.truncate_messages(
    messages=messages,
    max_tokens=128000,
    reserved_tokens=8000
)

# 敏感信息脱敏
from app.core.sensitive_filter import sensitive_filter

safe_text = sensitive_filter.filter("用户手机号: 13800138000")
# 输出: "用户手机号: 138****8000"

# 优雅停机
from app.core import init_shutdown_manager, setup_signal_handlers

init_shutdown_manager()
setup_signal_handlers()  # 注册 SIGTERM/SIGINT 处理
```

【安全红线】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- [G-SEC-01] 禁止硬编码密钥/密码，所有敏感配置使用 [SECRET] 标记
- [G-SEC-02] 敏感信息必须脱敏后才能写入日志
- [G-SEC-03] 审计数据不可删改，audit_event 表有触发器保护
- [S-AGENT-01] 用户输入必须经过 prompt_guard 检测
- [S-AGENT-05] 模型输出必须经过 output_guard 检测

【参考】
- 配置管理最佳实践: https://12factor.net/config
- Pydantic Settings 文档: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- 熔断器模式: https://martinfowler.com/bliki/CircuitBreaker.html
"""

from app.core.config import config
from app.core.constants import *
from app.core.exceptions import *
from app.core.logging import get_logger, setup_logging
from app.core.prompt_guard import PromptInjectionError, prompt_guard
from app.core.shutdown import (
    GracefulShutdown,
    get_shutdown_manager,
    init_shutdown_manager,
    setup_signal_handlers,
)

__all__ = [
    "config",
    "setup_logging",
    "get_logger",
    "prompt_guard",
    "PromptInjectionError",
    "GracefulShutdown",
    "get_shutdown_manager",
    "init_shutdown_manager",
    "setup_signal_handlers",
]
