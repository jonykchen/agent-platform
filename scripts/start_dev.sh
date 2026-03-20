#!/bin/bash
# ============================================================
#  本地开发启动脚本
#  用法: ./scripts/start_dev.sh
# ============================================================

set -e

echo "🚀 Starting Agent Platform development environment..."

# 启动基础设施
echo "Starting infrastructure services..."
docker compose -f infra/docker-compose.yml up -d

# 等待服务就绪
echo "Waiting for infrastructure to be ready..."
sleep 10

# 检查 PostgreSQL
echo "Checking PostgreSQL..."
until docker exec agent-postgres pg_isready -U app_user; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done
echo "✅ PostgreSQL is ready"

# 检查 Redis
echo "Checking Redis..."
until docker exec agent-redis redis-cli -a dev_password ping | grep -q PONG; do
    echo "Waiting for Redis..."
    sleep 2
done
echo "✅ Redis is ready"

# 运行数据库迁移
echo "Running database migrations..."
docker exec -i agent-postgres psql -U app_user -d agent_platform < shared/sql/V001__init_schema.sql || true

echo ""
echo "✅ Development environment is ready!"
echo ""
echo "Services:"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo "  - MinIO: http://localhost:9001 (minioadmin/minioadmin123)"
echo "  - Grafana: http://localhost:3000 (admin/admin)"
echo "  - Prometheus: http://localhost:9090"
echo ""
echo "To start services:"
echo "  Gateway:        cd services/gateway-java && ./mvnw spring-boot:run"
echo "  Orchestrator:   cd services/orchestrator-python && uv run uvicorn app.main:app --reload"
echo "  Model Gateway:  cd services/model-gateway-python && uv run uvicorn app.main:app --reload --port 8001"
echo "  Tool Bus:       cd services/tool-bus-java && ./mvnw spring-boot:run"
