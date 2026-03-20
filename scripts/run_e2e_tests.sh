#!/bin/bash
# ============================================================
#  E2E 测试运行脚本
#  用法: ./scripts/run_e2e_tests.sh
# ============================================================

set -e

echo "🚀 Starting E2E tests..."

# 检查服务是否运行
check_service() {
    local name=$1
    local url=$2
    echo "Checking $name..."
    if curl -sf "$url" > /dev/null 2>&1; then
        echo "✅ $name is running"
    else
        echo "❌ $name is not running"
        return 1
    fi
}

# 启动依赖服务（如果未运行）
echo "Checking dependencies..."
docker compose -f infra/docker-compose.yml up -d

# 等待服务就绪
echo "Waiting for services to be ready..."
sleep 10

# 运行测试
echo "Running E2E tests..."
python -m pytest tests/e2e/ -v --tb=short -m "not slow"

echo "✅ E2E tests completed!"
