#!/bin/bash
# 测试运行脚本
# 用法: ./scripts/run_tests.sh [service] [type]

set -e

SERVICE="${1:-all}"
TYPE="${2:-unit}"

echo "=== Agent Platform Test Runner ==="
echo "Service: $SERVICE"
echo "Type: $TYPE"
echo ""

run_python_tests() {
    local service=$1
    local test_type=$2
    local test_path="tests/$test_type"

    echo "Running $test_type tests for $service..."

    if [ -f "$service/pyproject.toml" ]; then
        if command -v uv >/dev/null 2>&1; then
            cd "$service" && uv run pytest "$test_path" -v --tb=short || echo "Tests failed for $service"
        elif command -v pytest >/dev/null 2>&1; then
            cd "$service" && pytest "$test_path" -v --tb=short || echo "Tests failed for $service"
        else
            echo "Warning: pytest not available for $service"
        fi
    fi
}

run_java_tests() {
    local service=$1

    echo "Running tests for $service..."

    if [ -f "$service/pom.xml" ]; then
        cd "$service" && mvn test -q || echo "Tests failed for $service"
    fi
}

# Python 服务
PYTHON_SERVICES=(
    "services/orchestrator-python"
    "services/model-gateway-python"
    "services/knowledge-python"
)

# Java 服务
JAVA_SERVICES=(
    "services/gateway-java"
    "services/tool-bus-java"
    "services/governance-java"
)

case "$SERVICE" in
    all)
        for svc in "${PYTHON_SERVICES[@]}"; do
            run_python_tests "$svc" "$TYPE"
        done
        for svc in "${JAVA_SERVICES[@]}"; do
            run_java_tests "$svc"
        done
        ;;
    orchestrator)
        run_python_tests "services/orchestrator-python" "$TYPE"
        ;;
    model-gateway)
        run_python_tests "services/model-gateway-python" "$TYPE"
        ;;
    knowledge)
        run_python_tests "services/knowledge-python" "$TYPE"
        ;;
    gateway-java)
        run_java_tests "services/gateway-java"
        ;;
    tool-bus-java)
        run_java_tests "services/tool-bus-java"
        ;;
    python)
        for svc in "${PYTHON_SERVICES[@]}"; do
            run_python_tests "$svc" "$TYPE"
        done
        ;;
    java)
        for svc in "${JAVA_SERVICES[@]}"; do
            run_java_tests "$svc"
        done
        ;;
    *)
        echo "Unknown service: $SERVICE"
        echo "Available: all, orchestrator, model-gateway, knowledge, gateway-java, tool-bus-java, python, java"
        exit 1
        ;;
esac

echo ""
echo "=== Tests completed ==="