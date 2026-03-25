# 运维指南 — 配置管理、Feature Flag、CI/CD 与服务发现

> **版本**：v2.1 | **状态**：✅ 完成 | **对应审查项**：M-03, M-04, M-05
>
> **v2.1 更新**：新增三级健康检查、Prometheus Metrics、缓存管理器

---

## 1. 配置管理策略（M-03 补充）

### 配置优先级链（低 → 高）

```
优先级 1 (最低): application.yml / pyproject.toml     内置默认值
优先级 2:        Nacos / Apollo 配置中心               环境级默认值
优先级 3:        环境变量                                容器注入（覆盖配置中心）
优先级 4 (最高): 启动参数 --option=value                 命令行显式指定
```

### 环境命名规范

| 环境 | 命名 | 用途 | 特征 |
|---|---|---|---|
| **local** | 本地开发 | 开发者个人电脑 | DEBUG 日志全量、无严格限流 |
| **dev** | 开发环境 | 共享联调环境 | 允许调试接口、日志 INFO 全量 |
| **test** | 测试环境 | 自动化测试运行 | 数据可重置、Mock 外部依赖 |
| **staging** | 预发布 | 与生产同配置（脱敏数据） | 生产级限流、日志采样、监控全量 |
| **prod** | 生产环境 | 线上正式环境 | 严格限流、日志 1% DEBUG 采样 |

### 敏感配置清单

以下配置项 **必须走 KMS/Vault/Secrets Manager**，禁止明文写入配置中心或代码：

```yaml
# ⚠️ 绝对不能明文存储的配置项：
forbidden_plain_text:
  database:
    - spring.datasource.password
    - redis.password
  security:
    - jwt.secret-key
    - encryption.master-key
  llm:
    - providers.*.api-key       # 各厂商 API Key
  external:
    - oss.access-key-secret
    - kafka.sasl.password
    - vault.token

# ✅ 安全的获取方式：
secure_sources:
  production:
    - HashiCorp Vault (动态凭证)
    - AWS Secrets Manager / KMS
    - K8s External Secrets Operator (从 Vault 同步到 K8s Secret)
  development:
    - .env.local (gitignored) + direnv 自动加载
```

### Nacos/Apollo 配置示例

```yaml
# ====== gateway-java: application-prod.yml ======
spring:
  profiles:
    active: prod
  
  cloud:
    nacos:
      discovery:
        server-addr: ${NACOS_SERVER:nacos-headless.agent-platform:8848}
        namespace: ${NAMESPACE_ID:prod}
      config:
        server-addr: ${NACOS_SERVER:nacos-headless.agent-platform:8848}
        namespace: ${NAMESPACE_ID:prod}
        file-extension: yaml
        shared-configs:
          # 公共配置
          - data-id: common-db.yaml
            group: DEFAULT_GROUP
            refresh: true
          - data-id: common-redis.yaml
            group: DEFAULT_GROUP
            refresh: true
          - data-id: common-security.yaml
            group: DEFAULT_GROUP
            refresh: false  # 安全配置不自动刷新，需要重启

# 敏感配置从环境变量读取（由 External Secrets 注入）
secrets:
  db-password: ${DB_PASSWORD}
  redis-password: ${REDIS_PASSWORD}
  jwt-secret: ${JWT_SECRET}
```

```python
# ====== orchestrator-python: app/core/config.py ======
"""Pydantic Settings — 统一配置管理。

支持从环境变量和 .env 文件加载。
敏感字段在文档中标记为 [SECRET]。
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """应用主配置"""
    
    # ---- 环境 ----
    environment: str = Field(default="local", description="local/dev/test/staging/prod")
    debug: bool = Field(default=False)
    
    # ---- 应用基础 ----
    app_name: str = "orchestrator"
    app_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000
    
    # ---- 模型网关地址 ----
    model_gateway_url: str = "http://model-gateway:8001"
    tool_bus_grpc_addr: str = "tool-bus:50051"
    
    # ---- 数据库 [SECRET] ----
    database_url: str = Field(
        default="postgresql+asyncpg://app_user:dev_pass@localhost:5432/agent_platform",
        description="[SECRET] PostgreSQL 异步连接 URL",
    )
    database_pool_size: int = 20
    
    # ---- Redis [SECRET] ----
    redis_url: str = Field(
        default="redis://:dev_pass@localhost:6379/0",
        description="[SECRET] Redis 连接 URL",
    )
    
    # ---- LLM API Keys [SECRET] ----
    qwen_api_key: str = Field(default="", description="[SECRET] 通义千问 API Key")
    glm_api_key: str = Field(default="", description="[SECRET] 智谱 GLM API Key")
    kimi_api_key: str = Field(default="", description="[SECRET] Moonshot Kimi API Key")
    deepseek_api_key: str = Field(default="", description="[SECRET] DeepSeek API Key")
    
    # ---- JWT [SECRET] ----
    jwt_secret: str = Field(
        default="dev-only-change-me-in-production-min-32-chars!!!",
        description="[SECRET] JWT 签名密钥（生产必须 ≥ 32 字符）",
    )
    jwt_algorithm: str = "HS256"
    jwt_expiry_seconds: int = 86400  # 24h
    
    # ---- OpenTelemetry ----
    otel_enabled: bool = True
    otlp_endpoint: str = "http://otel-collector:4317"
    
    class Config:
        env_prefix = ""           # 环境变量前缀（空=直接匹配）
        env_nested_delimiter = "__"  # 支持嵌套: DATABASE__POOL_SIZE
        env_file = ".env.local"   # 从 .env.local 加载（gitignored）
        extra = "ignore"           # 忽略未声明的环境变量
    
    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        if info.data.get("environment") == "prod" and len(v) < 32:
            raise ValueError("Production JWT secret must be at least 32 characters")
        return v


config = AppConfig()
```

---

## 2. Feature Flag 功能开关体系（M-04 补充）

### 为什么需要 Feature Flag

没有 Feature Flag 的后果：
- 新功能上线只能"全量或不上"
- 出问题时无法一键关闭某个功能
- 无法做 A/B 测试或灰度发布
- 无法按租户/用户组开放不同能力

### 推荐方案：Unleash（开源）或自建简化版

```yaml
# feature-flag 配置示例
features:
  # === 核心功能开关 ===
  rag_enabled:
    enabled: true
    strategies:
      - name: default
        parameters:
          rolloutPercentage: 100
  
  multi_modal_enabled:
    enabled: true
    strategies:
      - name: gradualRollout
        parameters:
          rolloutPercentage: 20
          stickiness: userId  # 同一用户稳定看到同一版本
  
  # === Agent 模式切换 ===
  plan_execute_mode:
    enabled: true
    strategies:
      - name: specificUsers
        parameters:
          userIds: ["admin_001", "ai_engineer_001"]
  
  # === 工具级别开关 ===
  tool_query_invoice_v2:
    enabled: true
    strategies:
      - name: specificTenant
        parameters:
          tenantIds: ["tenant_alpha", "tenant_beta"]
  
  # === 紧急 Kill Switch ===
  kill_switch_model_glm:
    enabled: false              # 🔴 紧急情况置 false，立即下线 GLM
    description: "紧急关闭 GLM 模型（如检测到异常输出）"
  
  kill_switch_tool_approval:
    enabled: true               # 审批功能总开关
  
  # === A/B 测试配置 ===
  ab_test_prompt_v3:
    enabled: true
    strategies:
      - name: flexibleRollout
        parameters:
          rolloutPercentage: 50
          stickiness: sessionId
    variants:
      control:
        weight: 50
        payload: { "prompt_version": "v2_stable" }
      treatment:
        weight: 50
        payload: { "prompt_version": "v3_experimental" }
```

### Python 侧集成

```python
# orchestrator-python/app/core/feature_flags.py
"""Feature Flag 客户端。

轻量实现：基于 Redis + JSON 配置。
生产环境建议替换为 Unleash SDK。
"""

from __future__ import annotations

import json

import redis.asyncio as aioredis


class FeatureFlagClient:
    """Feature Flag 客户端"""
    
    def __init__(self, redis: aioredis.Redis, config_cache_ttl: int = 60):
        self.redis = redis
        self.config_cache_ttl = config_cache_ttl
        self._local_cache: dict[str, dict] = {}
        self._cache_time: float = 0
    
    async def is_enabled(
        self,
        flag_name: str,
        context: dict | None = None,
        default: bool = False,
    ) -> bool:
        """
        判断一个 Feature Flag 是否启用。
        
        Args:
            flag_name: 功能开关名称
            context: 上下文信息（用于灰度判断），包含 tenant_id/user_id/session_id 等
            default: 默认值（flag 不存在时返回）
        
        Returns:
            是否启用
        """
        config = await self._get_flag_config(flag_name)
        if config is None:
            return default
        
        if not config.get("enabled", False):
            return False
        
        strategies = config.get("strategies", [])
        if not strategies:
            return config["enabled"]
        
        # 检查每个策略
        for strategy in strategies:
            if await self._match_strategy(strategy, context):
                return True
        
        return default
    
    async def _get_flag_config(self, flag_name: str) -> dict | None:
        """获取 Flag 配置（带本地缓存）"""
        import time
        
        now = time.time()
        if self._local_cache and (now - self._cache_time) < self.config_cache_ttl:
            return self._local_cache.get(flag_name)
        
        raw = await self.redis.get(f"ff:{flag_name}")
        if raw is None:
            return None
        
        config = json.loads(raw)
        self._local_cache[flag_name] = config
        self._cache_time = now
        return config
    
    async def _match_strategy(self, strategy: dict, context: dict | None) -> bool:
        """匹配单个策略"""
        name = strategy.get("name", "")
        params = strategy.get("parameters", {})
        
        if name == "default":
            return True
        
        elif name == "gradualRollout":
            percentage = params.get("rolloutPercentage", 100)
            stickiness_key = params.get("stickiness", "userId")
            
            if not context or stickiness_key not in context:
                return percentage >= 100
            
            # 一致性哈希：同一个 user_id 总是得到相同结果
            value = context[stickiness_key]
            hash_val = int(hashlib.md5(f"{name}:{value}".encode()).hexdigest(), 16)
            bucket = hash_val % 100
            return bucket < percentage
        
        elif name == "specificTenant":
            tenant_ids = params.get("tenantIds", [])
            if context and context.get("tenant_id") in tenant_ids:
                return True
            return False
        
        elif name == "specificUsers":
            user_ids = params.get("userIds", [])
            if context and context.get("user_id") in user_ids:
                return True
            return False
        
        return False


# 使用示例
ff = FeatureFlagClient(redis=redis_client)

async def select_model(request: ChatRequest):
    """根据 Feature Flag 选择模型"""
    context = {
        "user_id": request.user_id,
        "tenant_id": request.tenant_id,
        "session_id": request.session_id,
    }
    
    # 紧急 Kill Switch
    if not await ff.is_enabled("kill_switch_model_glm", context):
        log.info("GLM disabled by kill switch")
        return "qwen-max"
    
    # RAG 功能开关
    if await ff.is_enabled("rag_enabled", context):
        return await do_rag_enhanced_query(request)
    
    return await do_normal_query(request)
```

---

## 3. CI/CD 完整流水线（M-05 补充）

### Pipeline 架构

```yaml
# ci/pipelines/main.yml（GitLab CI 示例）
stages:
  - lint                  # 代码风格检查
  - type-check            # 类型检查
  - unit-test             # 单元测试
  - integration-test      # 集成测试
  - contract-test         # 契约兼容性测试
  - security-scan         # 安全扫描
  - eval-regression       # Gold Set 回归评测
  - build                 # Docker 构建
  - deploy-staging        # 部署预发布
  - smoke-test            # 冒烟测试
  - manual-production     # 生产部署（手动触发）

variables:
  DOCKER_REGISTRY: registry.example.com/agent-platform
  MAVEN_OPTS: "-Dmaven.repo.local=$CI_PROJECT_DIR/.m2/repository"

# ====== Stage 1: Lint ======
lint:java:
  stage: lint
  image: maven:3.9-eclipse-temurin-21
  script:
    - cd services/gateway-java && ./mvnw checkstyle:check spotless:check -q
  only:
    - merge_request_event

lint:python:
  stage: lint
  image: python:3.12-slim
  before_script:
    - pip install ruff
  script:
    - cd services/orchestrator-python && ruff check .
    - cd services/orchestrator-python && ruff format --check .
    - cd services/model-gateway-python && ruff check .
  only:
    - merge_request_event

lint:proto:
  stage: lint
  image: bufbuild/buf:latest
  script:
    - buf lint contracts/proto
    - buf breaking --against 'main' contracts/proto
  only:
    - merge_request_event

# ====== Stage 2: Type Check ======
type-check:python:
  stage: type-check
  image: python:3.12-slim
  before_script:
    - pip install mypy pyright
  script:
    - cd services/orchestrator-python && mypy app/ --strict || true
    - cd services/orchestrator-python && pyright app/ || true
  allow_failure: true  # 初期允许类型错误，逐步修复

# ====== Stage 3: Unit Test ======
test:java:
  stage: unit-test
  image: maven:3.9-eclipse-temurin-21
  services:
    - name: postgres:16-alpine
      alias: db
    - name: redis:7-alpine
      alias: redis
  variables:
    SPRING_DATASOURCE_URL: jdbc:postgresql://db:5432/test_db
    REDIS_HOST: redis
  script:
    - cd services/gateway-java && ./mvnw test -q
  coverage: '/Total.*?([0-9]{1,3})%/'
  artifacts:
    reports:
      junit: "**/target/surefire-reports/TEST-*.xml"

test:python:
  stage: unit-test
  image: python:3.12-slim
  before_script:
    - pip install pytest pytest-cov pytest-asyncio
  services:
    - postgres:16-alpine
    - redis:7-alpine
  script:
    - cd services/orchestrator-python && uv run pytest tests/unit/ -v --cov=app --cov-report=xml --tb=short
  coverage: '/TOTAL\s+\d+\s+\d+\s+(\d+%)/'
  artifacts:
    reports:
      junit: orchestrator-python/reports/junit.xml
      cobertura: orchestrator-python/coverage.xml

# ====== Stage 4: Integration Test ======
integration-test:
  stage: integration-test
  image: docker:24-dind
  services:
    - docker:24-dind
  variables:
    DOCKER_TLS_CERTDIR: "/certs"
  script:
    - docker compose -f infra/docker-compose.test.yml up -d --build
    - sleep 30  # 等待所有服务启动
    - docker compose -f infra/docker-compose.test.yml exec -T test-runner python scripts/run_integration_tests.py
  after_script:
    - docker compose -f infra/docker-compose.test.yml down -v
  only:
    - main
    - develop
  timeout: 15m

# ====== Stage 5: Contract Test ======
contract-test:
  stage: contract-test
  image: bufbuild/buf:latest
  script:
    - buf breaking --against 'main' contracts/proto
    - buf lint contracts/proto
  after_script:
    - spectral lint contracts/openapi/*.yaml --ruleset .spectral.yaml
  only:
    - merge_request_event

# ====== Stage 6: Security Scan ======
security-scan:
  stage: security-scan
  image: securecodebox/scb-cli:latest
  script:
    - trivy fs --severity HIGH,CRITICAL --exit-code 1 .
    - gitleaks detect --source . --verbose || true
  allow_failure: true
  artifacts:
    paths:
      - trivy-report.json
      - gitleaks-report.json
  only:
    - main
    - develop

# ====== Stage 7: Eval Regression ======
eval-regression:
  stage: eval-regression
  image: python:3.12-slim
  before_script:
    - pip install openai requests pandas
  script:
    - python shared/evals/scripts/run_regression_eval.py \
        --gold-set shared/evals/gold-set/ \
        --endpoint http://model-gateway:8001/v1/chat/completions \
        --output reports/eval_report.json \
        --threshold-json-rate 99.0
  artifacts:
    paths:
      - reports/eval_report.json
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"  # 仅定时任务执行
  allow_failure: true  # 评测不阻塞部署，但生成报告供 review

# ====== Stage 8: Build Docker ======
build:gateway:
  stage: build
  image: docker:24-dind
  services:
    - docker:24-dind
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $DOCKER_REGISTRY
    - docker build -t $DOCKER_REGISTRY/gateway:$CI_COMMIT_SHA -f services/gateway-java/Dockerfile services/gateway-java/
    - docker push $DOCKER_REGISTRY/gateway:$CI_COMMIT_SHA
  only:
    - main
    - develop

build:orchestrator:
  stage: build
  image: docker:24-dind
  services:
    - docker:24-dind
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $DOCKER_REGISTRY
    - docker build -t $DOCKER_REGISTRY/orchestrator:$CI_COMMIT_SHA -f services/orchestrator-python/Dockerfile services/orchestrator-python/
    - docker push $DOCKER_REGISTRY/orchestrator:$CI_COMMIT_SHA
  only:
    - main
    - develop

# ... 其他服务的 build job 类似 ...

# ====== Stage 9: Deploy Staging ======
deploy:staging:
  stage: deploy-staging
  image: bitnami/kubectl:latest
  script:
    - kubectl config use-context staging
    - kubectl set image deployment/gateway gateway=$DOCKER_REGISTRY/gateway:$CI_COMMIT_SHA -n agent-platform
    - kubectl set image deployment/orchestrator orchestrator=$DOCKER_REGISTRY/orchestrator:$CI_COMMIT_SHA -n agent-platform
    - kubectl rollout status deployment/gateway -n agent-platform --timeout=300s
    - kubectl rollout status deployment/orchestrator -n agent-platform --timeout=300s
  environment:
    name: staging
    url: https://staging.agent-platform.example.com
  only:
    - develop
  when: manual  # 手动触发

# ====== Stage 10: Smoke Test ======
smoke-test:
  stage: smoke-test
  image: curlimages/curl:latest
  script:
    # 健康检查
    - curl -sf https://staging.agent-platform.example.com/health | jq .
    # 简单对话测试
    - curl -sf -X POST https://staging.agent-platform.example.com/api/v1/chat/completions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TEST_TOKEN" \
        -d '{"message":"hello"}' | jq '.choices[0].message.content'
  environment:
    name: staging
  needs: ["deploy:staging"]

# ====== Stage 11: Production Deploy (Manual) ======
deploy:production:
  stage: manual-production
  image: bitnami/kubectl:latest
  script:
    - kubectl config use-context production
    - kubectl set image deployment/gateway gateway=$DOCKER_REGISTRY/gateway:$CI_COMMIT_SHA -n agent-platform
    - kubectl set image deployment/orchestrator orchestrator=$DOCKER_REGISTRY/orchestrator:$CI_COMMIT_SHA -n agent-platform
    - kubectl rollout status deployment/gateway -n agent-platform --timeout=600s
    - kubectl rollout status deployment/orchestrator -n agent-platform --timeout=600s
  environment:
    name: production
    url: https://api.agent-platform.example.com
  only:
    - main
  when: manual
  allow_failure: false
```

---

## 4. Graceful Shutdown（优雅停机）

### Python 服务 Shutdown Handler

```python
# orchestrator-python/app/core/shutdown.py
"""优雅停机处理。确保：停止接收新请求 → 等待进行中请求完成 → 刷新缓冲区 → 关闭连接"""

from __future__ import annotations

import asyncio
import signal
import sys

import structlog

logger = structlog.get_logger()


class GracefulShutdown:
    """
    优雅停机管理器。
    
    使用方式：
        shutdown = GracefulShutdown()
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown.handle(signal.SIGTERM)))
        loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown.handle(signal.SIGINT)))
    """
    
    def __init__(
        self,
        shutdown_timeout: float = 30.0,
        health_checker=None,
        buffer_flushers: list | None = None,
        connection_closers: list | None = None,
    ):
        self.shutdown_timeout = shutdown_timeout
        self.health_checker = health_checker
        self.buffer_flushers = buffer_flushers or []
        self.connection_closers = connection_closers or []
        self._shutdown_event = asyncio.Event()
    
    async def handle(self, sig):
        """处理 SIGTERM/SIGINT 信号"""
        logger.info("Received shutdown signal", signal=sig.name)
        self._shutdown_event.set()
        
        try:
            # Step 1: 标记不健康（让负载均衡器不再转发流量）
            if self.health_checker:
                await self.health_checker.mark_unhealthy()
                logger.info("Marked unhealthy, no more traffic will be routed here")
            
            # Step 2: 等待进行中的请求完成
            logger.info("Waiting for in-flight requests...", timeout=self.shutdown_timeout)
            try:
                await asyncio.wait_for(
                    self._wait_for_inflight_requests(),
                    timeout=self.shutdown_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for in-flight requests, forcing shutdown")
            
            # Step 3: 刷新 buffered data
            logger.info("Flushing buffers...")
            for flusher in self.buffer_flushers:
                try:
                    if hasattr(flusher, 'flush'):
                        await flusher.flush()
                    elif callable(flusher):
                        await flusher()
                except Exception as e:
                    logger.error("Failed to flush buffer", error=str(e))
            
            # Step 4: 关闭连接池
            logger.info("Closing connections...")
            for closer in self.connection_closers:
                try:
                    if hasattr(closer, 'close'):
                        await closer.close()
                    elif callable(closer):
                        await closer()
                except Exception as e:
                    logger.error("Failed to close connection", error=str(e))
            
            logger.info("Graceful shutdown complete")
        
        finally:
            sys.exit(0)
    
    async def _wait_for_inflight_requests(self):
        """等待进行中的请求完成。
        
        实际实现需要跟踪活跃请求数量。
        这里用简单的 sleep + event 替代。
        """
        # 在实际 FastAPI 中可以通过 middleware 计数 active connections
        # 这里简化处理
        await asyncio.sleep(2)  # 给现有请求 2 秒时间完成


# 注册到 FastAPI 应用
# main.py
from app.core.shutdown import GracefulShutdown

def create_app() -> FastAPI:
    app = FastAPI(title="Agent Orchestrator")
    
    shutdown = GracefulShutdown(
        shutdown_timeout=30.0,
        buffer_flushers=[step_buffer],  # 如果有的话
        connection_closers=[db_pool, redis_pool],
    )
    
    # 注册信号处理器（需要在事件循环启动后）
    @app.on_event("startup")
    def setup_signal_handlers():
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(
            signal.SIGTERM,
            lambda: asyncio.create_task(shutdown.handle(signal.SIGTERM)),
        )
        loop.add_signal_handler(
            signal.SIGINT,
            lambda: asyncio.create_task(shutdown.handle(signal.SIGINT)),
        )
    
    return app
```

### Java 服务 Shutdown Hook

```java
// gateway-java/src/main/java/com/platform/gateway/config/GracefulShutdownConfig.java
@Configuration
public class GracefulShutdownConfig {

    @Bean
    public TomcatServletWebServerFactory servletContainer() {
        TomcatServletWebServerFactory factory = new TomcatServletWebServerFactory();
        factory.configure(connector -> {
            // 优雅停机超时：30秒
            connector.setProperty("gracefulShutdown", "true");
        });
        return factory;
    }

    @PreDestroy
    public void onShutdown() {
        // 1. 健康检查端点返回非 200（让 K8s 移除 Pod 流量）
        HealthChecker.markUnhealthy();
        
        // 2. 等待进行中请求完成（Tomcat gracefulShutdown 已处理）
        
        // 3. 刷新 Kafka Producer 缓冲区
        kafkaProducer.flush();
        
        // 4. 关闭连接池
        dataSource.close();
        
        log.info("Gateway shutdown complete");
    }
}
```

---

## 5. 服务发现与注册

### 方案：K8s Service + Istio ServiceEntry

对于 K8s 内部部署的服务，使用原生 K8s Service 发现：

```yaml
# infra/kubernetes/services/gateway-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: gateway
  namespace: agent-platform
  labels:
    app: gateway
spec:
  selector:
    app: gateway
  ports:
    - name: http
      port: 8080
      targetPort: 8080
    - name: grpc
      port: 50051
      targetPort: 50051
  type: ClusterIP  # 仅集群内部访问

---
apiVersion: v1
kind: Service
metadata:
  name: tool-bus
  namespace: agent-platform
spec:
  selector:
    app: tool-bus
  ports:
    - name: grpc
      port: 50051
      targetPort: 50051
  type: ClusterIP
```

### Python 侧服务发现客户端

```python
# orchestrator-python/app/core/service_discovery.py
"""K8s 原生服务发现。

通过 DNS 解析 K8s Service 名获取后端地址。
Istio Sidecar 会自动处理负载均衡和 mTLS。
"""

from __future__ import annotations


class KubernetesServiceDiscovery:
    """K8s DNS-based service discovery.
    
    使用方式:
        svc = KubernetesServiceDiscovery()
        addr = svc.resolve("tool-bus")  # => ("tool-bus.agent-platform.svc.cluster.local", 50051)
    """
    
    NAMESPACE = "agent-platform"
    
    def resolve(self, service_name: str, default_port: int | None = None) -> tuple[str, int]:
        """
        解析服务地址。
        
        Args:
            service_name: K8s Service 名称（不含命名空间前缀）
            default_port: 默认端口（如果 DNS SRV 记录无端口信息）
        
        Returns:
            (host, port) 元组
        """
        fqdn = f"{service_name}.{self.NAMESPACE}.svc.cluster.local"
        
        # 默认端口映射
        port_map = {
            "gateway": 8080,
            "orchestrator": 8000,
            "model-gateway": 8001,
            "tool-bus": 50051,
            "governance": 50052,
            "knowledge": 8081,
        }
        
        port = port_map.get(service_name, default_port or 8080)
        return (fqdn, port)


# gRPC Channel 创建
def get_tool_bus_channel():
    discovery = KubernetesServiceDiscovery()
    host, port = discovery.resolve("tool-bus")
    
    import grpc
    channel_options = [
        ('grpc.max_concurrent_streams', 100),
        ('grpc.keepalive_time_ms', 60000),
        ('grpc.keepalive_timeout_ms', 20000),
    ]
    
    channel = grpc.insecure_channel(f"{host}:{port}", options=channel_options)
    return channel
```

---

## 6. 三级健康检查（v2.1 新增）

### 实现位置

`services/orchestrator-python/app/core/health_checker.py`
`services/orchestrator-python/app/api/v1/health.py`

### 端点设计

| 端点 | 用途 | Kubernetes 探针 | 检查内容 |
|------|------|-----------------|----------|
| `/health/live` | 存活检查 | livenessProbe | 进程存活 |
| `/health/ready` | 就绪检查 | readinessProbe | Redis + ModelGateway |
| `/health/deep` | 深度检查 | 无 | Redis + ModelGateway + ToolBus + Database |

### 状态枚举

```python
class HealthStatus(str, Enum):
    HEALTHY = "healthy"     # 健康
    DEGRADED = "degraded"   # 降级（部分依赖不可用）
    UNHEALTHY = "unhealthy" # 不健康（关键依赖不可用）
```

### Kubernetes 探针配置

```yaml
# deployment.yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 3
```

### 检查逻辑

```python
async def check_readiness(self) -> tuple[bool, dict]:
    """检查就绪状态"""
    redis_health = await self.check_redis()
    model_health = await self.check_model_gateway()

    is_ready = (
        redis_health.status != HealthStatus.UNHEALTHY
        and model_health.status != HealthStatus.UNHEALTHY
    )

    return is_ready, {
        "redis": redis_health.status.value,
        "model_gateway": model_health.status.value,
    }
```

---

## 7. Prometheus Metrics（v2.1 新增）

### 实现位置

`services/orchestrator-python/app/core/metrics.py`

### 暴露端点

```bash
curl http://localhost:8000/metrics
```

### 指标分类

| 类别 | 指标名 | 类型 | 说明 |
|------|--------|------|------|
| **请求** | `orchestrator_request_total` | Counter | 总请求数 |
| | `orchestrator_request_latency_seconds` | Histogram | 请求延迟 |
| | `orchestrator_requests_in_progress` | Gauge | 进行中请求数 |
| **模型** | `model_call_total` | Counter | 模型调用总数 |
| | `model_call_latency_seconds` | Histogram | 模型调用延迟 |
| | `model_calls_in_progress` | Gauge | 进行中模型调用数 |
| **工具** | `tool_call_total` | Counter | 工具调用总数 |
| | `tool_call_latency_seconds` | Histogram | 工具调用延迟 |
| **熔断器** | `circuit_breaker_state` | Gauge | 熔断器状态 (0=closed, 1=open, 2=half-open) |
| | `circuit_breaker_failures_total` | Counter | 熔断器失败总数 |
| **缓存** | `cache_hits_total` | Counter | 缓存命中数 |
| | `cache_misses_total` | Counter | 缓存未命中数 |
| | `cache_size` | Gauge | 当前缓存大小 |
| **Agent** | `agent_run_total` | Counter | Agent 运行总数 |
| | `agent_step_count` | Histogram | 每次运行步骤数 |
| | `agent_run_latency_seconds` | Histogram | Agent 运行延迟 |

### 延迟 Bucket 配置

```python
# 模型调用延迟 buckets
MODEL_LATENCY = Histogram(
    "model_call_latency_seconds",
    "Model call latency",
    buckets=[5, 10, 15, 20, 30, 45, 60, 90, 120],
)

# 请求延迟 buckets
REQUEST_LATENCY = Histogram(
    "orchestrator_request_latency_seconds",
    "Request latency",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)
```

### Grafana Dashboard 查询示例

```promql
# P99 请求延迟
histogram_quantile(0.99, rate(orchestrator_request_latency_seconds_bucket[5m]))

# 模型调用成功率
sum(rate(model_call_total{status="success"}[5m])) 
/ sum(rate(model_call_total[5m]))

# 缓存命中率
sum(rate(cache_hits_total[5m])) 
/ (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))

# 熔断器状态
circuit_breaker_state{service="model_gateway"}
```

---

## 8. 缓存管理器（v2.1 新增）

### 实现位置

`services/orchestrator-python/app/core/cache.py`

### 初始化

```python
# main.py
from app.core.cache import init_cache_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = Redis.from_url(config.redis_url)
    init_cache_manager(redis_client)
    ...
```

### 使用示例

```python
from app.core.cache import get_cache_manager

# RAG 缓存
rag_cache = get_cache_manager().get_rag_cache()
result = await rag_cache.get_or_set(
    DualLayerCache._hash_key(query),
    lambda: await rag_retrieve(query),
)

# 工具 Schema 缓存
schema_cache = get_cache_manager().get_tool_schema_cache()
schema = await schema_cache.get_or_set(
    f"schema:{tool_name}",
    lambda: await fetch_tool_schema(tool_name),
)
```

### 统计查询

```python
stats = get_cache_manager().get_all_stats()
# {
#   "rag": {"hit_count": 100, "miss_count": 50, "hit_rate": 0.67},
#   "tool_schema": {"hit_count": 80, "miss_count": 20, "hit_rate": 0.80},
# }
```
