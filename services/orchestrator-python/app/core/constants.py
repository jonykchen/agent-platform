"""全局常量定义 (C-01)

避免魔法数字散落在各处。
"""

# ====== Agent 循环限制 ======
MAX_AGENT_STEPS = 10          # ReAct 最大循环次数
MAX_PLAN_STEPS = 20           # Plan-and-Execute 最大计划步骤数
MAX_CONSECUTIVE_SAME_TOOL = 2 # 相同工具重复调用阈值（防死循环）

# ====== 超时设置 ======
AGENT_TOTAL_TIMEOUT_S = 300   # 单次 Agent 任务总超时（5分钟）
MODEL_CALL_TIMEOUT_S = 30     # 单次模型调用超时
TOOL_CALL_TIMEOUT_S = 15      # 单次工具调用超时
APPROVAL_WAIT_TIMEOUT_S = 7200  # 审批等待超时（2小时）
STREAM_TIMEOUT_S = 60         # 流式响应总超时

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

# ====== 并发限制 ======
MAX_CONCURRENT_REQUESTS = 50           # 最大并发请求数
MAX_CONCURRENT_MODEL_CALLS = 20        # 最大并发模型调用数
MAX_CONCURRENT_TOOL_CALLS = 30         # 最大并发工具调用数

# ====== 熔断器默认配置 ======
CIRCUIT_FAILURE_THRESHOLD = 5          # 熔断器失败阈值
CIRCUIT_RECOVERY_TIMEOUT = 30          # 熔断器恢复超时（秒）

# ====== 重试默认配置 ======
RETRY_MAX_ATTEMPTS = 3                 # 最大重试次数
RETRY_MIN_WAIT_S = 1.0                 # 最小等待时间（秒）
RETRY_MAX_WAIT_S = 10.0                # 最大等待时间（秒）


class RiskLevel:
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StepType:
    """步骤类型"""
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"
    INTENT_CLASSIFY = "intent_classify"
    RETRIEVE = "retrieve"
    RISK_CHECK = "risk_check"
    APPROVAL_WAIT = "approval_wait"


class AuditCategory:
    """审计事件分类"""
    LIFECYCLE = "lifecycle"
    SECURITY = "security"
    BUSINESS = "business"
    SYSTEM = "system"


class SessionStatus:
    """会话状态"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"


class RunStatus:
    """运行状态"""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PENDING_APPROVAL = "pending_approval"