"""测试 Prometheus Metrics"""

from unittest.mock import MagicMock


class TestMetricsDefinitions:
    """测试 Metrics 定义"""

    def test_request_metrics_defined(self):
        """测试请求指标定义"""
        from app.core.metrics import (
            REQUEST_COUNT,
            REQUEST_IN_PROGRESS,
            REQUEST_LATENCY,
        )

        assert REQUEST_COUNT is not None
        assert REQUEST_LATENCY is not None
        assert REQUEST_IN_PROGRESS is not None

    def test_model_metrics_defined(self):
        """测试模型指标定义"""
        from app.core.metrics import (
            MODEL_CALL_COUNT,
            MODEL_CALL_IN_PROGRESS,
            MODEL_CALL_LATENCY,
        )

        assert MODEL_CALL_COUNT is not None
        assert MODEL_CALL_LATENCY is not None
        assert MODEL_CALL_IN_PROGRESS is not None

    def test_tool_metrics_defined(self):
        """测试工具指标定义"""
        from app.core.metrics import (
            TOOL_CALL_COUNT,
            TOOL_CALL_IN_PROGRESS,
            TOOL_CALL_LATENCY,
        )

        assert TOOL_CALL_COUNT is not None
        assert TOOL_CALL_LATENCY is not None
        assert TOOL_CALL_IN_PROGRESS is not None

    def test_circuit_breaker_metrics_defined(self):
        """测试熔断器指标定义"""
        from app.core.metrics import (
            CIRCUIT_BREAKER_FAILURES,
            CIRCUIT_BREAKER_OPENS,
            CIRCUIT_BREAKER_STATE,
        )

        assert CIRCUIT_BREAKER_STATE is not None
        assert CIRCUIT_BREAKER_FAILURES is not None
        assert CIRCUIT_BREAKER_OPENS is not None

    def test_cache_metrics_defined(self):
        """测试缓存指标定义"""
        from app.core.metrics import (
            CACHE_HITS,
            CACHE_MISSES,
            CACHE_SIZE,
        )

        assert CACHE_HITS is not None
        assert CACHE_MISSES is not None
        assert CACHE_SIZE is not None

    def test_agent_metrics_defined(self):
        """测试 Agent 指标定义"""
        from app.core.metrics import (
            AGENT_RUN_COUNT,
            AGENT_RUN_LATENCY,
            AGENT_STEP_COUNT,
        )

        assert AGENT_RUN_COUNT is not None
        assert AGENT_STEP_COUNT is not None
        assert AGENT_RUN_LATENCY is not None


class TestMetricFunctions:
    """测试指标记录函数"""

    def test_record_request(self):
        """测试记录请求"""
        from app.core.metrics import record_request

        # 记录请求
        record_request("GET", "/health", 200, 0.05)

        # 验证计数器增加
        # 注意：prometheus_client 的 Counter 不能直接读取值
        # 这里只验证函数不抛异常

    def test_record_model_call(self):
        """测试记录模型调用"""
        from app.core.metrics import record_model_call

        record_model_call("qwen-max", "qwen", "success", 10.5)

    def test_record_tool_call(self):
        """测试记录工具调用"""
        from app.core.metrics import record_tool_call

        record_tool_call("query_order", "tenant_001", "success", 0.5)

    def test_update_circuit_breaker_state(self):
        """测试更新熔断器状态"""
        from app.core.metrics import update_circuit_breaker_state

        update_circuit_breaker_state("model_gateway", 0)  # closed
        update_circuit_breaker_state("model_gateway", 1)  # open
        update_circuit_breaker_state("model_gateway", 2)  # half-open

    def test_record_cache_hit(self):
        """测试记录缓存命中"""
        from app.core.metrics import record_cache_hit

        record_cache_hit("rag")

    def test_record_cache_miss(self):
        """测试记录缓存未命中"""
        from app.core.metrics import record_cache_miss

        record_cache_miss("rag")

    def test_record_agent_run(self):
        """测试记录 Agent 运行"""
        from app.core.metrics import record_agent_run

        record_agent_run("success", 5, 30.5)


class TestRequestMetricsMiddleware:
    """测试请求指标中间件"""

    def test_middleware_creates(self):
        """测试中间件创建"""
        from app.core.metrics import RequestMetricsMiddleware

        mock_app = MagicMock()
        middleware = RequestMetricsMiddleware(mock_app)

        assert middleware.app == mock_app
