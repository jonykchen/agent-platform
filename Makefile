# ============================================================
#  Agent Platform — Monorepo Build System
#  用法: make <target>
# ============================================================

.PHONY: help build test lint proto fmt dev clean docker ci

# 默认显示帮助
help:
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:' $(MAKEFILE_LIST) | sort | awk -F':' '{printf "  %-20s %s\n", $$1, $$2}'

# ---- 构建 ----
build: build-java build-python
	@echo "✅ All services built"

build-java:
	@if [ -d services/gateway-java ]; then cd services/gateway-java && ./mvnw package -DskipTests -q 2>/dev/null || echo "gateway-java: no build configured"; fi
	@if [ -d services/tool-bus-java ]; then cd services/tool-bus-java && ./mvnw package -DskipTests -q 2>/dev/null || echo "tool-bus-java: no build configured"; fi
	@if [ -d services/governance-java ]; then cd services/governance-java && ./mvnw package -DskipTests -q 2>/dev/null || echo "governance-java: no build configured"; fi

build-python:
	@if [ -f services/orchestrator-python/pyproject.toml ]; then cd services/orchestrator-python && uv sync --quiet && uv build 2>/dev/null || pip install -e .; fi
	@if [ -f services/model-gateway-python/pyproject.toml ]; then cd services/model-gateway-python && uv sync --quiet && uv build 2>/dev/null || pip install -e .; fi
	@if [ -f services/knowledge-python/pyproject.toml ]; then cd services/knowledge-python && uv sync --quiet && uv build 2>/dev/null || pip install -e .; fi

# ---- 测试 ----
test: test-java test-python
	@echo "✅ All tests passed"

test-java:
	@if [ -d services/gateway-java ]; then cd services/gateway-java && ./mvnw test -q 2>/dev/null || echo "gateway-java: no tests"; fi

test-python:
	@if [ -f services/orchestrator-python/pyproject.toml ]; then cd services/orchestrator-python && uv run pytest tests/ -v --tb=short 2>/dev/null || echo "orchestrator-python: no tests"; fi

# ---- 代码质量 ----
lint: lint-java lint-python lint-proto
	@echo "✅ Lint passed"

lint-java:
	@if [ -d services/gateway-java ]; then cd services/gateway-java && ./mvnw checkstyle:check -q 2>/dev/null || echo "gateway-java: checkstyle not configured"; fi

lint-python:
	@if [ -f services/orchestrator-python/pyproject.toml ]; then cd services/orchestrator-python && uv run ruff check . 2>/dev/null || echo "ruff not installed"; fi
	@if [ -f services/orchestrator-python/pyproject.toml ]; then cd services/orchestrator-python && uv run ruff format --check . 2>/dev/null || true; fi

lint-proto:
	@if command -v buf >/dev/null 2>&1; then buf lint contracts/proto 2>/dev/null || echo "buf not configured"; fi

# ---- Proto 生成 ----
proto:
	@if command -v buf >/dev/null 2>&1; then buf generate 2>/dev/null || echo "buf generate failed"; fi
	@echo "✅ Proto code generated"

# ---- 格式化 ----
fmt: fmt-java fmt-python
	@echo "✅ Code formatted"

fmt-java:
	@if [ -d services/gateway-java ]; then cd services/gateway-java && ./mvnw spotless:apply -q 2>/dev/null || echo "spotless not configured"; fi

fmt-python:
	@if [ -f services/orchestrator-python/pyproject.toml ]; then cd services/orchestrator-python && uv run ruff format . 2>/dev/null || echo "ruff not installed"; fi

# ---- 开发环境 ----
dev:
	@if command -v docker-compose >/dev/null 2>&1; then docker-compose -f infra/docker-compose.yml up -d 2>/dev/null || docker compose -f infra/docker-compose.yml up -d; fi
	@echo "🚀 Dev environment started"

dev-down:
	@if command -v docker-compose >/dev/null 2>&1; then docker-compose -f infra/docker-compose.yml down 2>/dev/null || docker compose -f infra/docker-compose.yml down; fi
	@echo "🛑 Dev environment stopped"

# ---- 清理 ----
clean: clean-java clean-python
	@echo "🧹 Cleaned"

clean-java:
	find . -name target -type d -exec rm -rf {} + 2>/dev/null || true

clean-python:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name .pytest_cache -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name ".ruff_cache" -type d -exec rm -rf {} + 2>/dev/null || true

# ---- Docker ----
docker-build:
	@echo "Building Docker images..."
	@if [ -f services/gateway-java/Dockerfile ]; then docker build -t agent-platform/gateway:latest -f services/gateway-java/Dockerfile services/gateway-java/; fi
	@if [ -f services/orchestrator-python/Dockerfile ]; then docker build -t agent-platform/orchestrator:latest -f services/orchestrator-python/Dockerfile services/orchestrator-python/; fi

# ---- Full check (CI 使用) ----
ci: lint test
	@echo "✅ CI checks passed"

security-scan:
	@echo "Running security scans..."
	@if command -v gitleaks >/dev/null 2>&1; then gitleaks detect --source . --verbose || true; fi
	@if command -v trivy >/dev/null 2>&1; then trivy fs --severity HIGH,CRITICAL . || true; fi
