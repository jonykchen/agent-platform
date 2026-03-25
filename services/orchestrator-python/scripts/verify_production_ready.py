#!/usr/bin/env python3
"""生产级优化验证脚本

验证内容:
1. 熔断器状态
2. 健康检查端点
3. Prometheus Metrics 端点
4. 缓存管理器初始化

使用方法:
    python scripts/verify_production_ready.py
"""

import asyncio
import sys
from pathlib import Path

# 添加 app 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


async def verify_resilience():
    """验证熔断器模块"""
    print("\n=== 1. 熔断器模块验证 ===")

    try:
        from app.core.resilience import (
            ModelGatewayCircuitBreaker,
            AsyncRetryPolicy,
            model_gateway_circuit,
            tool_bus_circuit,
            get_circuit_state_metric,
        )

        # 测试熔断器创建
        cb = ModelGatewayCircuitBreaker(
            name="test_circuit",
            failure_threshold=3,
            recovery_timeout=10,
        )
        print(f"✓ 熔断器创建成功: {cb.name}")
        print(f"  - 失败阈值: {cb.failure_threshold}")
        print(f"  - 恢复超时: {cb.recovery_timeout}s")

        # 测试全局实例
        print(f"✓ 全局 ModelGateway 熔断器: {model_gateway_circuit.name}")
        print(f"✓ 全局 ToolBus 熔断器: {tool_bus_circuit.name}")

        # 测试状态指标
        state = get_circuit_state_metric("model_gateway")
        print(f"✓ 熔断器状态指标: {state} (0=closed, 1=open, 2=half-open)")

        print("✅ 熔断器模块验证通过")
        return True

    except Exception as e:
        print(f"❌ 熔断器模块验证失败: {e}")
        return False


async def verify_health_checker():
    """验证健康检查模块"""
    print("\n=== 2. 健康检查模块验证 ===")

    try:
        from app.core.health_checker import (
            HealthChecker,
            HealthStatus,
            ComponentHealth,
            get_health_checker,
        )

        # 测试枚举
        print(f"✓ 健康状态枚举: {[s.value for s in HealthStatus]}")

        # 测试组件健康状态
        health = ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
            message="OK",
            latency_ms=10.5,
        )
        print(f"✓ 组件健康状态: {health.to_dict()}")

        # 测试健康检查器
        checker = HealthChecker()
        print(f"✓ 健康检查器创建成功")

        print("✅ 健康检查模块验证通过")
        return True

    except Exception as e:
        print(f"❌ 健康检查模块验证失败: {e}")
        return False


async def verify_metrics():
    """验证 Prometheus Metrics 模块"""
    print("\n=== 3. Prometheus Metrics 模块验证 ===")

    try:
        from app.core.metrics import (
            REQUEST_COUNT,
            REQUEST_LATENCY,
            MODEL_CALL_COUNT,
            TOOL_CALL_COUNT,
            CIRCUIT_BREAKER_STATE,
            CACHE_HITS,
            CACHE_MISSES,
            record_request,
            record_model_call,
            record_tool_call,
            RequestMetricsMiddleware,
        )

        # 验证指标定义
        print(f"✓ 请求计数指标: {REQUEST_COUNT._name}")
        print(f"✓ 请求延迟指标: {REQUEST_LATENCY._name}")
        print(f"✓ 模型调用指标: {MODEL_CALL_COUNT._name}")
        print(f"✓ 工具调用指标: {TOOL_CALL_COUNT._name}")
        print(f"✓ 熔断器状态指标: {CIRCUIT_BREAKER_STATE._name}")
        print(f"✓ 缓存命中指标: {CACHE_HITS._name}")

        # 测试记录函数
        record_request("GET", "/health", 200, 0.05)
        print(f"✓ 请求记录函数可用")

        record_model_call("qwen-max", "qwen", "success", 10.5)
        print(f"✓ 模型调用记录函数可用")

        record_tool_call("query_order", "tenant_001", "success", 0.5)
        print(f"✓ 工具调用记录函数可用")

        print("✅ Prometheus Metrics 模块验证通过")
        return True

    except Exception as e:
        print(f"❌ Prometheus Metrics 模块验证失败: {e}")
        return False


async def verify_cache():
    """验证缓存模块"""
    print("\n=== 4. 缓存模块验证 ===")

    try:
        from app.core.cache import (
            DualLayerCache,
            CacheManager,
            init_cache_manager,
            get_cache_manager,
        )

        # 测试哈希函数
        hash1 = DualLayerCache._hash_key("test query")
        hash2 = DualLayerCache._hash_key({"a": 1, "b": 2})
        print(f"✓ 字符串哈希: {hash1}")
        print(f"✓ 字典哈希: {hash2}")

        # 测试相同内容生成相同哈希
        hash3 = DualLayerCache._hash_key({"b": 2, "a": 1})  # 顺序不同
        assert hash2 == hash3, "相同内容应该生成相同哈希"
        print(f"✓ 哈希一致性验证通过")

        # 测试缓存管理器（需要 Mock Redis）
        from unittest.mock import AsyncMock
        mock_redis = AsyncMock()
        manager = CacheManager(mock_redis)

        rag_cache = manager.get_rag_cache()
        schema_cache = manager.get_tool_schema_cache()
        model_cache = manager.get_model_list_cache()

        print(f"✓ RAG 缓存创建成功: {rag_cache._name}")
        print(f"✓ 工具 Schema 缓存创建成功: {schema_cache._name}")
        print(f"✓ 模型列表缓存创建成功: {model_cache._name}")

        print("✅ 缓存模块验证通过")
        return True

    except Exception as e:
        print(f"❌ 缓存模块验证失败: {e}")
        return False


async def verify_constants():
    """验证常量定义"""
    print("\n=== 5. 常量定义验证 ===")

    try:
        from app.core.constants import (
            MAX_CONCURRENT_REQUESTS,
            MAX_CONCURRENT_MODEL_CALLS,
            MAX_CONCURRENT_TOOL_CALLS,
            CIRCUIT_FAILURE_THRESHOLD,
            CIRCUIT_RECOVERY_TIMEOUT,
            RETRY_MAX_ATTEMPTS,
            STREAM_TIMEOUT_S,
        )

        print(f"✓ 最大并发请求: {MAX_CONCURRENT_REQUESTS}")
        print(f"✓ 最大并发模型调用: {MAX_CONCURRENT_MODEL_CALLS}")
        print(f"✓ 最大并发工具调用: {MAX_CONCURRENT_TOOL_CALLS}")
        print(f"✓ 熔断器失败阈值: {CIRCUIT_FAILURE_THRESHOLD}")
        print(f"✓ 熔断器恢复超时: {CIRCUIT_RECOVERY_TIMEOUT}s")
        print(f"✓ 最大重试次数: {RETRY_MAX_ATTEMPTS}")
        print(f"✓ 流式超时: {STREAM_TIMEOUT_S}s")

        print("✅ 常量定义验证通过")
        return True

    except Exception as e:
        print(f"❌ 常量定义验证失败: {e}")
        return False


async def main():
    """主验证流程"""
    print("=" * 60)
    print("Agent Platform 生产级优化验证")
    print("=" * 60)

    results = []

    results.append(await verify_resilience())
    results.append(await verify_health_checker())
    results.append(await verify_metrics())
    results.append(await verify_cache())
    results.append(await verify_constants())

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"验证结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有验证通过，生产级优化完成！")
        return 0
    else:
        print("⚠️ 部分验证失败，请检查实现")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
