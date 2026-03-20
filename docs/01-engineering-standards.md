# 工程规范 — 代码结构与工程标准

> **版本**：v2.0 | **状态**：✅ 完成 | **对应审查项**：C-01, C-02, C-03, M-01, M-02(部分)

---

## 1. Monorepo 工程基础设施（C-03 补充）

### 1.1 根目录必须文件

```
agent-platform/
├── Makefile                  # ← 统一构建/测试/检查入口
├── .editorconfig             # ← 跨语言代码风格统一
├── .gitignore                # ← Git 忽略规则
├── buf.yaml                   # ← Buf Proto 管理
├── buf.gen.yaml               # ← Proto 多语言代码生成
├── .python-version            # ← Python 版本锁定 (3.12)
├── .java-version              # ← Java 版本锁定 (21)
├── tools/
│   └── .tool-versions         # ← asdf/mise 开发工具版本锁定
├── docs/                      # 文档（本目录）
├── contracts/                 # 契约文件
├── services/                  # 各服务
├── shared/                    # 共享资产
├── infra/                     # IaC
└── scripts/                   # 运维脚本
```

### 1.2 Makefile 统一入口

```makefile
# ============================================================
#  Agent Platform — Monorepo Build System
#  用法: make <target>
# ============================================================

.PHONY: help build test lint proto fmt dev clean docker

# 默认显示帮助
help:
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:' $(MAKEFILE_LIST) | sort | awk -F':' '{printf "  %-20s %s\n", $$1, $$2}'

# ---- 构建 ----
build: build-java build-python
	@echo "✅ All services built"

build-java:
	cd services/gateway-java && ./mvnw package -DskipTests -q
	cd services/tool-bus-java && ./mvnw package -DskipTests -q
	cd services/risk-java && ./mvnw package -DskipTests -q
	cd services/approval-java && ./mvnw package -DskipTests -q

build-python:
	cd services/orchestrator-python && uv sync --quiet && uv build
	cd services/model-gateway-python && uv sync --quiet && uv build
	cd services/knowledge-python && uv sync --quiet && uv build

# ---- 测试 ----
test: test-java test-python
	@echo "✅ All tests passed"

test-java:
	cd services/gateway-java && ./mvnw test -q
	cd services/tool-bus-java && ./mvnw test -q

test-python:
	cd services/orchestrator-python && uv run pytest tests/ -v --tb=short
	cd services/model-gateway-python && uv run pytest tests/ -v --tb=short

# ---- 代码质量 ----
lint: lint-java lint-python lint-proto
	@echo "✅ Lint passed"

lint-java:
	cd services/gateway-java && ./mvnw checkstyle:check -q
	cd services/tool-bus-java && ./mvnw checkstyle:check -q

lint-python:
	cd services/orchestrator-python && uv run ruff check .
	cd services/orchestrator-python && uv run ruff format --check .
	cd services/model-gateway-python && uv run ruff check .

lint-proto:
	buf lint contracts/proto
	buf breaking --against 'main' contracts/proto

# ---- Proto 生成 ----
proto:
	buf generate
	@echo "✅ Proto code generated"

# ---- 格式化 ----
fmt: fmt-java fmt-python
	@echo "✅ Code formatted"

fmt-java:
	cd services/gateway-java && ./mvnw spotless:apply -q

fmt-python:
	cd services/orchestrator-python && uv run ruff format .
	cd services/model-gateway-python && uv run ruff format .

# ---- 开发环境 ----
dev:
	docker compose -f infra/docker-compose.yml up -d
	@echo "🚀 Dev environment started"

# ---- 清理 ----
clean: clean-java clean-python
	@echo "🧹 Cleaned"

clean-java:
	find . -name target -type d -exec rm -rf {} + 2>/dev/null || true

clean-python:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name .pytest_cache -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name *.egg-info -type d -exec rm -rf {} + 2>/dev/null || true

# ---- Docker ----
docker: docker-build docker-push

docker-build:
	docker build -t agent-platform/gateway:latest -f services/gateway-java/Dockerfile services/gateway-java/
	docker build -t agent-platform/orchestrator:latest -f services/orchestrator-python/Dockerfile services/orchestrator-python/
	docker build -t agent-platform/model-gateway:latest -f services/model-gateway-python/Dockerfile services/model-gateway-python/

# ---- Full check (CI 使用) ----
ci: lint test proto security-scan
	@echo "✅ CI checks passed"

security-scan:
	@echo "Running security scans..."
	gitleaks detect --source . --verbose || true
```

### 1.3 EditorConfig

```ini
# .editorconfig
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 4

[*.py]
indent_size = 4
max_line_length = 120

[*.{java,kt}]
indent_size = 4
max_line_length = 120

[*.{yml,yaml,json}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false
max_line_length = 200

[Makefile]
indent_style = tab
```

### 1.4 Proto 代码生成配置

```yaml
# buf.gen.yaml
version: v1
managed:
  enabled: true
  override:
    - file_option: java_outer_classname
      value: false
plugins:
  # Java gRPC + Protobuf
  - name: java
    out: services/gateway-java/src/main/java/gen
    opt:
      - source_relative
  - name: grpc-java
    out: services/gateway-java/src/main/java/gen
    opt:
      - source_relative
  - name: java
    out: services/tool-bus-java/src/main/java/gen
    opt:
      - source_relative
  - name: grpc-java
    out: services/tool-bus-java/src/main/java/gen
    opt:
      - source_relative
  # Python gRPC + Protobuf
  - name: python
    out: services/orchestrator-python/app/gen
    opt:
      - source_relative
  - name: grpc-python
    out: services/orchestrator-python/app/gen
    opt:
      - source_relative
  # OpenAPI (用于 REST 接口文档)
  - name: openapiv2
    out: contracts/openapi/gen
```

```yaml
# buf.yaml
version: v1
breaking:
  use:
    - FILE
lint:
  use:
    - DEFAULT
  except:
    - PACKAGE_VERSION_SUFFIX
```

### 1.5 工具版本锁定

```
# tools/.tool-versions
python 3.12.0
java 21.0.2
node 20.11.0
buf 1.33.0
golangci-lint 1.56.0
```

---

## 2. 服务内部代码分层（C-01 / C-02 补充）

### 2.1 Orchestrator Python 完整包结构

```
services/orchestrator-python/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI 应用入口
│   │
│   ├── api/                             # === 路由层 ===
│   │   ├── __init__.py
│   │   ├── deps.py                      # 依赖注入 (request_id, tenant, user context)
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py                  # POST /api/v1/chat/completions
│   │   │   ├── agent.py                 # POST /api/v1/agents/{id}/runs
│   │   │   ├── session.py               # GET /api/v1/sessions/{id}
│   │   │   └── health.py                # GET /health
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── otel_middleware.py       # OpenTelemetry 追踪中间件
│   │       ├── request_context.py       # request_id / tenant_id 注入
│   │       ├── error_handler.py         # 统一异常处理中间件
│   │       └── rate_limiter.py          # 限流中间件
│   │
│   ├── core/                            # === 核心配置层 ===
│   │   ├── __init__.py
│   │   ├── config.py                    # Pydantic Settings (环境变量→配置对象)
│   │   ├── exceptions.py               # ← 新增：统一异常体系
│   │   └── constants.py                # ← 新增：MAX_STEPS/TIMEOUT等常量
│   │
│   ├── graph/                           # === LangGraph 状态机层 ===
│   │   ├── __init__.py
│   │   ├── state.py                     # TypedDict State 定义
│   │   ├── router.py                   # 条件路由逻辑 (edge routing)
│   │   ├── builder.py                  # Graph 构建器 (compile)
│   │   └── nodes/                      # ← 新增：每个节点一个文件
│   │       ├── __init__.py
│   │       ├── intent_classifier.py     # 意图分类节点
│   │       ├── thinker.py               # 思考/推理节点
│   │       ├── tool_caller.py           # 工具调用节点
│   │       ├── tool_validator.py        # 工具结果校验节点
│   │       ├── rag_retriever.py         # RAG 检索节点
│   │       ├── risk_checker.py          # 风险评估节点
│   │       ├── answer_synthesizer.py    # 最终答案合成节点
│   │       └── approval_waiter.py       # 审批等待节点
│   │
│   ├── memory/                          # === 记忆管理层 ===
│   │   ├── __init__.py
│   │   ├── conversation.py             # 对话记忆 (滑动窗口+摘要)
│   │   ├── long_term.py                # 长期记忆 (偏好/实体)
│   │   └── checkpoint_store.py         # LangGraph Checkpoint (Redis-backed)
│   │
│   ├── tools/                           # === 工具客户端层 ===
│   │   ├── __init__.py
│   │   ├── base.py                     # ← 新增：Tool Protocol/ABC
│   │   ├── registry.py                 # ← 新增：工具注册表
│   │   ├── schemas.py                  # 工具入参/出参 Pydantic Schema
│   │   └── clients/                    # gRPC clients to Tool Bus
│   │       ├── __init__.py
│   │       ├── tool_bus_client.py      # Tool Bus gRPC Client
│   │       └── interceptors.py         # gRPC 认证/追踪拦截器
│   │
│   ├── prompts/                         # === Prompt 模板层 ===
│   │   ├── __init__.py
│   │   ├── system/                     # System Prompt 模板
│   │   │   ├── default_system.txt
│   │   │   ├── react_system.txt
│   │   │   └── plan_execute_system.txt
│   │   ├── few_shot/                   # Few-shot 示例
│   │   └── loader.py                   # 模板加载器 (版本化)
│   │
│   ├── schemas/                         # ← 新增：请求/响应 Pydantic 模型
│   │   ├── __init__.py
│   │   ├── chat.py                     # ChatRequest / ChatResponse
│   │   ├── agent.py                    # AgentRunRequest / AgentRunResponse
│   │   ├── tool.py                     # ToolCallRequest / ToolCallResult
│   │   └── session.py                  # SessionCreate / SessionInfo
│   │
│   └── utils/                           # 工具函数
│       ├── __init__.py
│       ├── token_counter.py            # Token 计数
│       ├── hash_utils.py               # Hash 工具
│       └── time_utils.py               # 时间工具
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # pytest fixtures
│   ├── unit/
│   │   ├── test_graph_nodes.py
│   │   ├── test_tools.py
│   │   ├── test_memory.py
│   │   └── test_prompts.py
│   ├── integration/
│   │   ├── test_chat_flow.py
│   │   └── test_tool_calling.py
│   └── e2e/
│       └── test_full_agent_run.py
│
├── pyproject.toml                      # 项目配置(uv/pip/ruff/pytest/mypy)
├── Dockerfile
└── requirements.txt                    # (deprecated, 用 pyproject.toml 管理)
```

#### core/exceptions.py — 统一异常体系（新增）

```python
# orchestrator-python/app/core/exceptions.py
"""统一的异常类体系。

所有业务异常必须继承自基类，确保错误码和消息格式一致。
跨服务的错误码定义见 contracts/proto/common/error_code.proto。
"""

from typing import Any, Optional


class BasePlatformException(Exception):
    """平台基础异常。"""

    def __init__(
        self,
        message: str,
        code: str = "ERR_UNKNOWN",
        user_message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.user_message = user_message or message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "user_message": self.user_message,
            "details": self.details,
        }


# ====== 通用错误 (10xxx) ======

class InvalidRequestError(BasePlatformException):
    def __init__(self, message: str, details=None):
        super().__init__(message, code="ERR_INVALID_REQUEST",
                         user_message="请求参数有误", details=details)


class UnauthorizedError(BasePlatformException):
    def __init__(self, message: str = "未授权"):
        super().__init__(message, code="ERR_UNAUTHORIZED",
                         user_message="请先登录")


class RateLimitedError(BasePlatformException):
    def __init__(self, retry_after: int = 60):
        super().__init__("请求过于频繁", code="ERR_RATE_LIMITED",
                         user_message=f"请 {retry_after} 秒后重试",
                         details={"retry_after": retry_after})


class TimeoutError(BasePlatformException):
    def __init__(self, operation: str, timeout_s: float):
        super()(f"{operation} 超时 ({timeout_s}s)",
                code="ERR_TIMEOUT",
                user_message=f"请求处理超时，请稍后重试")


# ====== Agent 编排错误 (20xxx) ======

class MaxStepsExceededError(BasePlatformException):
    def __init__(self, max_steps: int):
        super().__init__(f"超过最大步骤数 ({max_steps})",
                         code="_ERR_AGENT_MAX_STEPS_EXCEEDED",
                         user_message="任务复杂度过高，已自动终止")


class ContextTooLongError(BasePlatformException):
    def __init__(self, current_tokens: int, max_tokens: int):
        super().__init__(f"上下文过长 ({current_tokens}/{max_tokens})",
                         code="ERR_AGENT_CONTEXT_TOO_LONG",
                         user_message="对话过长，请开启新会话")


class ToolNotFoundError(BasePlatformException):
    def __init__(self, tool_name: str):
        super().__init__(f"工具不存在: {tool_name}",
                         code="ERR_AGENT_TOOL_NOT_FOUND",
                         user_message=f"系统内部错误：找不到工具 [{tool_name[:16]}]")


# ====== 模型网关错误 (30xxx) ======

class AllProvidersDownError(BasePlatformException):
    def __init__(self):
        super().__init__("所有模型提供商不可用",
                         code="ERR_MODEL_ALL_PROVIDERS_DOWN",
                         user_message="AI 服务暂时不可用，请稍后重试")


class ModelContentFilteredError(BasePlatformException):
    def __init__(self, reason: str = ""):
        super().__init__(f"内容被安全过滤: {reason}",
                         code="ERR_MODEL_CONTENT_FILTERED",
                         user_message="输入内容可能包含不当信息，请调整后重试")


# ====== 工具总线错误 (40xxx) ======

class ToolValidationError(BasePlatformException):
    def __init__(self, tool_name: str, reason: str):
        super().__init__(f"工具参数校验失败 [{tool_name}]: {reason}",
                         code="ERR_TOOL_VALIDATION_FAILED",
                         user_message=f"参数不正确: {reason}")


class ToolExecutionFailedError(BasePlatformException):
    def __init__(self, tool_name: str, reason: str):
        super().__init__(f"工具执行失败 [{tool_name}]: {reason}",
                         code="ERR_TOOL_EXECUTION_FAILED",
                         user_message=f"工具执行失败，请稍后重试")


class ToolRiskRejectedError(BasePlatformException):
    def __init__(self, reason: str):
        super().__init__(f"操作被风控拒绝: {reason}",
                         code="ERR_TOOL_RISK_REJECTED",
                         user_message=f"该操作被安全策略阻止: {reason}")


class ApprovalRequiredError(BasePlatformException):
    def __init__(self, approval_id: str):
        super().__init__(f"需要人工审批: {approval_id}",
                         code="ERR_TOOL_APPROVAL_REQUIRED",
                         user_message="该操作需要人工审批，已提交审批申请")
```

#### core/constants.py — 常量定义（新增）

```python
# orchestrator-python/app/core/constants.py
"""全局常量定义。避免魔法数字散落在各处。"""

# ====== Agent 循环限制 ======
MAX_AGENT_STEPS = 10          # ReAct 最大循环次数
MAX_PLAN_STEPS = 20           # Plan-and-Execute 最大计划步骤数
MAX_CONSECUTIVE_SAME_TOOL = 2 # 相同工具重复调用阈值（防死循环）

# ====== 超时设置 ======
AGENT_TOTAL_TIMEOUT_S = 300   # 单次 Agent 任务总超时（5分钟）
MODEL_CALL_TIMEOUT_S = 30     # 单次模型调用超时
TOOL_CALL_TIMEOUT_S = 15      # 单次工具调用超时
APPROVAL_WAIT_TIMEOUT_S = 7200  # 审批等待超时（2小时）

# ====== Token 限制 ======
MAX_SYSTEM_PROMPT_TOKENS = 4000  # System Prompt 最大 token 数
MAX_USER_INPUT_TOKENS = 8000     # 用户输入最大 token 数
MAX_CONTEXT_WINDOW_TOKENS = 128000  # 模型最大上下文窗口
CONVERSATION_MEMORY_TARGET_TOKENS = 6000  # 对话记忆目标大小

# ====== RAG 参数 ======
RAG_TOP_K_BM25 = 50           # BM25 召回数量
RAG_TOP_K_VECTOR = 50         # 向量召回数量
RAG_RERANK_TOP_N = 20         # 精排保留数量
RAG_FINAL_TOP_K = 10          # 最终返回数量
EMBEDDING_CACHE_TTL_SECONDS = 2592000  # Embedding 缓存 TTL（30天）
RAG_RESULT_CACHE_TTL_SECONDS = 600     # RAG 结果缓存 TTL（10分钟）

# ====== 缓存 TTL ======
CACHE_SESSION_TTL_HOURS = 24           # 会话缓存 TTL
CACHE_USER_PREF_TTL_DAYS = 7           # 用户偏好 TTL
CACHE_TOOL_RESULT_TTL_MINUTES = 10     # 只读工具结果 TTL
CACHE_PROMPT_TEMPLATE_TTL_HOURS = 1    # Prompt 模板 TTL
CACHE_ROUTE_POLICY_TTL_MINUTES = 5     # 路由策略 TTL

# ====== 风险等级 ======
class RiskLevel(str):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# ====== 步骤类型 ======
class StepType(str):
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"
    INTENT_CLASSIFY = "intent_classify"
    RETRIEVE = "retrieve"
    RISK_CHECK = "risk_check"
    APPROVAL_WAIT = "approval_wait"

# ====== 审计事件分类 ======
class AuditCategory(str):
    LIFECYCLE = "lifecycle"
    SECURITY = "security"
    BUSINESS = "business"
    SYSTEM = "system"
```

### 2.2 Gateway Java 标准包结构（C-02 补充）

```
services/gateway-java/
└── src/main/java/com/platform/gateway/
    ├── GatewayApplication.java          # Spring Boot 启动类
    │
    ├── config/                          # === 配置层 ===
    │   ├── SecurityConfig.java          # Spring Security 配置 (JWT/OAuth2/API Key)
    │   ├── RateLimitConfig.java         # 令牌桶限流配置
    │   ├── GrpcClientConfig.java        # gRPC 客户端配置 (连接池/拦截器)
    │   ├── WebClientConfig.java         # HTTP 客户端配置
    │   ├── OpenTelemetryConfig.java     # OTel Tracing 配置
    │   └── CorsConfig.java              # CORS 配置
    │
    ├── controller/                      # === REST 控制器层 ===
    │   ├── ChatController.java          # POST /api/v1/chat/completions
    │   ├── AgentController.java         # POST /api/v1/agents/{id}/runs
    │   ├── SessionController.java       # GET /api/v1/sessions/{id}
    │   ├── ApprovalController.java      # POST /api/v1/approvals/{id}/review
    │   └── HealthController.java        # GET /health, /ready
    │
    ├── service/                         # === 业务逻辑层 ===
    │   ├── AuthService.java            # JWT 验证/Token 生成
    │   ├── TenantContextService.java    # 租户上下文管理
    │   ├── OrchestratorClient.java      # → Orchestrator gRPC/HTTP client
    │   ├── FastPathService.java        # ← 新增：快速路径意图判断
    │   └── AuditEventPublisher.java    # Kafka Producer (审计事件发布)
    │
    ├── middleware/                      # === Servlet 过滤器层 ===
    │   ├── RequestIdFilter.java        # 生成/传递 request_id (MDC)
    │   ├── TenantContextFilter.java    # 提取/注入 tenant_id
    │   ├── LoggingFilter.java          # 请求日志记录 (access log)
    │   ├── TimingFilter.java           # 请求耗时统计
    │   └── ExceptionHandlerFilter.java # 未捕获异常兜底处理
    │
    ├── dto/                            # === 数据传输对象 ===
    │   ├── request/
    │   │   ├── ChatRequest.java
    │   │   ├── AgentRunRequest.java
    │   │   └── ApprovalReviewRequest.java
    │   └── response/
    │       ├── ChatResponse.java
    │       ├── AgentRunResponse.java
    │       ├── ErrorResponse.java       # ← 统一错误响应格式
    │       └── HealthResponse.java
    │
    ├── exception/                      # === 异常处理层 ===
    │   ├── ErrorCode.java              # ← 统一错误码枚举 (映射 Proto)
    │   ├── BusinessException.java      # 自定义业务异常
    │   ├── GlobalExceptionHandler.java # @RestControllerAdvice
    │   └── ErrorAttributesEnhancer.java # 错误属性增强
    │
    ├── security/                       # === 安全层 ===
    │   ├── JwtTokenProvider.java       # JWT 生成/验证
    │   ├── ApiKeyAuthenticator.java    # API Key 认证
    │   ├── TenantAwareUserDetails.java # 租户感知的用户信息
    │   └── PermissionEvaluatorImpl.java # RBAC 权限评估
    │
    └── util/                           # === 工具类 ===
        ├── RequestIdGenerator.java     # UUID v7 生成
        └── ResponseUtil.java           # 统一响应封装
```

#### GlobalExceptionHandler.java — 统一异常处理（新增示例）

```java
// gateway-java/src/main/java/com/platform/gateway/exception/GlobalExceptionHandler.java
package com.platform.gateway.exception;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ErrorResponse handleBusinessException(BusinessException ex) {
        log.warn("Business error: code={}, msg={}", ex.getCode(), ex.getMessage());
        return ErrorResponse.builder()
                .error(ex.getCode())
                .message(ex.getMessage())
                .userMessage(ex.getUserMessage())
                .requestId(RequestIdGenerator.getCurrent())
                .build();
    }

    @ExceptionHandler({UnauthorizedException.class})
    @ResponseStatus(HttpStatus.UNAUTHORIZED)
    public ErrorResponse handleUnauthorized(UnauthorizedException ex) {
        return ErrorResponse.builder()
                .error("ERR_UNAUTHORIZED")
                .message(ex.getMessage())
                .userMessage("身份验证失败，请重新登录")
                .requestId(RequestIdGenerator.getCurrent())
                .build();
    }

    @ExceptionHandler({RateLimitExceededException.class})
    @ResponseStatus(HttpStatus.TOO_MANY_REQUESTS)
    public ErrorResponse handleRateLimit(RateLimitExceededException ex) {
        return ErrorResponse.builder()
                .error("ERR_RATE_LIMITED")
                .message("Rate limit exceeded")
                .userMessage("请求过于频繁，请稍后重试")
                .details(Map.of("retryAfter", ex.getRetryAfterSeconds()))
                .requestId(RequestIdGenerator.getCurrent())
                .build();
    }

    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ErrorResponse handleUnexpected(Exception ex) {
        log.error("Unexpected error", ex);
        // 不暴露内部异常细节给用户
        return ErrorResponse.builder()
                .error("ERR_UNKNOWN")
                .message("Internal server error")
                .userMessage("服务器内部错误，请联系管理员")
                .requestId(RequestIdGenerator.getCurrent())
                .build();
    }
}
```

### 2.3 其他 Java 服务的包结构模板

所有 Java 服务遵循相同的包组织模式：

```
{service-name}-java/src/main/java/com/platform/{service}/
├── {ServiceName}Application.java    # 启动类
├── config/                          # 配置类
├── service/                         # 业务逻辑
├── controller/                      # REST Controller (如有对外接口)
├── grpc/                            # gRPC Service 实现 (如需)
├── dto/                             # DTO
├── exception/                       # 异常处理
├── repository/                      # 数据访问 (JPA/MyBatis)
├── kafka/                           # Kafka Producer/Consumer (如需)
└── util/                            # 工具类
```

---

## 3. 日志规范（M-01 补充）

### 3.1 日志格式要求

**必须使用 JSON 结构化日志**（生产环境）。

每条日志必须包含的通用字段：

```json
{
  "timestamp": "2026-05-08T10:30:00.123Z",
  "level": "INFO",
  "logger": "com.platform.gateway.controller.ChatController",
  "message": "Chat request received",
  
  "request_id": "req_abc123def456",
  "trace_id": "trace_xyz789",
  "span_id": "span_001",
  
  "tenant_id": "tenant_001",
  "user_id": "user_zhangsan",
  
  "service": "gateway-java",
  "service_version": "1.2.3",
  "environment": "production",
  
  "duration_ms": 1234,
  "http_method": "POST",
  "http_path": "/api/v1/chat/completions",
  "http_status": 200,
  
  "custom_field_1": "value"
}
```

### 3.2 字段定义

| 字段名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `timestamp` | ISO8601 | 是 | UTC 时间 |
| `level` | Enum | 是 | DEBUG/INFO/WARN/ERROR/FATAL |
| `logger` | String | 是 | 类全限定名或模块标识 |
| `message` | String | 是 | 人类可读描述 |
| `request_id` | String(128) | **是** | 全链路唯一 ID，贯穿所有服务 |
| `trace_id` | String(128) | **是** | OpenTelemetry Trace ID |
| `span_id` | String(128) | 推荐 | OpenTelemetry Span ID |
| `tenant_id` | String(64) | **是** | 租户 ID |
| `user_id` | String(128) | **是** | 操作用户 ID |
| `service` | String(32) | **是** | 服务名称 |
| `service_version` | SemVer | 推荐 | 服务版本号 |
| `environment` | Enum | 推荐 | dev/test/staging/prod |

### 3.3 级别使用规范

| 级别 | 使用场景 | 生产采样 |
|---|---|---|
| **FATAL** | 系统无法自行恢复的致命错误（启动失败） | 100% 全量 |
| **ERROR** | 不可恢复的业务错误、安全事件 | 100% 全量 |
| **WARN** | 可恢复异常、降级、重试、接近阈值 | 100% 全量 |
| **INFO** | 关键业务节点（请求到达/完成/工具调用开始结束） | 100% 全量 |
| **DEBUG** | 详细调试信息 | **1% 采样** |

### 3.4 敏感信息过滤规则

日志输出前必须过滤以下字段：

| 敏感字段 | 过滤方式 | 过滤示例 |
|---|---|---|
| 手机号 | 中间 4 位脱敏 | `138****5678` |
| 身份证号 | 前 6 后 4 | `110101********1234` |
| 银行卡号 | 仅显后 4 位 | `****1234` |
| 邮箱 | 名首字符 + *** | `z***@example.com` |
| 密码/Token | 完全隐藏 | `[REDACTED]` |
| 用户原始输入 | 截断至 500 字符 | `... (truncated)` |
| API Key / Secret Key | 完全隐藏 | `[REDACTED]` |

### 3.5 Python 侧日志实现（推荐 structlog）

```python
# orchestrator-python/app/core/logging.py
"""统一的日志配置模块。
使用 structlog 作为结构化日志框架。
"""

import sys
import logging
import structlog
from typing import Any


def setup_logging(
    environment: str = "production",
    log_level: str = "INFO",
    json_output: bool = True,
) -> None:
    """
    配置 structlog 日志。
    
    Args:
        environment: dev/test/staging/prod
        log_level: 日志级别
        json_output: 是否输出 JSON 格式（生产环境必须 True）
    """
    
    # 共享处理器
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        
        # 敏感信息过滤器
        _SensitiveDataProcessor(),
        
        # 请求上下文注入
        _RequestContextProcessor(),
    ]
    
    if json_output or environment == "production":
        # 生产环境: JSON 输出
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.format_json_info,
                structlog.processors.JSONRenderer(sort_keys=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )
    else:
        # 开发环境: 彩色可读输出
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )


class _SensitiveDataProcessor(structlog.types.Processor):
    """过滤日志中的敏感数据。"""
    
    PATTERNS = {
        "phone": (r'1[3-9]\d{9}', lambda m: f"{m.group()[:3]}****{m.group()[-4:]}"),
        "id_card": (r'\d{17}[\dXx]', lambda m: f"{m.group()[:6]}********{m.group()[-4:]}"),
        "bank_card": (r'\d{16,19}', lambda m: f"****{m.group()[-4:]}"),
        "email": (r'[^@\s]+@[^@\s]+', lambda m: f"{m.group()[0]}***@{m.group().split('@')[1]}"),
    }
    
    def __call__(self, logger, method_name, event_dict):
        import re
        
        for key, value in event_dict.items():
            if isinstance(value, str):
                for field_type, (pattern, replacer) in self.PATTERNS.items():
                    value = re.sub(pattern, replacer, value)
                if len(value) > 500:
                    value = value[:500] + "... (truncated)"
                event_dict[key] = value
        return event_dict


class _RequestContextProcessor(structlog.types.Processor):
    """从上下文变量中提取 request_id / trace_id 等。"""
    
    def __call__(self, logger, method_name, event_dict):
        from contextvars import ContextVar
        
        try:
            from app.api.middleware.request_context import (
                get_request_id, get_tenant_id, get_user_id
            )
            event_dict.setdefault("request_id", get_request_id(""))
            event_dict.setdefault("tenant_id", get_tenant_id(""))
            event_dict.setdefault("user_id", get_user_id(""))
        except ImportError:
            pass
        return event_dict


# 全局 Logger
get_logger = structlog.get_logger
```

### 3.6 Java 侧日志实现（Logback + Logstash Encoder）

```xml
<!-- gateway-java/src/main/resources/logback.xml -->
<configuration>
    <!-- 引入 Spring 默认配置 -->
    <include resource="org/springframework/boot/logging/logback/defaults.xml"/>

    <springProperty scope="context" name="SERVICE_NAME" source="spring.application.name"/>
    <springProperty scope="context" name="ENVIRONMENT" source="spring.profiles.active" defaultValue="local"/>

    <!-- 控制台输出 (开发环境) -->
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%clr(%d{yyyy-MM-dd HH:mm:ss.SSS}){faint} %clr(%5p) %clr([%15.15t]){cyan} %clr(%-40.40logger{39}){yellow} : %msg%n</pattern>
            <charset>UTF-8</charset>
        </encoder>
    </appender>

    <!-- JSON 文件输出 (生产环境) -->
    <appender name="JSON_FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>${LOG_PATH:-/var/log/agent-platform}/${SERVICE_NAME}.json</file>
        <rollingPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy">
            <fileNamePattern>${LOG_PATH:-/var/log/agent-platform}/${SERVICE_NAME}.%d{yyyy-MM-dd}.%i.json.gz</fileNamePattern>
            <maxFileSize>256MB</maxFileSize>
            <maxHistory>30</maxHistory>
            <totalSizeCap>10GB</totalSizeCap>
        </rollingPolicy>
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <includeMdcKeyName>request_id</includeMdcKeyName>
            <includeMdcKeyName>trace_id</includeMdcKeyName>
            <includeMdcKeyName>tenant_id</includeMdcKeyName>
            <includeMdcKeyName>user_id</includeMdcKeyName>
            <fieldNames>
                <timestamp>timestamp</timestamp>
                <level>level</level>
                <logger>logger</logger>
                <message>message</message>
                <stack_trace>stack_trace</stack_trace>
            </fieldNames>
            <customFields>{"service":"${SERVICE_NAME}","version":"${APP_VERSION:-unknown}","environment":"${ENVIRONMENT}"}</customFields>
        </encoder>
    </appender>

    <!-- 异步写入 (性能保障) -->
    <appender name="ASYNC_JSON_FILE" class="ch.qos.logback.classic.AsyncAppender">
        <queueSize>1024</queueSize>
        <discardingThreshold>0</discardingThreshold>
        <neverBlock>true</neverBlock>
        <appender-ref ref="JSON_FILE"/>
    </appender>

    <!-- 敏感数据脱敏 -->
    <conversionRule conversionWord="mask" converterClass="com.platform.gateway.util.MaskingConverter"/>

    <logger name="com.platform" level="${LOG_LEVEL:-INFO}" additivity="false">
        <if condition='property("ENVIRONMENT").contains("prod")'>
            <then><appender-ref ref="ASYNC_JSON_FILE"/></then>
            <else><appender-ref ref="CONSOLE"/></else>
        </if>
    </logger>

    <root level="WARN">
        <appender-ref ref="ASYNC_JSON_FILE"/>
    </root>
</configuration>
```
