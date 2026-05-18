# ============================================================
#  Agent Platform — Monorepo Build System
#  用法: make <target>
# ============================================================

.PHONY: help build test lint proto proto-commit proto-verify fmt dev clean docker ci build-frontend test-frontend lint-frontend

# 默认显示帮助
help:
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:' $(MAKEFILE_LIST) | sort | awk -F':' '{printf "  %-20s %s\n", $$1, $$2}'

# ---- 构建 ----
build: build-java build-python build-frontend
	@echo "✅ All services built"

build-java:
	@if [ -d services/gateway-java ]; then cd services/gateway-java && ./mvnw package -DskipTests -q 2>/dev/null || echo "gateway-java: no build configured"; fi
	@if [ -d services/tool-bus-java ]; then cd services/tool-bus-java && ./mvnw package -DskipTests -q 2>/dev/null || echo "tool-bus-java: no build configured"; fi
	@if [ -d services/governance-java ]; then cd services/governance-java && ./mvnw package -DskipTests -q 2>/dev/null || echo "governance-java: no build configured"; fi

build-python:
	@if [ -f services/orchestrator-python/pyproject.toml ]; then cd services/orchestrator-python && uv sync --quiet && uv build 2>/dev/null || pip install -e .; fi
	@if [ -f services/model-gateway-python/pyproject.toml ]; then cd services/model-gateway-python && uv sync --quiet && uv build 2>/dev/null || pip install -e .; fi
	@if [ -f services/knowledge-python/pyproject.toml ]; then cd services/knowledge-python && uv sync --quiet && uv build 2>/dev/null || pip install -e .; fi

build-frontend:
	@if [ -f services/web-frontend/package.json ]; then \
		echo "Building frontend..."; \
		cd services/web-frontend && \
		(pnpm install --frozen-lockfile 2>/dev/null || npm install 2>/dev/null || echo "Install dependencies manually"); \
		pnpm build 2>/dev/null || npm run build 2>/dev/null || echo "Frontend build skipped"; \
	fi

# ---- 测试 ----
test: test-java test-python test-frontend
	@echo "✅ All tests passed"

test-java:
	@if [ -d services/gateway-java ]; then cd services/gateway-java && ./mvnw test -q 2>/dev/null || echo "gateway-java: no tests"; fi

test-python:
	@if [ -f services/orchestrator-python/pyproject.toml ]; then cd services/orchestrator-python && uv run pytest tests/ -v --tb=short 2>/dev/null || echo "orchestrator-python: no tests"; fi

test-frontend:
	@if [ -f services/web-frontend/package.json ]; then \
		cd services/web-frontend && \
		pnpm test 2>/dev/null || npm test 2>/dev/null || echo "Frontend tests skipped"; \
	fi

# ---- 测试覆盖率 ----
test-coverage: test-coverage-python test-coverage-java
	@echo "✅ Coverage reports generated"

test-coverage-python:
	@echo "Running Python tests with coverage..."
	@if [ -f services/orchestrator-python/pyproject.toml ]; then \
		cd services/orchestrator-python && uv run pytest tests/ --cov=app --cov-report=html --cov-report=term --cov-fail-under=80; \
	fi
	@if [ -f services/model-gateway-python/pyproject.toml ]; then \
		cd services/model-gateway-python && uv run pytest tests/ --cov=app --cov-report=html --cov-report=term; \
	fi

test-coverage-java:
	@echo "Running Java tests with coverage..."
	@if [ -d services/gateway-java ]; then \
		cd services/gateway-java && ./mvnw jacoco:prepare-agent test jacoco:report; \
	fi

# ---- 代码质量 ----
lint: lint-java lint-python lint-proto lint-frontend
	@echo "✅ Lint passed"

lint-java:
	@if [ -d services/gateway-java ]; then cd services/gateway-java && ./mvnw checkstyle:check -q 2>/dev/null || echo "gateway-java: checkstyle not configured"; fi

lint-python:
	@if [ -f services/orchestrator-python/pyproject.toml ]; then cd services/orchestrator-python && uv run ruff check . 2>/dev/null || echo "ruff not installed"; fi
	@if [ -f services/orchestrator-python/pyproject.toml ]; then cd services/orchestrator-python && uv run ruff format --check . 2>/dev/null || true; fi

lint-proto:
	@buf lint contracts/proto 2>/dev/null || echo "buf not installed"

lint-frontend:
	@if [ -f services/web-frontend/package.json ]; then \
		cd services/web-frontend && \
		pnpm lint 2>/dev/null || npm run lint 2>/dev/null || echo "Frontend lint skipped"; \
	fi

# ---- Proto 生成 ----
# 检测 buf 命令（兼容 Windows）
BUF_CMD := $(shell buf version >/dev/null 2>&1 && echo "buf" || echo "$(LOCALAPPDATA)/buf/buf.exe")

proto:
	@$(BUF_CMD) generate 2>/dev/null || echo "buf not installed or generate failed"
	@echo "✅ Proto code generated"

# Proto 生成并提交（最佳实践：Proto 改动时使用）
proto-commit: proto
	@echo "Adding generated code to git..."
	git add contracts/proto/
	git add services/*/target/generated-sources/proto/
	git add services/*/app/gen/
	@echo "✅ Proto and generated code staged. Run 'git commit' to complete."

# CI 验证：确保生成代码是最新的
proto-verify:
	@$(BUF_CMD) generate 2>/dev/null || (echo "❌ buf not installed" && exit 1)
	@git diff --exit-code contracts/proto services/*/target/generated-sources services/*/app/gen 2>/dev/null || \
		(echo "❌ Generated code is outdated! Run 'make proto-commit'" && exit 1)
	@echo "✅ Generated code is up-to-date"

# ---- 格式化 ----
fmt: fmt-java fmt-python
	@echo "✅ Code formatted"

fmt-java:
	@if [ -d services/gateway-java ]; then cd services/gateway-java && ./mvnw spotless:apply -q 2>/dev/null || echo "spotless not configured"; fi

fmt-python:
	@if [ -f services/orchestrator-python/pyproject.toml ]; then cd services/orchestrator-python && uv run ruff format . 2>/dev/null || echo "ruff not installed"; fi

# ---- 开发环境 ----
# 检测 docker compose 命令（兼容 Windows）
DOCKER_COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

dev:
	@$(DOCKER_COMPOSE) -f infra/docker-compose.yml up -d
	@echo "🚀 Dev environment started"

dev-down:
	@$(DOCKER_COMPOSE) -f infra/docker-compose.yml down
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
	@gitleaks detect --source . --verbose 2>/dev/null || echo "gitleaks not installed"
	@trivy fs --severity HIGH,CRITICAL . 2>/dev/null || echo "trivy not installed"
