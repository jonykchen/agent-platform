"""Prometheus 指标定义

集中定义 Model Gateway 的业务指标，供 chat/embeddings 端点埋点，
并通过 /metrics 端点暴露给 Prometheus 抓取。

指标命名遵循 Prometheus 约定（snake_case + 单位后缀），
并与 infra/prometheus-alerts.yml 中的告警规则对齐：
- model_call_total / model_call_latency_seconds → 模型调用次数与延迟
- model_call_cost_usd_total → 累计成本（用于成本看板与预算告警）
- model_gateway_rate_limited_total → 被限流的请求数
- model_content_filtered_total → 被内容过滤拦截的请求数
"""

from prometheus_client import Counter, Histogram

# 模型调用次数（按 provider/model/状态维度）
MODEL_CALL_TOTAL = Counter(
    "model_call_total",
    "模型调用总次数",
    ["provider", "model", "status", "stream"],
)

# 模型调用延迟（秒）
MODEL_CALL_LATENCY = Histogram(
    "model_call_latency_seconds",
    "模型调用延迟（秒）",
    ["provider", "model", "stream"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0),
)

# 累计 token 数（按方向：prompt/completion）
MODEL_TOKENS_TOTAL = Counter(
    "model_tokens_total",
    "累计 token 数",
    ["provider", "model", "direction"],
)

# 累计调用成本（美元）。这是成本上报的核心指标。
MODEL_COST_USD_TOTAL = Counter(
    "model_call_cost_usd_total",
    "模型调用累计成本（美元）",
    ["provider", "model", "tenant_id"],
)

# 被限流拦截的请求数
RATE_LIMITED_TOTAL = Counter(
    "model_gateway_rate_limited_total",
    "被分布式限流拦截的请求数",
    ["tenant_id"],
)

# 被内容过滤拦截的请求数（按类目）
CONTENT_FILTERED_TOTAL = Counter(
    "model_content_filtered_total",
    "被内容过滤拦截的请求数",
    ["category", "source"],
)

# Embedding 调用次数
EMBEDDING_CALL_TOTAL = Counter(
    "embedding_call_total",
    "Embedding 调用总次数",
    ["provider", "model", "status"],
)


def record_cost(
    provider: str,
    model: str,
    tenant_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
) -> None:
    """上报一次模型调用的 token 与成本指标。

    Args:
        provider: 提供商名称
        model: 模型名称
        tenant_id: 租户 ID（未知时传 "unknown"）
        prompt_tokens: 输入 token 数
        completion_tokens: 输出 token 数
        cost_usd: 本次调用成本（美元）
    """
    tenant = tenant_id or "unknown"
    MODEL_TOKENS_TOTAL.labels(provider=provider, model=model, direction="prompt").inc(prompt_tokens)
    MODEL_TOKENS_TOTAL.labels(provider=provider, model=model, direction="completion").inc(completion_tokens)
    MODEL_COST_USD_TOTAL.labels(provider=provider, model=model, tenant_id=tenant).inc(cost_usd)
