"""Prometheus Metrics 模块

暴露关键指标，支持 Prometheus 抓取。
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ====== 请求指标 ======

REQUEST_COUNT = Counter(
    "orchestrator_request_total",
    "Total requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "orchestrator_request_latency_seconds",
    "Request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

REQUEST_IN_PROGRESS = Gauge(
    "orchestrator_requests_in_progress",
    "Requests currently in progress",
    ["method", "endpoint"],
)

# ====== 模型调用指标 ======

MODEL_CALL_COUNT = Counter(
    "model_call_total",
    "Total model calls",
    ["model", "provider", "status"],
)

MODEL_CALL_LATENCY = Histogram(
    "model_call_latency_seconds",
    "Model call latency",
    ["model", "provider"],
    buckets=[5, 10, 15, 20, 30, 45, 60, 90, 120],
)

MODEL_CALL_IN_PROGRESS = Gauge(
    "model_calls_in_progress",
    "Model calls currently in progress",
    ["model"],
)

# ====== 工具调用指标 ======

TOOL_CALL_COUNT = Counter(
    "tool_call_total",
    "Total tool calls",
    ["tool_name", "tenant_id", "status"],
)

TOOL_CALL_LATENCY = Histogram(
    "tool_call_latency_seconds",
    "Tool call latency",
    ["tool_name"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 15.0, 30.0],
)

TOOL_CALL_IN_PROGRESS = Gauge(
    "tool_calls_in_progress",
    "Tool calls currently in progress",
    ["tool_name"],
)

# ====== 熔断器指标 ======

CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["service"],
)

CIRCUIT_BREAKER_FAILURES = Counter(
    "circuit_breaker_failures_total",
    "Total circuit breaker failures",
    ["service"],
)

CIRCUIT_BREAKER_OPENS = Counter(
    "circuit_breaker_opens_total",
    "Total times circuit breaker opened",
    ["service"],
)

# ====== 缓存指标 ======

CACHE_HITS = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_name"],
)

CACHE_MISSES = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_name"],
)

CACHE_SIZE = Gauge(
    "cache_size",
    "Current cache size",
    ["cache_name"],
)

# ====== Agent 指标 ======

AGENT_RUN_COUNT = Counter(
    "agent_run_total",
    "Total agent runs",
    ["status"],
)

AGENT_STEP_COUNT = Histogram(
    "agent_step_count",
    "Number of steps per agent run",
    buckets=[1, 2, 3, 5, 7, 10, 15, 20],
)

AGENT_RUN_LATENCY = Histogram(
    "agent_run_latency_seconds",
    "Agent run latency",
    buckets=[5, 10, 15, 30, 45, 60, 90, 120, 180, 300],
)


def record_request(method: str, endpoint: str, status: int, latency: float):
    """记录请求指标"""
    status_str = str(status)
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status_str).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(latency)


def record_model_call(
    model: str,
    provider: str,
    status: str,
    latency: float,
):
    """记录模型调用指标"""
    MODEL_CALL_COUNT.labels(model=model, provider=provider, status=status).inc()
    MODEL_CALL_LATENCY.labels(model=model, provider=provider).observe(latency)


def record_tool_call(
    tool_name: str,
    tenant_id: str,
    status: str,
    latency: float,
):
    """记录工具调用指标"""
    TOOL_CALL_COUNT.labels(
        tool_name=tool_name,
        tenant_id=tenant_id,
        status=status,
    ).inc()
    TOOL_CALL_LATENCY.labels(tool_name=tool_name).observe(latency)


def update_circuit_breaker_state(service: str, state: int):
    """更新熔断器状态"""
    CIRCUIT_BREAKER_STATE.labels(service=service).set(state)


def record_cache_hit(cache_name: str):
    """记录缓存命中"""
    CACHE_HITS.labels(cache_name=cache_name).inc()


def record_cache_miss(cache_name: str):
    """记录缓存未命中"""
    CACHE_MISSES.labels(cache_name=cache_name).inc()


def record_agent_run(status: str, step_count: int, latency: float):
    """记录 Agent 运行"""
    AGENT_RUN_COUNT.labels(status=status).inc()
    AGENT_STEP_COUNT.observe(step_count)
    AGENT_RUN_LATENCY.observe(latency)


class RequestMetricsMiddleware:
    """请求指标中间件

    使用方法：
    app.add_middleware(RequestMetricsMiddleware)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]

        # 排除 metrics 端点本身
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        REQUEST_IN_PROGRESS.labels(method=method, endpoint=path).inc()

        start_time = __import__("time").monotonic()

        status_code = 200

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            latency = __import__("time").monotonic() - start_time
            REQUEST_IN_PROGRESS.labels(method=method, endpoint=path).dec()
            record_request(method, path, status_code, latency)
