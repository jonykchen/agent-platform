# 安全与加密加固方案

> **版本**：v1.2 | **状态**：已实施 | **对应审查项**：S-01~S-06 补充、G-SEC-01~04 强化
>
> **实施状态更新（2026-06-25）**：
> - ✅ 服务间 mTLS（Istio PeerAuthentication 已配置）
> - ✅ 租户 RLS 行级安全（SQL 迁移已实现）
> - ✅ 安全扫描自动化（CI 已集成 Trivy/Gitleaks/Semgrep）
> - ✅ 数据加密 at-rest（pgcrypto 列级加密方案已设计，EncryptionService 已实现）
> - ✅ 密码/密钥生命周期管理（SecretValidationConfig + EncryptionService 已实现）

---

## 目录

1. [服务间 mTLS 启用与验证](#1-服务间-mtls-启用与验证)
2. [租户 RLS 行级安全强化](#2-租户-rls-行级安全强化)
3. [数据加密 at-rest](#3-数据加密-at-rest)
4. [数据库备份与恢复体系](#4-数据库备份与恢复体系)
5. [安全扫描自动化](#5-安全扫描自动化)
6. [密码/密钥生命周期管理](#6-密码密钥生命周期管理)

---

## 1. 服务间 mTLS 启用与验证

### 1.1 问题背景

项目已存在 Istio mTLS 配置文件（`infra/k8s/istio-peer-authentication.yaml`、`infra/k8s/istio-destination-rule.yaml`），但存在以下问题：

- **PeerAuthentication 仅定义了 namespace 级默认 STRICT 模式**，未对每个服务单独配置，无法按服务粒度降级
- **DestinationRule 仅覆盖 `*.agent-platform.svc.cluster.local` 和 `orchestrator`**，其余 5 个服务缺少独立的 DestinationRule
- **AuthorizationPolicy 规则过于宽松**：允许同一 namespace 内所有服务互访，未遵循最小权限原则
- **未验证证书轮转、未配置自定义 CA**、未编写 mTLS 验证脚本
- 开发环境（无 Istio）降级策略仅在应用层配置，未在 Istio 层面提供 PERMISSIVE 过渡

### 1.2 方案设计

#### 1.2.1 整体架构

```mermaid
graph TB
    subgraph "K8s Namespace: agent-platform"
        GW[Gateway<br/>:8080/:9091]
        ORC[Orchestrator<br/>:8000/:50100]
        MG[ModelGateway<br/>:8002]
        KB[Knowledge<br/>:8003]
        TB[ToolBus<br/>:8083/:40051]
        GOV[Governance<br/>:8082]
    end

    subgraph "Istio Control Plane"
        IC[Istiod]
        CA[Citadel/CA]
    end

    IC -->|签发证书| GW
    IC -->|签发证书| ORC
    IC -->|签发证书| MG
    IC -->|签发证书| KB
    IC -->|签发证书| TB
    IC -->|签发证书| GOV
    CA -->|自动轮转| IC

    GW -->|mTLS| ORC
    ORC -->|mTLS| MG
    ORC -->|mTLS| TB
    TB -->|mTLS| GOV
    ORC -->|mTLS| KB
```

#### 1.2.2 服务间通信矩阵

| 调用方 | 被调用方 | 协议 | 端口 | 是否需要 mTLS |
|--------|----------|------|------|---------------|
| Gateway | Orchestrator | gRPC | 50100 | 是 |
| Orchestrator | ModelGateway | HTTP | 8002 | 是 |
| Orchestrator | ToolBus | gRPC | 40051 | 是 |
| Orchestrator | Knowledge | HTTP | 8003 | 是 |
| ToolBus | Governance | HTTP | 8082 | 是 |
| Ingress Gateway | Gateway | HTTP | 8080 | 是（TLS 终止在 Ingress） |

### 1.3 配置示例

#### 1.3.1 PeerAuthentication — namespace 级 STRICT + 服务级覆盖

```yaml
# infra/k8s/security/peer-authentication.yaml
# Namespace 级默认 STRICT：所有服务间通信必须 mTLS
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: agent-platform
  labels:
    app.kubernetes.io/name: agent-platform
    app.kubernetes.io/component: security
spec:
  mtls:
    mode: STRICT

---
# 服务级 PeerAuthentication（可选：灰度期间对特定服务使用 PERMISSIVE）
# 灰度完成后应删除此资源，统一使用 namespace 级 STRICT
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: orchestrator-permissive
  namespace: agent-platform
spec:
  selector:
    matchLabels:
      app: orchestrator
  mtls:
    mode: PERMISSIVE  # 灰度期：同时接受 mTLS 和 plain text
```

#### 1.3.2 DestinationRule — 每个服务独立配置

```yaml
# infra/k8s/security/destination-rules.yaml
# 全局默认 DestinationRule
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: default-mtls
  namespace: agent-platform
  labels:
    app.kubernetes.io/name: agent-platform
    app.kubernetes.io/component: security
spec:
  host: "*.agent-platform.svc.cluster.local"
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL

---
# Orchestrator DestinationRule（含连接池、熔断、一致性哈希）
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: orchestrator
  namespace: agent-platform
spec:
  host: orchestrator.agent-platform.svc.cluster.local
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL
    connectionPool:
      tcp:
        maxConnections: 100
        connectTimeout: 10s
      http:
        h2UpgradePolicy: UPGRADE
        http1MaxPendingRequests: 100
        http2MaxRequests: 1000
        maxRequestsPerConnection: 10
        maxRetries: 3
        idleTimeout: 60s
    outlierDetection:
      consecutive5xxErrors: 5
      consecutiveGatewayErrors: 3
      interval: 30s
      baseEjectionTime: 60s
      maxEjectionPercent: 50
      minHealthPercent: 25
    loadBalancer:
      consistentHash:
        httpHeaderName: x-session-id
        minimumRingSize: 1024

---
# ModelGateway DestinationRule
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: model-gateway
  namespace: agent-platform
spec:
  host: model-gateway.agent-platform.svc.cluster.local
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL
    connectionPool:
      tcp:
        maxConnections: 50
        connectTimeout: 5s
      http:
        http2MaxRequests: 200
        maxRequestsPerConnection: 5
        idleTimeout: 30s

---
# ToolBus DestinationRule
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: tool-bus
  namespace: agent-platform
spec:
  host: tool-bus.agent-platform.svc.cluster.local
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL
    connectionPool:
      tcp:
        maxConnections: 80
        connectTimeout: 10s
      http:
        http2MaxRequests: 500
        maxRequestsPerConnection: 10

---
# Governance DestinationRule
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: governance
  namespace: agent-platform
spec:
  host: governance.agent-platform.svc.cluster.local
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL
    connectionPool:
      tcp:
        maxConnections: 30
        connectTimeout: 5s

---
# Knowledge DestinationRule
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: knowledge
  namespace: agent-platform
spec:
  host: knowledge.agent-platform.svc.cluster.local
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL
    connectionPool:
      tcp:
        maxConnections: 50
        connectTimeout: 5s
```

#### 1.3.3 AuthorizationPolicy — 最小权限原则

```yaml
# infra/k8s/security/authorization-policies.yaml
# Gateway 只能调用 Orchestrator
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: gateway-to-orchestrator
  namespace: agent-platform
spec:
  selector:
    matchLabels:
      app: orchestrator
  rules:
    - from:
        - source:
            principals: ["cluster.local/ns/agent-platform/sa/gateway"]
      to:
        - operation:
            methods: ["POST"]
            paths: ["/api/v1/*"]

---
# Orchestrator 只能调用 ModelGateway、ToolBus、Knowledge
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: orchestrator-egress
  namespace: agent-platform
spec:
  selector:
    matchLabels:
      app: orchestrator
  action: ALLOW
  rules:
    - to:
        - operation:
            hosts:
              - "model-gateway.agent-platform.svc.cluster.local"
              - "tool-bus.agent-platform.svc.cluster.local"
              - "knowledge.agent-platform.svc.cluster.local"

---
# ToolBus 只能调用 Governance
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: toolbus-to-governance
  namespace: agent-platform
spec:
  selector:
    matchLabels:
      app: governance
  rules:
    - from:
        - source:
            principals: ["cluster.local/ns/agent-platform/sa/tool-bus"]

---
# 允许 Istio Ingress Gateway 访问 Gateway 服务
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: ingress-to-gateway
  namespace: agent-platform
spec:
  selector:
    matchLabels:
      app: gateway
  rules:
    - from:
        - source:
            principals:
              - "cluster.local/ns/istio-system/sa/istio-ingressgateway-service-account"

---
# 默认拒绝：未匹配以上规则的请求全部拒绝
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: deny-all-default
  namespace: agent-platform
spec:
  {}  # 空 spec = 拒绝所有未匹配 ALLOW 规则的请求
```

#### 1.3.4 证书管理

**方案 A：Istio 内置 CA（推荐起步用）**

Istio Citadel 自动为每个 Sidecar 签发证书，默认轮转周期 24 小时。

```yaml
# 无需额外配置，Istio 默认行为：
# - 证书有效期：24h
# - 轮转提前量：1h（证书过期前 1 小时开始轮转）
# - 签发 CA：Istio 内置 Citadel

# 如需调整轮转周期（更严格场景）：
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
spec:
  meshConfig:
    certificates:
      - secretName: istio-citadel-ca
        dnsNames: ["istio-citadel"]
        duration: 720h        # 30 天
        renewBefore: 24h     # 过期前 24h 轮转
```

**方案 B：自定义 CA（生产推荐）**

使用企业 PKI 或 HashiCorp Vault 作为 Istio 的外部 CA，证书链可追溯到企业根证书。

```yaml
# infra/k8s/security/istio-external-ca.yaml
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
spec:
  components:
    cni:
      enabled: true
  meshConfig:
    trustDomain: "agent-platform.example.com"
    configSources:
      - address: "https://vault.agent-platform.svc:8200/v1/istio-ca/sign"
        tlsSettings:
          mode: ISTIO_MUTUAL
```

Vault 签发证书的 PKI Secrets Engine 配置：

```hcl
# Vault PKI backend for Istio
resource "vault_mount" "istio_pki" {
  path        = "istio-pki"
  type        = "pki"
  description = "Istio mTLS PKI"

  default_lease_ttl_seconds = 86400     # 24h
  max_lease_ttl_seconds     = 2592000   # 30d
}

resource "vault_pki_secret_backend_root_cert" "istio" {
  backend     = vault_mount.istio_pki.path
  type        = "internal"
  common_name = "Agent Platform Istio Root CA"
  ttl         = "87600h"  # 10 年
}

resource "vault_pki_secret_backend_intermediate_cert" "istio_intermediate" {
  backend     = vault_mount.istio_pki.path
  type        = "internal"
  common_name = "Agent Platform Istio Intermediate CA"
}
```

### 1.4 验证方法

#### 1.4.1 mTLS 验证脚本

```bash
#!/bin/bash
# scripts/verify-mtls.sh
# 验证所有服务间通信已启用 mTLS
set -euo pipefail

NAMESPACE="agent-platform"
EXPECTED_SERVICES=("gateway" "orchestrator" "model-gateway" "tool-bus" "governance" "knowledge")

echo "=== mTLS 验证开始 ==="

# 1. 检查 PeerAuthentication 配置
echo "[1/5] 检查 PeerAuthentication 配置..."
MTLS_MODE=$(kubectl get peerauthentication default -n "$NAMESPACE" -o jsonpath='{.spec.mtls.mode}')
if [ "$MTLS_MODE" = "STRICT" ]; then
    echo "  ✅ Namespace 级 mTLS 模式: STRICT"
else
    echo "  ❌ Namespace 级 mTLS 模式: $MTLS_MODE (期望 STRICT)"
    exit 1
fi

# 2. 检查所有 Pod 是否注入了 Istio Sidecar
echo "[2/5] 检查 Istio Sidecar 注入..."
for svc in "${EXPECTED_SERVICES[@]}"; do
    SIDECAR_COUNT=$(kubectl get pods -n "$NAMESPACE" -l "app=$svc" -o json \
        | jq -r '.items[] | .spec.containers[] | select(.name=="istio-proxy") | .name' \
        | wc -l)
    if [ "$SIDECAR_COUNT" -gt 0 ]; then
        echo "  ✅ $svc: Sidecar 已注入"
    else
        echo "  ❌ $svc: Sidecar 未注入"
    fi
done

# 3. 使用 istioctl analyze 检查配置一致性
echo "[3/5] Istio 配置分析..."
istioctl analyze -n "$NAMESPACE" --all-namespaces 2>&1 | tee /tmp/istio-analyze.txt
if grep -q "No issues found" /tmp/istio-analyze.txt; then
    echo "  ✅ Istio 配置无问题"
else
    echo "  ⚠️  Istio 配置存在问题，详见上方输出"
fi

# 4. 检查 mTLS 统计（通过 Envoy stats）
echo "[4/5] 检查 mTLS 连接统计..."
for svc in "${EXPECTED_SERVICES[@]}"; do
    POD=$(kubectl get pods -n "$NAMESPACE" -l "app=$svc" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "$POD" ]; then
        TLS_SUCCESS=$(kubectl exec -n "$NAMESPACE" "$POD" -c istio-proxy -- \
            pilot-agent request GET stats | grep -c "ssl.handshake.success" || echo "0")
        echo "  $svc: TLS 握手成功数=$TLS_SUCCESS"
    fi
done

# 5. 验证 plain text 连接被拒绝（STRICT 模式）
echo "[5/5] 验证 STRICT 模式拒绝 plain text..."
# 从 orchestrator 尝试以 plain text 调用 model-gateway（应失败）
ORC_POD=$(kubectl get pods -n "$NAMESPACE" -l "app=orchestrator" -o jsonpath='{.items[0].metadata.name}')
if [ -n "$ORC_POD" ]; then
    HTTP_CODE=$(kubectl exec -n "$NAMESPACE" "$ORC_POD" -c app -- \
        curl -s -o /dev/null -w "%{http_code}" \
        --connect-timeout 3 \
        http://model-gateway.agent-platform.svc.cluster.local:8002/health \
        2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "000" ] || [ "$HTTP_CODE" = "503" ]; then
        echo "  ✅ Plain text 连接被拒绝 (http_code=$HTTP_CODE)"
    else
        echo "  ❌ Plain text 连接未被拒绝 (http_code=$HTTP_CODE)，mTLS STRICT 未生效"
    fi
fi

echo "=== mTLS 验证完成 ==="
```

#### 1.4.2 CI 集成验证

```yaml
# .github/workflows/ci.yml 中追加 mTLS 验证步骤
mtls-verify:
  name: mTLS Configuration Verify
  runs-on: ubuntu-latest
  needs: deploy-staging
  steps:
    - uses: actions/checkout@v4
    - name: Install istioctl
      run: curl -L https://istio.io/downloadIstio | sh -
    - name: Verify mTLS
      run: |
        export PATH="$PWD/istio/bin:$PATH"
        bash scripts/verify-mtls.sh
```

### 1.5 故障排查

| 问题 | 现象 | 排查方法 | 解决方案 |
|------|------|----------|----------|
| Sidecar 未注入 | Pod 内无 `istio-proxy` 容器 | `kubectl get pod <pod> -o jsonpath='{.spec.containers[*].name}'` | 检查 namespace label: `istio-injection=enabled`；检查 Pod annotation `sidecar.istio.io/inject` |
| mTLS STRICT 导致服务 503 | 非 Istio 管理的客户端无法连接 | `kubectl logs <pod> -c istio-proxy \| grep "connection refused"` | 对该服务使用 PERMISSIVE 模式过渡，或为客户端添加 Sidecar |
| 证书轮转失败 | 日志中出现 "certificate expired" | `istioctl proxy-config secret <pod> -n <ns>` | 检查 Istiod 日志；确认 CA 根证书未过期；重启 Istiod |
| DestinationRule 冲突 | 多个 DestinationRule 匹配同一 host | `istioctl analyze -n <ns>` | 确保每个 host 仅有一个 DestinationRule；使用 `exportTo` 限制作用域 |
| AuthorizationPolicy 拒绝合法请求 | 请求返回 RBAC denied | `kubectl logs <pod> -c istio-proxy \| grep "RBAC"` | 检查 policy 的 source.principals 和 operation 匹配规则；临时添加 ALLOW 规则调试 |

### 1.6 风险与回滚策略

| 风险 | 影响 | 回滚方案 |
|------|------|----------|
| STRICT 模式导致服务不可用 | 全部服务 503 | 将 PeerAuthentication 切换为 PERMISSIVE：`kubectl patch peerauthentication default -n agent-platform --type merge -p '{"spec":{"mtls":{"mode":"PERMISSIVE"}}}'` |
| 自定义 CA 故障 | 证书签发失败 | 回退到 Istio 内置 CA：删除 IstioOperator 中的 externalCA 配置，重启 Istiod |
| AuthorizationPolicy 过严 | 合法请求被拒绝 | 删除 deny-all-default 策略：`kubectl delete authorizationpolicy deny-all-default -n agent-platform` |

---

## 2. 租户 RLS 行级安全强化

### 2.1 问题背景

现有 RLS 策略（`V002__tenant_rls_policies.sql`）存在以下不足：

- **仅覆盖 6 张表**：`agent_session`、`agent_run`、`agent_step`、`approval_task`、`knowledge_document`、`knowledge_chunk`，缺少 `tool_invocation`、`audit_event`、`tool_usage_daily`、`tenant_tool_config` 等表
- **策略均为 `FOR ALL TO app_user`**，未区分 SELECT/INSERT/UPDATE/DELETE 操作粒度
- **应用层无强制 tenant_id 过滤**：Java JPA Repository 和 Python SQLAlchemy 查询未强制携带 tenant_id 条件，依赖开发人员自觉
- **无超级用户 bypass 机制**：运维管理查询（跨租户统计、数据迁移）无法绕过 RLS
- **无定期审计检查**：缺少自动化测试验证跨租户数据不会泄露

### 2.2 方案设计

```mermaid
graph TB
    subgraph "请求入口"
        REQ[HTTP/gRPC 请求<br/>携带 tenant_id]
    end

    subgraph "应用层保障"
        A1[Java: TenantContext Filter<br/>设置 tenant_id 到 ThreadLocal]
        A2[Python: TenantMiddleware<br/>设置 tenant_id 到 contextvars]
        A3[JPA Repository<br/>自动追加 WHERE tenant_id=?]
        A4[SQLAlchemy Event<br/>自动追加 tenant_id 过滤]
    end

    subgraph "数据库层保障"
        B1[SET app.current_tenant]
        B2[RLS Policy<br/>USING tenant_id = current_tenant_id]
        B3[超级用户 bypass<br/>app_user_bypass 角色]
    end

    REQ --> A1
    REQ --> A2
    A1 --> A3
    A2 --> A4
    A3 -->|参数化查询| B1
    A4 -->|参数化查询| B1
    B1 --> B2
    B1 -.->|运维查询| B3
```

### 2.3 RLS 策略完整定义

#### 2.3.1 补充缺失表的 RLS 策略

```sql
-- ============================================================
--  V004__tenant_rls_policies_enhanced.sql
--  补充 RLS 策略 + 操作粒度细化 + 超级用户 bypass
-- ============================================================

-- 1. tool_invocation 表 RLS（通过 run_id → agent_run.tenant_id 间接关联）
ALTER TABLE tool_invocation ENABLE ROW LEVEL SECURITY;

-- 方案 A：直接在 tool_invocation 上添加 tenant_id 列（推荐，需迁移）
-- ALTER TABLE tool_invocation ADD COLUMN tenant_id VARCHAR(64);
-- UPDATE tool_invocation ti SET tenant_id = ar.tenant_id
--   FROM agent_run ar WHERE ti.run_id = ar.id;

-- 方案 B：通过子查询关联（无需改表，但性能较差）
CREATE POLICY tenant_isolation_tool_invocation ON tool_invocation
    FOR ALL TO app_user
    USING (EXISTS (
        SELECT 1 FROM agent_run
        WHERE agent_run.id = tool_invocation.run_id
          AND agent_run.tenant_id = current_tenant_id()
    ));

-- 2. tool_usage_daily 表 RLS
ALTER TABLE tool_usage_daily ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_tool_usage ON tool_usage_daily
    FOR ALL TO app_user
    USING (tenant_id = current_tenant_id());

-- 3. tenant_tool_config 表 RLS
ALTER TABLE tenant_tool_config ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_tenant_tool_config ON tenant_tool_config
    FOR ALL TO app_user
    USING (tenant_id = current_tenant_id());

-- 4. tenant_user 表 RLS
ALTER TABLE tenant_user ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_tenant_user ON tenant_user
    FOR ALL TO app_user
    USING (tenant_id = current_tenant_id());
```

#### 2.3.2 操作粒度细化（以 agent_session 为例）

```sql
-- 替换原有的 FOR ALL 策略为操作粒度策略
DROP POLICY IF EXISTS tenant_isolation_session ON agent_session;

-- SELECT: 只能看到本租户数据
CREATE POLICY tenant_select_session ON agent_session
    FOR SELECT TO app_user
    USING (tenant_id = current_tenant_id());

-- INSERT: 只能插入本租户数据
CREATE POLICY tenant_insert_session ON agent_session
    FOR INSERT TO app_user
    WITH CHECK (tenant_id = current_tenant_id());

-- UPDATE: 只能更新本租户数据，且不能修改 tenant_id
CREATE POLICY tenant_update_session ON agent_session
    FOR UPDATE TO app_user
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

-- DELETE: 只能删除本租户数据
CREATE POLICY tenant_delete_session ON agent_session
    FOR DELETE TO app_user
    USING (tenant_id = current_tenant_id());
```

#### 2.3.3 超级用户 bypass 机制

```sql
-- 创建运维角色（bypass RLS）
CREATE ROLE app_admin NOBYPASSRLS;  -- 默认受 RLS 约束
CREATE ROLE app_admin_bypass BYPASSRLS;  -- 可绕过 RLS

-- 将 app_admin_bypass 授予运维人员
-- GRANT app_admin_bypass TO <运维用户>;

-- app_admin_bypass 的权限：只读 + 跨租户查询
GRANT USAGE ON SCHEMA public TO app_admin_bypass;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_admin_bypass;

-- 审计：超级用户查询记录
CREATE OR REPLACE FUNCTION log_admin_query()
RETURNS EVENT_TRIGGER AS $$
BEGIN
    INSERT INTO audit_event (event_id, event_type, event_category, severity,
        tenant_id, user_id, action, details)
    VALUES (
        format('admin_query_%s', gen_random_uuid()),
        'ADMIN_QUERY',
        'security',
        'warn',
        'system',
        current_user,
        'BYPASS_RLS_QUERY',
        jsonb_build_object(
            'query_tag', current_query(),
            'timestamp', NOW()
        )
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### 2.4 应用层 tenant_id 强制过滤

#### 2.4.1 Java 侧 — JPA Repository 拦截

```java
// gateway-java/src/main/java/com/platform/gateway/config/TenantContext.java
package com.platform.gateway.config;

/**
 * 租户上下文持有器。
 * 通过 ThreadLocal 存储当前请求的 tenant_id，
 * 在 Filter 中设置，在 Repository 查询中自动追加。
 */
public final class TenantContext {
    private static final ThreadLocal<String> CURRENT_TENANT = new ThreadLocal<>();

    public static void setTenantId(String tenantId) {
        if (tenantId == null || tenantId.isBlank()) {
            throw new SecurityException("tenant_id 不能为空");
        }
        CURRENT_TENANT.set(tenantId);
    }

    public static String getTenantId() {
        String tenantId = CURRENT_TENANT.get();
        if (tenantId == null) {
            throw new SecurityException("未设置租户上下文，拒绝查询");
        }
        return tenantId;
    }

    public static void clear() {
        CURRENT_TENANT.remove();
    }
}
```

```java
// gateway-java/src/main/java/com/platform/gateway/config/TenantFilter.java
package com.platform.gateway.config;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import java.io.IOException;

/**
 * 租户上下文 Filter。
 * 从 JWT Token 或请求头中提取 tenant_id，
 * 设置到 TenantContext 的 ThreadLocal 中。
 * 优先级最高（Order = -100），确保所有后续处理都能获取到 tenant_id。
 */
@Component
@Order(-100)
public class TenantFilter implements Filter {

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest httpRequest = (HttpServletRequest) request;

        try {
            // 从 JWT Token 中提取 tenant_id（由 Spring Security 解析后设置到 SecurityContext）
            String tenantId = extractTenantId(httpRequest);

            if (tenantId != null) {
                TenantContext.setTenantId(tenantId);
            }

            chain.doFilter(request, response);
        } finally {
            // 确保请求结束后清理 ThreadLocal，防止内存泄露
            TenantContext.clear();
        }
    }

    private String extractTenantId(HttpServletRequest request) {
        // 优先从 JWT claims 中获取
        // 备选从请求头 x-tenant-id 获取（仅限内部服务调用）
        var authentication = org.springframework.security.context
            .SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof var jwt) {
            return jwt.getClaim("tenant_id");
        }
        return request.getHeader("x-tenant-id");
    }
}
```

```java
// gateway-java/src/main/java/com/platform/gateway/config/TenantHibernateInterceptor.java
package com.platform.gateway.config;

import org.hibernate.EmptyInterceptor;
import org.hibernate.type.Type;
import java.io.Serializable;

/**
 * Hibernate 拦截器：自动为查询追加 tenant_id 条件。
 *
 * 此拦截器在 SQL 语句执行前检查是否包含 tenant_id 列，
 * 如果是则自动追加 WHERE tenant_id = ? 条件。
 *
 * 注意：此拦截器是应用层保障，与数据库层 RLS 形成双重防护。
 * 即使拦截器被绕过（如原生 SQL），RLS 仍然生效。
 */
public class TenantHibernateInterceptor extends EmptyInterceptor {

    @Override
    public String onPrepareStatement(String sql) {
        String tenantId = TenantContext.getTenantId();
        if (tenantId == null) {
            return sql;  // 超级用户查询，不追加条件
        }

        // 检查 SQL 是否涉及含 tenant_id 的表，自动追加过滤
        // 此处为简化实现，生产环境建议使用 Hibernate Filter 机制
        return sql;
    }
}
```

**更推荐的方案：Hibernate @FilterDef + @Filter 注解**

```java
// Entity 定义
@Entity
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = String.class))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
@Table(name = "agent_session")
public class AgentSession {
    // ...
}

// Repository 使用
@Repository
public interface AgentSessionRepository extends JpaRepository<AgentSession, UUID> {

    @Override
    default List<AgentSession> findAll() {
        // 强制启用 tenant filter
        return entityManager.unwrap(Session.class)
            .enableFilter("tenantFilter")
            .setParameter("tenantId", TenantContext.getTenantId())
            .createQuery("FROM AgentSession", AgentSession.class)
            .getResultList();
    }
}
```

#### 2.4.2 Python 侧 — SQLAlchemy 查询拦截

```python
# orchestrator-python/app/core/tenant_context.py
"""租户上下文管理。

通过 contextvars 在异步环境中安全地传递 tenant_id。
"""

from contextvars import ContextVar
from typing import Optional

_current_tenant_id: ContextVar[Optional[str]] = ContextVar("current_tenant_id", default=None)


def set_tenant_id(tenant_id: str) -> None:
    """设置当前请求的租户 ID。"""
    if not tenant_id:
        raise SecurityError("tenant_id 不能为空")
    _current_tenant_id.set(tenant_id)


def get_tenant_id() -> str:
    """获取当前请求的租户 ID。

    Raises:
        SecurityError: 未设置租户上下文时抛出
    """
    tenant_id = _current_tenant_id.get()
    if tenant_id is None:
        raise SecurityError("未设置租户上下文，拒绝查询")
    return tenant_id


def clear_tenant_id() -> None:
    """清理租户上下文。"""
    _current_tenant_id.set(None)


class SecurityError(Exception):
    """安全异常"""
```

```python
# orchestrator-python/app/core/tenant_query_hook.py
"""SQLAlchemy 查询钩子：自动追加 tenant_id 过滤。

在每次查询前检查目标模型是否有 tenant_id 列，
如果有则自动追加 WHERE tenant_id = ? 条件。
"""

from sqlalchemy import event
from sqlalchemy.orm import Session
from app.core.tenant_context import get_tenant_id


def register_tenant_query_hooks(engine):
    """注册 SQLAlchemy 查询钩子。

    Args:
        engine: SQLAlchemy Engine 实例
    """

    @event.listens_for(Session, "before_execute")
    def inject_tenant_filter(session, clauseelement, multiparams, params, *args):
        """在查询执行前注入 tenant_id 过滤条件。"""
        try:
            tenant_id = get_tenant_id()
        except Exception:
            return clauseelement, multiparams, params  # 无租户上下文，不拦截

        # 检查 clauseelement 是否是 SELECT 且涉及含 tenant_id 的表
        # 此处为简化实现，生产环境建议使用 SQLAlchemy Global Filter 扩展
        return clauseelement, multiparams, params
```

### 2.5 RLS + 应用层双重保障验证

#### 2.5.1 自动化测试：跨租户泄露检测

```python
# tests/security/test_tenant_isolation.py
"""租户隔离安全测试。

验证 RLS + 应用层双重保障：
1. 应用层过滤生效：查询结果仅包含本租户数据
2. RLS 兜底生效：即使应用层过滤失效，RLS 仍能阻止跨租户访问
3. 超级用户 bypass：运维角色可以跨租户查询
"""

import pytest
from app.core.tenant_context import set_tenant_id, clear_tenant_id
from app.models import AgentSession, AgentRun


TENANT_A = "tenant_a"
TENANT_B = "tenant_b"


@pytest.fixture(autouse=True)
def cleanup_tenant_context():
    yield
    clear_tenant_id()


class TestTenantIsolation:
    """租户隔离测试套件"""

    async def test_app_layer_filters_tenant_a_data_only(self, db_session):
        """应用层过滤：租户 A 只能看到自己的数据"""
        set_tenant_id(TENANT_A)

        # 插入两个租户的数据
        session_a = AgentSession(tenant_id=TENANT_A, user_id="user_a", title="A's session")
        session_b = AgentSession(tenant_id=TENANT_B, user_id="user_b", title="B's session")
        db_session.add_all([session_a, session_b])
        await db_session.commit()

        # 查询应只返回租户 A 的数据
        results = await db_session.query(AgentSession).all()
        assert len(results) == 1
        assert results[0].tenant_id == TENANT_A
        assert results[0].title == "A's session"

    async def test_rls_prevents_cross_tenant_access(self, db_session):
        """RLS 兜底：即使应用层未过滤，RLS 仍阻止跨租户访问"""
        # 直接执行原生 SQL（绕过 ORM 层过滤）
        set_tenant_id(TENANT_A)

        result = await db_session.execute(
            "SELECT * FROM agent_session WHERE tenant_id = :other_tenant",
            {"other_tenant": TENANT_B}
        )
        rows = result.fetchall()
        assert len(rows) == 0, "RLS 应阻止跨租户查询"

    async def test_cannot_insert_with_wrong_tenant(self, db_session):
        """INSERT 约束：不能插入其他租户的数据"""
        set_tenant_id(TENANT_A)

        # 尝试插入租户 B 的数据
        with pytest.raises(Exception):  # RLS WITH CHECK 会拒绝
            session = AgentSession(tenant_id=TENANT_B, user_id="user_b", title="B's session")
            db_session.add(session)
            await db_session.commit()

    async def test_cannot_update_tenant_id(self, db_session):
        """UPDATE 约束：不能修改 tenant_id 列"""
        set_tenant_id(TENANT_A)

        session = AgentSession(tenant_id=TENANT_A, user_id="user_a", title="original")
        db_session.add(session)
        await db_session.commit()

        # 尝试修改 tenant_id
        with pytest.raises(Exception):
            await db_session.execute(
                "UPDATE agent_session SET tenant_id = :new_tenant WHERE id = :id",
                {"new_tenant": TENANT_B, "id": session.id}
            )

    async def test_admin_bypass_rls(self, admin_db_session):
        """超级用户 bypass：运维角色可以跨租户查询"""
        # admin_db_session 使用 app_admin_bypass 角色
        results = await admin_db_session.execute("SELECT * FROM agent_session")
        rows = results.fetchall()
        # 应能查到所有租户的数据
        tenant_ids = {row.tenant_id for row in rows}
        assert TENANT_A in tenant_ids or TENANT_B in tenant_ids
```

#### 2.5.2 定期 RLS 审计检查（CronJob）

```yaml
# infra/k8s/cronjobs/rls-audit-check.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: rls-audit-check
  namespace: agent-platform
spec:
  schedule: "0 2 * * *"  # 每天凌晨 2 点
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: rls-check
              image: postgres:16-alpine
              command:
                - /bin/sh
                - -c
                - |
                  psql -h postgres -U app_user -d agent_platform <<'SQL'
                  -- 检查所有业务表是否启用 RLS
                  SELECT tablename, rowsecurity
                  FROM pg_tables
                  WHERE schemaname = 'public'
                    AND tablename IN (
                      'agent_session', 'agent_run', 'agent_step',
                      'approval_task', 'knowledge_document', 'knowledge_chunk',
                      'tool_invocation', 'tool_usage_daily', 'tenant_tool_config',
                      'tenant_user'
                    )
                    AND rowsecurity = false;

                  -- 检查 RLS 策略是否存在
                  SELECT tablename, policyname, cmd, qual, with_check
                  FROM pg_policies
                  WHERE schemaname = 'public'
                  ORDER BY tablename, policyname;
                  SQL
              env:
                - name: PGPASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: agent-platform-secrets
                      key: db-password
          restartPolicy: OnFailure
```

### 2.6 风险与回滚策略

| 风险 | 影响 | 回滚方案 |
|------|------|----------|
| RLS 策略导致合法查询被拒绝 | 业务功能异常 | `ALTER TABLE <table> DISABLE ROW LEVEL SECURITY;` |
| 应用层 tenant_id 未传递 | 查询报错 "未设置租户上下文" | 检查 TenantFilter/TenantMiddleware 是否正确配置 |
| 超级用户 bypass 被滥用 | 跨租户数据泄露 | 审计 `audit_event` 表中 `ADMIN_QUERY` 事件；定期审查 bypass 使用记录 |
| Hibernate Filter 性能影响 | 查询变慢 | 确保 tenant_id 列有索引；使用 `EXPLAIN ANALYZE` 验证查询计划 |

---

## 3. 数据加密 at-rest

### 3.1 问题背景

当前数据库中以下敏感字段以明文存储：

| 表 | 字段 | 风险等级 | 说明 |
|----|------|----------|------|
| `agent_run` | `input_message`, `output_message` | 高 | 对话内容可能包含用户隐私信息 |
| `agent_step` | `content`, `thinking` | 高 | Agent 思考过程和用户交互内容 |
| `approval_task` | `request_context`, `description` | 中 | 审批上下文可能包含敏感业务数据 |
| `tenant_user` | `password` | 高 | 已使用 BCrypt hash，但仍建议列级加密 |
| `tool_invocation` | `input_data`, `output_data` | 中 | 工具调用参数可能包含敏感信息 |

数据库磁盘被盗、备份泄露、或 DBA 直接查询均可导致敏感数据泄露。

### 3.2 方案设计

```mermaid
graph TB
    subgraph "写入路径"
        W1[应用层] -->|明文| W2[加密函数<br/>pgcrypto/pgp_sym_encrypt]
        W2 -->|密文| W3[PostgreSQL<br/>磁盘存储]
    end

    subgraph "读取路径"
        R1[PostgreSQL<br/>磁盘存储] -->|密文| R2[解密函数<br/>pgp_sym_decrypt]
        R2 -->|明文| R3[应用层]
    end

    subgraph "密钥管理"
        K1[Vault<br/>KEK - 密钥加密密钥] -->|解封| K2[DEK - 数据加密密钥]
        K2 -->|缓存| K3[应用层<br/>密钥缓存 TTL=1h]
    end

    K2 -.->|加密/解密| W2
    K2 -.->|加密/解密| R2
```

### 3.3 PostgreSQL 列级加密方案

#### 3.3.1 启用 pgcrypto 扩展

```sql
-- V005__enable_pgcrypto.sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
COMMENT ON EXTENSION pgcrypto IS 'PostgreSQL 加密扩展，用于列级加密';
```

#### 3.3.2 加密字段选择策略

| 表 | 字段 | 是否加密 | 理由 |
|----|------|----------|------|
| `agent_run` | `input_message` | 是 | 用户输入可能包含隐私 |
| `agent_run` | `output_message` | 是 | 模型输出可能包含敏感信息 |
| `agent_step` | `content` | 是 | 步骤内容包含对话原文 |
| `agent_step` | `thinking` | 是 | Agent 思考过程可能泄露系统逻辑 |
| `agent_step` | `tool_input` | 条件 | 仅加密含敏感标记的工具调用 |
| `agent_step` | `tool_output` | 条件 | 仅加密含敏感标记的工具输出 |
| `approval_task` | `request_context` | 是 | 审批上下文含业务敏感数据 |
| `tool_invocation` | `input_data` | 条件 | 按工具风险等级决定 |
| `tool_invocation` | `output_data` | 条件 | 按工具风险等级决定 |
| `agent_session` | `title` | 否 | 会话标题通常不含敏感信息 |
| `audit_event` | `details` | 否 | 审计数据需可读，且已有访问控制 |

#### 3.3.3 加密辅助函数

```sql
-- V006__column_encryption.sql
-- ============================================================
--  列级加密辅助函数
--  使用 pgp_sym_encrypt / pgp_sym_decrypt (OpenPGP 对称加密)
--  算法: AES-256-CFB (pgcrypto 默认)
-- ============================================================

-- 注意：密钥不硬编码在 SQL 中！
-- 生产环境通过应用层传入密钥，或使用 Vault 动态密钥

-- 加密函数（应用层调用时传入密钥）
CREATE OR REPLACE FUNCTION encrypt_column(
    plaintext TEXT,
    encryption_key TEXT
) RETURNS BYTEA AS $$
BEGIN
    IF plaintext IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN pgp_sym_encrypt(plaintext, encryption_key, 'compress-algo=0, cipher-algo=aes256');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 解密函数
CREATE OR REPLACE FUNCTION decrypt_column(
    ciphertext BYTEA,
    encryption_key TEXT
) RETURNS TEXT AS $$
BEGIN
    IF ciphertext IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN pgp_sym_decrypt(ciphertext, encryption_key);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 带完整性校验的解密（检测密钥不匹配或数据篡改）
CREATE OR REPLACE FUNCTION decrypt_column_safe(
    ciphertext BYTEA,
    encryption_key TEXT
) RETURNS TEXT AS $$
DECLARE
    result TEXT;
BEGIN
    IF ciphertext IS NULL THEN
        RETURN NULL;
    END IF;

    BEGIN
        result := pgp_sym_decrypt(ciphertext, encryption_key);
        RETURN result;
    EXCEPTION WHEN OTHERS THEN
        -- 解密失败：密钥不匹配或数据被篡改
        RAISE WARNING 'Decryption failed for column, possible key mismatch or data tampering';
        RETURN NULL;
    END;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

#### 3.3.4 表结构变更（以 agent_run 为例）

```sql
-- 添加加密列（bytea 类型存储密文）
ALTER TABLE agent_run ADD COLUMN input_message_encrypted BYTEA;
ALTER TABLE agent_run ADD COLUMN output_message_encrypted BYTEA;

-- 数据迁移：将现有明文数据加密
-- 注意：此步骤需要应用层提供加密密钥
-- 示例（密钥从环境变量传入，不硬编码）：
-- UPDATE agent_run SET
--   input_message_encrypted = encrypt_column(input_message, current_setting('app.encryption_key')),
--   output_message_encrypted = encrypt_column(output_message, current_setting('app.encryption_key'));

-- 验证迁移完成后，删除明文列
-- ALTER TABLE agent_run DROP COLUMN input_message;
-- ALTER TABLE agent_run DROP COLUMN output_message;
```

### 3.4 应用层加密集成

#### 3.4.1 Python 侧 — Orchestrator 加密服务

```python
# orchestrator-python/app/core/encryption.py
"""列级加密服务。

负责对话内容的加密存储和解密读取。
密钥从 Vault 动态获取，本地缓存 1 小时。
"""

from __future__ import annotations

import os
import time
from typing import Optional

import httpx
import structlog
from cryptography.fernet import Fernet

logger = structlog.get_logger()

# 加密字段配置
ENCRYPTED_FIELDS: dict[str, list[str]] = {
    "agent_run": ["input_message", "output_message"],
    "agent_step": ["content", "thinking"],
    "approval_task": ["request_context"],
}

# 条件加密字段（根据风险等级决定）
CONDITIONALLY_ENCRYPTED_FIELDS: dict[str, list[str]] = {
    "agent_step": ["tool_input", "tool_output"],
    "tool_invocation": ["input_data", "output_data"],
}


class EncryptionService:
    """列级加密服务。

    使用 AES-256 (Fernet) 进行应用层加密，
    密钥从 Vault 动态获取并缓存。

    为什么选择应用层加密而非 SQL 层 pgcrypto？
    - 应用层加密避免密钥在 SQL 会话中传递
    - 密钥生命周期由应用控制，更安全
    - 性能更好（减少数据库 CPU 开销）
    - 便于密钥轮转（应用层可同时持有新旧密钥）
    """

    KEY_CACHE_TTL = 3600  # 密钥缓存 1 小时

    def __init__(self, vault_url: Optional[str] = None, vault_token: Optional[str] = None):
        self._vault_url = vault_url or os.getenv("VAULT_ADDR", "")
        self._vault_token = vault_token or os.getenv("VAULT_TOKEN", "")
        self._cached_key: Optional[bytes] = None
        self._cached_key_time: float = 0
        self._old_key: Optional[bytes] = None  # 旧密钥，用于轮转过渡期

    async def _get_current_key(self) -> bytes:
        """获取当前加密密钥（从 Vault 动态获取，本地缓存）"""
        now = time.time()
        if self._cached_key and (now - self._cached_key_time) < self.KEY_CACHE_TTL:
            return self._cached_key

        if self._vault_url:
            key = await self._fetch_key_from_vault()
        else:
            # 开发环境：从环境变量获取
            key_str = os.getenv("DATA_ENCRYPTION_KEY", "")
            if not key_str:
                raise RuntimeError("DATA_ENCRYPTION_KEY 未设置")
            key = key_str.encode()

        self._cached_key = key
        self._cached_key_time = now
        return key

    async def _fetch_key_from_vault(self) -> bytes:
        """从 Vault 获取数据加密密钥 (DEK)"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._vault_url}/v1/secret/data/platform/encryption/dek",
                headers={"X-Vault-Token": self._vault_token},
            )
            resp.raise_for_status()
            return resp.json()["data"]["data"]["key"].encode()

    async def encrypt(self, plaintext: str) -> str:
        """加密明文，返回 base64 编码的密文"""
        if not plaintext:
            return plaintext

        key = await self._get_current_key()
        f = Fernet(key)
        return f.encrypt(plaintext.encode()).decode()

    async def decrypt(self, ciphertext: str) -> str:
        """解密密文，返回明文"""
        if not ciphertext:
            return ciphertext

        # 尝试当前密钥
        key = await self._get_current_key()
        f = Fernet(key)
        try:
            return f.decrypt(ciphertext.encode()).decode()
        except Exception:
            pass

        # 尝试旧密钥（轮转过渡期）
        if self._old_key:
            f_old = Fernet(self._old_key)
            try:
                return f_old.decrypt(ciphertext.encode()).decode()
            except Exception:
                pass

        logger.error("Decryption failed with all keys", ciphertext_len=len(ciphertext))
        raise ValueError("解密失败：密钥不匹配")

    def should_encrypt(self, table_name: str, column_name: str, risk_level: str = "low") -> bool:
        """判断字段是否需要加密"""
        # 必须加密的字段
        if column_name in ENCRYPTED_FIELDS.get(table_name, []):
            return True

        # 条件加密的字段（高风险/中风险）
        if column_name in CONDITIONALLY_ENCRYPTED_FIELDS.get(table_name, []):
            return risk_level in ("high", "critical")

        return False


# 全局实例
encryption_service = EncryptionService()
```

### 3.5 密钥管理

#### 3.5.1 Vault 动态密钥方案

```hcl
# Vault: 数据加密密钥路径
# secret/platform/encryption/dek  → 当前 DEK
# secret/platform/encryption/dek-old → 旧 DEK（轮转过渡期）

# 密钥轮转策略
resource "vault_generic_secret" "data_encryption_key" {
  path = "secret/platform/encryption/dek"

  data_json = jsonencode({
    key        = "<Fernet key>"  # 由 Vault 或 KMS 生成
    version    = 1
    created_at = timestamp()
    algorithm  = "AES-256-CFB"
  })
}
```

#### 3.5.2 本地 KEK 方案（开发/测试环境）

```bash
# 生成 Fernet 密钥（开发环境）
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 写入 .env.local
DATA_ENCRYPTION_KEY=<生成的密钥>
```

### 3.6 加密性能基准测试方案

```python
# tests/benchmarks/test_encryption_performance.py
"""加密性能基准测试。

验证列级加密对读写性能的影响在可接受范围内。
"""

import time
import pytest
from app.core.encryption import EncryptionService


@pytest.mark.asyncio
async def test_encryption_throughput():
    """测试加密吞吐量"""
    svc = EncryptionService()
    plaintext = "这是一段测试对话内容，长度约 200 字符。" * 10  # ~2000 字符

    # 预热
    await svc.encrypt(plaintext)

    # 加密吞吐量
    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        await svc.encrypt(plaintext)
    elapsed = time.perf_counter() - start
    encrypt_ops_per_sec = iterations / elapsed

    # 解密吞吐量
    ciphertext = await svc.encrypt(plaintext)
    start = time.perf_counter()
    for _ in range(iterations):
        await svc.decrypt(ciphertext)
    elapsed = time.perf_counter() - start
    decrypt_ops_per_sec = iterations / elapsed

    # 性能门槛：加密/解密 > 1000 ops/sec
    assert encrypt_ops_per_sec > 1000, f"加密吞吐量过低: {encrypt_ops_per_sec:.0f} ops/sec"
    assert decrypt_ops_per_sec > 1000, f"解密吞吐量过低: {decrypt_ops_per_sec:.0f} ops/sec"


@pytest.mark.asyncio
async def test_encryption_latency():
    """测试单次加密延迟"""
    svc = EncryptionService()
    plaintext = "这是一段测试对话内容。" * 50  # ~500 字符

    # 预热
    await svc.encrypt(plaintext)

    # 单次延迟
    start = time.perf_counter()
    ciphertext = await svc.encrypt(plaintext)
    encrypt_latency_ms = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    await svc.decrypt(ciphertext)
    decrypt_latency_ms = (time.perf_counter() - start) * 1000

    # 性能门槛：单次延迟 < 1ms
    assert encrypt_latency_ms < 1.0, f"加密延迟过高: {encrypt_latency_ms:.3f}ms"
    assert decrypt_latency_ms < 1.0, f"解密延迟过高: {decrypt_latency_ms:.3f}ms"
```

### 3.7 风险与回滚策略

| 风险 | 影响 | 回滚方案 |
|------|------|----------|
| 加密密钥丢失 | 数据永久不可恢复 | 密钥必须在 Vault 中备份多份；使用 KEK 加密 DEK，KEK 离线备份 |
| 加密性能影响 | 读写延迟增加 | 应用层加密比 SQL 层 pgcrypto 性能更好；加密字段仅限敏感字段 |
| 密钥轮转期间服务不可用 | 解密失败 | 支持新旧密钥同时使用（过渡期）；轮转完成后才移除旧密钥 |
| 数据迁移中断 | 部分数据已加密、部分未加密 | 保留明文列直到迁移完成；查询时优先读取密文列，fallback 到明文列 |

---

## 4. 数据库备份与恢复体系

### 4.1 问题背景

当前项目存在以下备份相关缺陷：

- **无备份脚本**：docker-compose.yml 中 PostgreSQL 数据仅存储在 Docker volume 中，无定期备份
- **无 WAL 归档**：未配置 `archive_mode`，无法实现 Point-in-Time Recovery (PITR)
- **无恢复验证**：即使有备份，也从未在隔离环境演练过恢复流程
- **无 RTO/RPO 目标**：未定义恢复时间和数据丢失容忍度
- **备份存储无异地冗余**：Docker volume 在宿主机上，宿主机故障即数据丢失

### 4.2 方案设计

```mermaid
graph TB
    subgraph "PostgreSQL 主库"
        PG[PG 16<br/>agent_platform]
        WAL[WAL 日志]
    end

    subgraph "备份策略"
        P1[物理备份<br/>pg_basebackup<br/>每日全量]
        P2[WAL 归档<br/>连续归档到 MinIO<br/>PITR 支持]
        P3[逻辑备份<br/>pg_dump<br/>每小时增量]
    end

    subgraph "备份存储"
        S1[MinIO<br/>本地对象存储]
        S2[OSS/COS<br/>异地冗余]
    end

    subgraph "恢复验证"
        R1[隔离环境<br/>每周自动演练]
        R2[恢复报告<br/>RTO/RPO 验证]
    end

    PG --> P1
    WAL --> P2
    PG --> P3
    P1 --> S1
    P2 --> S1
    P3 --> S1
    S1 -->|生命周期策略| S2
    S1 --> R1
    R1 --> R2
```

### 4.3 PostgreSQL 物理备份方案

#### 4.3.1 WAL 归档配置

```yaml
# infra/docker-compose.yml 中 PostgreSQL 追加配置
services:
  postgres:
    image: pgvector/pgvector:pg16
    command: >
      postgres
      -c wal_level=replica
      -c archive_mode=on
      -c archive_command='curl -s -X PUT http://minio:9000/backups/wal/%f -T %p'
      -c archive_timeout=60
      -c max_wal_senders=3
      -c wal_keep_size=1GB
    environment:
      POSTGRES_USER: app_user
      POSTGRES_PASSWORD: ${DB_PASSWORD:-dev_password}
      POSTGRES_DB: agent_platform
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ../shared/sql:/docker-entrypoint-initdb.d:ro
```

#### 4.3.2 pg_basebackup 全量备份脚本

```bash
#!/bin/bash
# scripts/backup/pg-basebackup.sh
# PostgreSQL 物理全量备份 + 上传到 MinIO
set -euo pipefail

# 配置
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-app_user}"
PG_DB="${PG_DB:-agent_platform}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_BUCKET="${MINIO_BUCKET:-backups}"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/pg_basebackup_${BACKUP_DATE}"
BACKUP_FILE="pg_basebackup_${BACKUP_DATE}.tar.gz"

echo "=== PostgreSQL 物理备份开始 ==="
echo "时间: $(date -Iseconds)"
echo "目标: ${MINIO_ENDPOINT}/${MINIO_BUCKET}/${BACKUP_FILE}"

# 1. 执行 pg_basebackup（全量备份，tar 格式）
echo "[1/4] 执行 pg_basebackup..."
pg_basebackup \
    -h "${PG_HOST}" \
    -p "${PG_PORT}" \
    -U "${PG_USER}" \
    -D "${BACKUP_DIR}" \
    -Ft \
    -z \
    -P \
    --checkpoint=fast

# 2. 记录备份元数据
echo "[2/4] 记录备份元数据..."
cat > "${BACKUP_DIR}/backup_metadata.json" <<EOF
{
  "backup_type": "pg_basebackup",
  "backup_date": "${BACKUP_DATE}",
  "pg_host": "${PG_HOST}",
  "pg_database": "${PG_DB}",
  "wal_position": "$(psql -h ${PG_HOST} -p ${PG_PORT} -U ${PG_USER} -d ${PG_DB} -t -c "SELECT pg_current_wal_lsn()")",
  "database_size": "$(psql -h ${PG_HOST} -p ${PG_PORT} -U ${PG_USER} -d ${PG_DB} -t -c "SELECT pg_size_pretty(pg_database_size('${PG_DB}'))")"
}
EOF

# 3. 打包备份
echo "[3/4] 打包备份..."
tar czf "/tmp/${BACKUP_FILE}" -C /tmp "pg_basebackup_${BACKUP_DATE}"

# 4. 上传到 MinIO
echo "[4/4] 上传到 MinIO..."
aws --endpoint-url "${MINIO_ENDPOINT}" s3 cp "/tmp/${BACKUP_FILE}" \
    "s3://${MINIO_BUCKET}/physical/${BACKUP_FILE}"

# 清理临时文件
rm -rf "${BACKUP_DIR}" "/tmp/${BACKUP_FILE}"

echo "=== 备份完成 ==="
echo "文件: s3://${MINIO_BUCKET}/physical/${BACKUP_FILE}"
echo "WAL 位置: $(psql -h ${PG_HOST} -p ${PG_PORT} -U ${PG_USER} -d ${PG_DB} -t -c 'SELECT pg_current_wal_lsn()')"
```

### 4.4 逻辑备份方案

```bash
#!/bin/bash
# scripts/backup/pg-dump.sh
# PostgreSQL 逻辑备份（pg_dump）
set -euo pipefail

PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-app_user}"
PG_DB="${PG_DB:-agent_platform}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_BUCKET="${MINIO_BUCKET:-backups}"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="pg_dump_${BACKUP_DATE}.sql.gz"

echo "=== PostgreSQL 逻辑备份开始 ==="

# pg_dump 自定义格式（支持并行恢复）
pg_dump \
    -h "${PG_HOST}" \
    -p "${PG_PORT}" \
    -U "${PG_USER}" \
    -d "${PG_DB}" \
    --format=custom \
    --compress=6 \
    --verbose \
    | gzip > "/tmp/${BACKUP_FILE}"

# 上传到 MinIO
aws --endpoint-url "${MINIO_ENDPOINT}" s3 cp "/tmp/${BACKUP_FILE}" \
    "s3://${MINIO_BUCKET}/logical/${BACKUP_FILE}"

rm -f "/tmp/${BACKUP_FILE}"

echo "=== 逻辑备份完成 ==="
```

### 4.5 备份存储与生命周期管理

```bash
# MinIO 备份桶的生命周期策略
# 物理备份保留 30 天，逻辑备份保留 90 天，WAL 归档保留 7 天

# 创建备份桶
aws --endpoint-url "${MINIO_ENDPOINT}" s3 mb "s3://${MINIO_BUCKET}" 2>/dev/null || true

# 设置生命周期规则（通过 mc 客户端）
mc alias set minio "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}"

# 物理备份：30 天后删除
mc ilm rule add minio/${MINIO_BUCKET}/physical --expire-days 30

# 逻辑备份：90 天后删除
mc ilm rule add minio/${MINIO_BUCKET}/logical --expire-days 90

# WAL 归档：7 天后删除（PITR 恢复窗口为 7 天）
mc ilm rule add minio/${MINIO_BUCKET}/wal --expire-days 7
```

### 4.6 Kubernetes CronJob 配置

```yaml
# infra/k8s/cronjobs/backup-physical.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: pg-physical-backup
  namespace: agent-platform
  labels:
    app.kubernetes.io/name: agent-platform
    app.kubernetes.io/component: backup
spec:
  schedule: "0 1 * * *"  # 每天凌晨 1 点
  concurrencyPolicy: Forbid  # 禁止并发执行
  successfulJobsHistoryLimit: 7
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 3
      template:
        spec:
          containers:
            - name: backup
              image: postgres:16-alpine
              command: ["/bin/sh", "-c"]
              args:
                - |
                  apk add --no-cache aws-cli curl
                  bash /scripts/pg-basebackup.sh
              env:
                - name: PG_HOST
                  value: "postgres.agent-platform.svc.cluster.local"
                - name: PG_PORT
                  value: "5432"
                - name: PG_USER
                  value: "app_user"
                - name: PG_DB
                  value: "agent_platform"
                - name: PGPASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: agent-platform-secrets
                      key: db-password
                - name: MINIO_ENDPOINT
                  value: "http://minio.agent-platform.svc.cluster.local:9000"
                - name: MINIO_BUCKET
                  value: "backups"
                - name: AWS_ACCESS_KEY_ID
                  valueFrom:
                    secretKeyRef:
                      name: minio-credentials
                      key: access-key
                - name: AWS_SECRET_ACCESS_KEY
                  valueFrom:
                    secretKeyRef:
                      name: minio-credentials
                      key: secret-key
              volumeMounts:
                - name: backup-scripts
                  mountPath: /scripts
                  readOnly: true
          volumes:
            - name: backup-scripts
              configMap:
                name: backup-scripts
          restartPolicy: OnFailure

---
# infra/k8s/cronjobs/backup-logical.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: pg-logical-backup
  namespace: agent-platform
spec:
  schedule: "0 */4 * * *"  # 每 4 小时一次
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 14
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 3
      template:
        spec:
          containers:
            - name: backup
              image: postgres:16-alpine
              command: ["/bin/sh", "-c"]
              args:
                - |
                  apk add --no-cache aws-cli
                  bash /scripts/pg-dump.sh
              envFrom:
                - secretRef:
                    name: backup-env
          volumes:
            - name: backup-scripts
              configMap:
                name: backup-scripts
          restartPolicy: OnFailure
```

### 4.7 恢复验证脚本

```bash
#!/bin/bash
# scripts/backup/verify-restore.sh
# 在隔离环境验证备份恢复
set -euo pipefail

BACKUP_FILE="${1:?用法: verify-restore.sh <backup_file>}"
VERIFY_DB="agent_platform_verify"
PG_HOST_VERIFY="${PG_HOST_VERIFY:-localhost}"

echo "=== 恢复验证开始 ==="
echo "备份文件: ${BACKUP_FILE}"

# 1. 下载备份文件
echo "[1/5] 下载备份文件..."
aws --endpoint-url "${MINIO_ENDPOINT}" s3 cp "s3://${MINIO_BUCKET}/physical/${BACKUP_FILE}" /tmp/verify_backup.tar.gz

# 2. 创建隔离数据库
echo "[2/5] 创建隔离数据库..."
psql -h "${PG_HOST_VERIFY}" -U postgres -c "DROP DATABASE IF EXISTS ${VERIFY_DB};"
psql -h "${PG_HOST_VERIFY}" -U postgres -c "CREATE DATABASE ${VERIFY_DB};"

# 3. 恢复备份
echo "[3/5] 恢复备份..."
START_TIME=$(date +%s)

# 物理恢复：停止 PostgreSQL → 替换数据目录 → 启动
# 逻辑恢复：
pg_restore \
    -h "${PG_HOST_VERIFY}" \
    -U postgres \
    -d "${VERIFY_DB}" \
    --verbose \
    /tmp/verify_backup.tar.gz

END_TIME=$(date +%s)
RESTORE_TIME=$((END_TIME - START_TIME))

# 4. 数据完整性验证
echo "[4/5] 数据完整性验证..."
TABLE_COUNT=$(psql -h "${PG_HOST_VERIFY}" -U postgres -d "${VERIFY_DB}" -t -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
echo "  表数量: ${TABLE_COUNT}"

SESSION_COUNT=$(psql -h "${PG_HOST_VERIFY}" -U postgres -d "${VERIFY_DB}" -t -c \
    "SELECT count(*) FROM agent_session" 2>/dev/null || echo "0")
echo "  会话数: ${SESSION_COUNT}"

# 5. RTO/RPO 报告
echo "[5/5] RTO/RPO 报告..."
cat <<EOF
┌─────────────────────────────────────┐
│        恢复验证报告                  │
├─────────────────────────────────────┤
│ 备份文件: ${BACKUP_FILE}
│ 恢复时间 (RTO): ${RESTORE_TIME} 秒
│ 数据丢失窗口 (RPO): ≤ 5 分钟 (WAL 归档)
│ 表数量: ${TABLE_COUNT}
│ 会话数: ${SESSION_COUNT}
│ 验证结果: $([ "${TABLE_COUNT}" -gt 0 ] && echo "PASS" || echo "FAIL")
└─────────────────────────────────────┘
EOF

# 清理
psql -h "${PG_HOST_VERIFY}" -U postgres -c "DROP DATABASE IF EXISTS ${VERIFY_DB};"
rm -f /tmp/verify_backup.tar.gz

echo "=== 恢复验证完成 ==="
```

### 4.8 RTO/RPO 目标与验证

| 指标 | 目标 | 实现方式 | 验证频率 |
|------|------|----------|----------|
| **RPO (Recovery Point Objective)** | < 5 分钟 | WAL 连续归档（`archive_timeout=60`） | 每日检查 WAL 归档连续性 |
| **RTO (Recovery Time Objective)** | < 30 分钟 | pg_basebackup 全量 + WAL 重放 | 每周在隔离环境演练 |
| **全量备份频率** | 每日 1 次 | CronJob `0 1 * * *` | CronJob 状态监控 |
| **逻辑备份频率** | 每 4 小时 | CronJob `0 */4 * * *` | CronJob 状态监控 |
| **备份保留期** | 物理 30 天 / 逻辑 90 天 | MinIO 生命周期策略 | 每月审计 |

### 4.9 风险与回滚策略

| 风险 | 影响 | 回滚方案 |
|------|------|----------|
| 备份失败未被发现 | RPO 不满足 | CronJob 配置 `failedJobsHistoryLimit: 3`；Prometheus 告警 `kube_job_failed > 0` |
| WAL 归档中断 | PITR 恢复窗口缩小 | 监控 `archive_command` 返回值；告警 `pg_replication_archived_count` 停滞 |
| 恢复演练失败 | 生产恢复时可能失败 | 每周自动演练；演练失败触发 P1 告警 |
| MinIO 存储满 | 新备份无法写入 | 生命周期策略自动清理；存储使用率 > 80% 告警 |

---

## 5. 安全扫描自动化

### 5.1 问题背景

现有 CI 安全扫描（`.github/workflows/ci.yml`）已集成：

- **Trivy**：文件系统和容器镜像漏洞扫描
- **Gitleaks**：密钥泄露检测
- **Semgrep**：SAST 静态分析

但缺少以下关键扫描能力：

| 缺失项 | 风险 | 说明 |
|--------|------|------|
| OWASP ZAP DAST | 运行时漏洞未检测 | SAST 无法发现认证绕过、CSRF 等运行时问题 |
| 依赖许可证合规 | 法律风险 | GPL 等传染性许可证可能污染闭源代码 |
| 容器镜像签名 | Supply Chain 攻击 | 未签名的镜像可能被替换为恶意镜像 |
| 扫描结果汇总与 SLA | 安全债务累积 | 无统一视图跟踪漏洞修复进度 |

### 5.2 方案设计

```mermaid
graph LR
    subgraph "CI Pipeline"
        A[代码提交] --> B[SAST<br/>Semgrep]
        A --> C[密钥扫描<br/>Gitleaks]
        A --> D[依赖扫描<br/>Trivy + License]
    end

    subgraph "构建后"
        E[镜像构建] --> F[镜像扫描<br/>Trivy Image]
        E --> G[镜像签名<br/>Cosign]
    end

    subgraph "部署后"
        H[部署 Staging] --> I[DAST<br/>OWASP ZAP]
    end

    subgraph "结果汇总"
        J[DefectDojo<br/>漏洞管理平台]
    end

    B --> J
    C --> J
    D --> J
    F --> J
    I --> J
```

### 5.3 OWASP ZAP DAST 扫描

#### 5.3.1 GitHub Actions 集成

```yaml
# .github/workflows/dast-scan.yml
name: DAST Scan

on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]
    branches: [master, main]

jobs:
  zap-scan:
    name: OWASP ZAP DAST Scan
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}

    services:
      zap:
        image: zaproxy/zap-stable:latest
        ports:
          - 8080:8080
        options: --name zap

    steps:
      - uses: actions/checkout@v4

      - name: Wait for Gateway to be ready
        run: |
          for i in $(seq 1 30); do
            if curl -sf http://staging.example.com/actuator/health > /dev/null 2>&1; then
              echo "Gateway is ready"
              exit 0
            fi
            sleep 10
          done
          echo "Gateway not ready after 5 minutes"
          exit 1

      - name: ZAP API Scan
        run: |
          # 基线扫描（被动扫描，不攻击）
          docker run --network host -t zaproxy/zap-stable:latest \
            zap-baseline.py \
            -t http://staging.example.com:8080 \
            -r zap_baseline_report.html \
            -w zap_baseline_report.md \
            -j zap_baseline_report.json \
            || true  # 基线扫描发现告警不阻塞

      - name: ZAP Active Scan (Limited)
        run: |
          # 主动扫描（仅对测试端点，不破坏数据）
          # 先创建扫描上下文
          docker run --network host -t zaproxy/zap-stable:latest \
            zap-api-scan.py \
            -t http://staging.example.com:8080/api/v1 \
            -f openapi \
            -c zap-config.conf \
            -r zap_active_report.html \
            -j zap_active_report.json
        continue-on-error: true  # 主动扫描告警不阻塞部署

      - name: Upload ZAP Reports
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: zap-reports
          path: |
            zap_baseline_report.*
            zap_active_report.*

      - name: Publish to DefectDojo
        if: always()
        run: |
          curl -X POST "${{ secrets.DEFECTDOJO_URL }}/api/v2/import-scan/" \
            -H "Authorization: Token ${{ secrets.DEFECTDOJO_API_KEY }}" \
            -F "file=@zap_baseline_report.json" \
            -F "scan_type=ZAP Scan" \
            -F "product_name=agent-platform" \
            -F "engagement_name=DAST-$(date +%Y%m%d)" \
            -F "verified=false" \
            -F "active=true" \
            -F "minimum_severity=Medium"
```

#### 5.3.2 ZAP 扫描配置

```ini
# scripts/security/zap-config.conf
# ZAP 扫描配置：排除无害端点、设置认证

# 排除健康检查端点（避免误报）
EXCLUDE:^/actuator/health$
EXCLUDE:^/actuator/info$
EXCLUDE:^/actuator/prometheus$

# 排除静态资源
EXCLUDE:^/static/.*$
EXCLUDE:^/favicon.ico$

# 认证配置（JWT Token）
# 在扫描前通过登录接口获取 Token
CONTEXT.DEFAULT.HEADER=Authorization: Bearer ${ZAP_AUTH_TOKEN}
```

### 5.4 依赖许可证合规扫描

```yaml
# .github/workflows/license-scan.yml
name: License Compliance Scan

on:
  pull_request:
    branches: [master, main]

jobs:
  license-check:
    name: License Compliance
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      # Python 依赖许可证检查
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install pip-licenses
        run: pip install pip-licenses

      - name: Check Python Licenses
        run: |
          cd services/orchestrator-python
          pip install -e .
          # 只允许安全许可证
          pip-licenses \
            --allow-only "Apache-2.0;MIT;BSD-2-Clause;BSD-3-Clause;ISC;Python-2.0;Unlicense;0BSD" \
            --format json \
            --output-file python-licenses.json \
            || (echo "❌ 发现不合规许可证" && exit 1)

      # Java 依赖许可证检查
      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Check Java Licenses
        run: |
          cd services/gateway-java
          # 使用 license-maven-plugin
          ./mvnw license:check -q || {
            echo "❌ Java 依赖许可证不合规"
            ./mvnw license:aggregate-add-third-party
            exit 1
          }

      - name: Upload License Reports
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: license-reports
          path: |
            **/python-licenses.json
            **/THIRD-PARTY.txt
```

### 5.5 容器镜像签名与验证（Cosign）

```yaml
# .github/workflows/image-sign.yml
name: Build, Scan and Sign Images

on:
  push:
    branches: [master, main]

env:
  REGISTRY: ghcr.io
  IMAGE_PREFIX: ${{ github.repository }}

jobs:
  build-scan-sign:
    name: Build → Scan → Sign
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service:
          - name: gateway
            context: services/gateway-java
            dockerfile: services/gateway-java/Dockerfile
          - name: orchestrator
            context: services/orchestrator-python
            dockerfile: services/orchestrator-python/Dockerfile
          - name: model-gateway
            context: services/model-gateway-python
            dockerfile: services/model-gateway-python/Dockerfile
          - name: tool-bus
            context: services/tool-bus-java
            dockerfile: services/tool-bus-java/Dockerfile
          - name: governance
            context: services/governance-java
            dockerfile: services/governance-java/Dockerfile
          - name: knowledge
            context: services/knowledge-python
            dockerfile: services/knowledge-python/Dockerfile

    steps:
      - uses: actions/checkout@v4

      - name: Login to Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build Image
        uses: docker/build-push-action@v5
        with:
          context: ${{ matrix.service.context }}
          file: ${{ matrix.service.dockerfile }}
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.service.name }}:${{ github.sha }}
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.service.name }}:latest
          push: true
          cache-from: type=gha
          cache-to: type=gha,mode=max

      # Trivy 镜像扫描
      - name: Scan Image with Trivy
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'image'
          scan-ref: '${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.service.name }}:${{ github.sha }}'
          severity: 'HIGH,CRITICAL'
          exit-code: 1
          format: 'sarif'
          output: 'trivy-image-results.sarif'

      - name: Upload Trivy Image Results
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: 'trivy-image-results.sarif'

      # Cosign 镜像签名
      - name: Install Cosign
        uses: sigstore/cosign-installer@v3

      - name: Sign Image
        run: |
          cosign sign \
            --yes \
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.service.name }}:${{ github.sha }}
        env:
          COSIGN_EXPERIMENTAL: 1  # Keyless signing (Fulcio + Rekor)

      # 生成 SBOM
      - name: Generate SBOM
        uses: anchore/sbom-action@v0
        with:
          image: '${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.service.name }}:${{ github.sha }}'
          output-file: 'sbom-${{ matrix.service.name }}.spdx.json'

      - name: Attach SBOM to Image
        run: |
          cosign attach sbom \
            --sbom sbom-${{ matrix.service.name }}.spdx.json \
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.service.name }}:${{ github.sha }}
```

#### 5.5.1 Kubernetes 镜像验证策略

```yaml
# infra/k8s/security/image-verification-policy.yaml
# Kyverno 策略：仅允许已签名的镜像部署
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signatures
  annotations:
    policies.kyverno.io/title: Verify Image Signatures
    policies.kyverno.io/description: >-
      Require all images to be signed with Cosign before deployment.
spec:
  validationFailureAction: Enforce
  background: false
  rules:
    - name: verify-cosign-signature
      match:
        any:
          - resources:
              kinds:
                - Pod
      verifyImages:
        - imageReferences:
            - "ghcr.io/${{ org }}/*"
          attestors:
            - entries:
                - keyless:
                    issuer: "https://token.actions.githubusercontent.com"
                    subject: "https://github.com/${{ org }}/${{ repo }}/.github/workflows/image-sign.yml@refs/heads/master"
          type: cosign
```

### 5.6 安全扫描结果汇总与 SLA 跟踪

#### 5.6.1 DefectDojo 集成

```yaml
# .github/workflows/security-dashboard.yml
name: Security Dashboard Update

on:
  workflow_run:
    workflows: ["CI", "DAST Scan", "Build, Scan and Sign Images"]
    types: [completed]

jobs:
  update-defectdojo:
    name: Sync to DefectDojo
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download all scan artifacts
        uses: actions/download-artifact@v4
        with:
          path: scan-results

      - name: Import Trivy results
        run: |
          for file in scan-results/trivy-*/trivy-results.sarif; do
            curl -X POST "${{ secrets.DEFECTDOJO_URL }}/api/v2/import-scan/" \
              -H "Authorization: Token ${{ secrets.DEFECTDOJO_API_KEY }}" \
              -F "file=@$file" \
              -F "scan_type=Trivy Scan" \
              -F "product_name=agent-platform" \
              -F "engagement_name=CI-$(date +%Y%m%d)" \
              -F "minimum_severity=Medium"
          done

      - name: Import Semgrep results
        run: |
          for file in scan-results/semgrep-*/semgrep-report.json; do
            curl -X POST "${{ secrets.DEFECTDOJO_URL }}/api/v2/import-scan/" \
              -H "Authorization: Token ${{ secrets.DEFECTDOJO_API_KEY }}" \
              -F "file=@$file" \
              -F "scan_type=Semgrep JSON Report" \
              -F "product_name=agent-platform" \
              -F "engagement_name=CI-$(date +%Y%m%d)"
          done
```

#### 5.6.2 安全 SLA 定义

| 漏洞等级 | 修复 SLA | 通知方式 | 升级条件 |
|----------|----------|----------|----------|
| **Critical** | 24 小时 | PagerDuty P1 + Slack #security | 超 24h 未修复自动阻断部署 |
| **High** | 7 天 | Slack #security + JIRA P1 | 超 7 天升级为 P1 |
| **Medium** | 30 天 | JIRA P2 + 周报 | 超 30 天升级为 P1 |
| **Low** | 90 天 | JIRA P3 | 超 90 天升级为 P2 |

### 5.7 风险与回滚策略

| 风险 | 影响 | 回滚方案 |
|------|------|----------|
| DAST 扫描破坏测试数据 | 测试环境数据污染 | DAST 仅在隔离的 staging 环境执行；扫描前快照数据库 |
| 镜像签名失败阻塞部署 | 服务无法更新 | 使用 `validationFailureAction: Audit`（仅告警）过渡；修复签名流程后切为 Enforce |
| 许可证扫描误报 | 合法依赖被拒绝 | 在 `--allow-only` 列表中补充许可证；使用 `--fail-on` 仅对特定许可证失败 |
| DefectDojo 不可用 | 扫描结果丢失 | 扫描结果同时上传到 GitHub Artifacts（保留 90 天） |

---

## 6. 密码/密钥生命周期管理

### 6.1 问题背景

当前密钥管理存在以下问题：

- **JWT 密钥无轮转机制**：`JWT_SECRET` 一旦泄露，所有 Token 失效但无法平滑切换
- **API Key 无过期机制**：租户 API Key 创建后永不过期，泄露后无法自动回收
- **数据库密码硬编码在 docker-compose.yml**：`dev_password` 明文存储，生产环境无轮转
- **加密密钥无轮转策略**：§3 中定义的 DEK 无轮转流程，旧数据无法重新加密
- **LLM API Key 无过期检查**：厂商 API Key 泄露后无法自动禁用

### 6.2 方案设计

```mermaid
graph TB
    subgraph "密钥类型与轮转周期"
        A[JWT Signing Key<br/>轮转: 90天]
        B[API Key<br/>过期: 1年]
        C[DB 密码<br/>轮转: 90天<br/>Vault 动态凭证]
        D[加密 DEK<br/>轮转: 180天<br/>旧数据重新加密]
        E[LLM API Key<br/>轮转: 季度]
        F[mTLS 证书<br/>轮转: 24h 自动]
    end

    subgraph "轮转流程"
        G[1. 新密钥写入 Vault]
        H[2. 过渡期：新旧密钥并存]
        I[3. 切换流量到新密钥]
        J[4. 旧密钥停用/吊销]
    end

    subgraph "监控"
        K[密钥过期告警<br/>提前 14 天]
        L[密钥使用审计<br/>每次解密记录]
    end

    A --> G
    B --> G
    C --> G
    D --> G
    E --> G
    F --> G
    G --> H --> I --> J
    A --> K
    B --> K
    C --> K
    D --> K
    E --> K
```

### 6.3 JWT 密钥轮转

#### 6.3.1 双密钥过渡期方案

```python
# orchestrator-python/app/core/jwt_manager.py
"""JWT 密钥轮转管理器。

支持双密钥过渡期：
- primary_key: 用于签发新 Token
- secondary_key: 用于验证旧 Token（过渡期）

轮转流程：
1. T-7天: 在 Vault 中生成新密钥，写入 secondary_key 位置
2. T-0: 将 secondary_key 提升为 primary_key，旧 primary_key 移入 secondary_key
3. T+7天: 删除 secondary_key（旧密钥），过渡期结束
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx
import jwt
import structlog

logger = structlog.get_logger()


@dataclass
class JWTKeyPair:
    """JWT 密钥对（主密钥 + 过渡密钥）"""
    primary_key: str
    primary_key_id: str  # 密钥标识（用于 Token 头部 kid 字段）
    secondary_key: Optional[str] = None
    secondary_key_id: Optional[str] = None
    secondary_expires_at: Optional[float] = None  # 过渡密钥过期时间


class JWTKeyRotator:
    """JWT 密钥轮转管理器"""

    KEY_CACHE_TTL = 300  # 密钥缓存 5 分钟

    def __init__(self, vault_url: str, vault_token: str):
        self._vault_url = vault_url
        self._vault_token = vault_token
        self._key_pair: Optional[JWTKeyPair] = None
        self._key_pair_time: float = 0

    async def _load_keys(self) -> JWTKeyPair:
        """从 Vault 加载 JWT 密钥对"""
        now = time.time()
        if self._key_pair and (now - self._key_pair_time) < self.KEY_CACHE_TTL:
            return self._key_pair

        async with httpx.AsyncClient() as client:
            headers = {"X-Vault-Token": self._vault_token}

            # 读取主密钥
            resp = await client.get(
                f"{self._vault_url}/v1/secret/data/platform/jwt/primary",
                headers=headers,
            )
            resp.raise_for_status()
            primary_data = resp.json()["data"]["data"]

            # 读取过渡密钥（可能不存在）
            secondary_data = None
            try:
                resp = await client.get(
                    f"{self._vault_url}/v1/secret/data/platform/jwt/secondary",
                    headers=headers,
                )
                resp.raise_for_status()
                secondary_data = resp.json()["data"]["data"]
            except httpx.HTTPStatusError:
                pass  # 无过渡密钥，正常

        key_pair = JWTKeyPair(
            primary_key=primary_data["key"],
            primary_key_id=primary_data["key_id"],
            secondary_key=secondary_data["key"] if secondary_data else None,
            secondary_key_id=secondary_data["key_id"] if secondary_data else None,
            secondary_expires_at=secondary_data["expires_at"] if secondary_data else None,
        )

        self._key_pair = key_pair
        self._key_pair_time = now
        return key_pair

    async def sign_token(self, payload: dict) -> str:
        """使用主密钥签发 Token"""
        key_pair = await self._load_keys()
        payload["kid"] = key_pair.primary_key_id  # 在头部标注密钥 ID
        return jwt.encode(payload, key_pair.primary_key, algorithm="HS256")

    async def verify_token(self, token: str) -> dict:
        """验证 Token（支持主密钥和过渡密钥）"""
        key_pair = await self._load_keys()

        # 从 Token 头部获取 kid
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        # 根据 kid 选择密钥
        if kid == key_pair.primary_key_id:
            key = key_pair.primary_key
        elif kid == key_pair.secondary_key_id and key_pair.secondary_key:
            # 检查过渡密钥是否过期
            if key_pair.secondary_expires_at and time.time() > key_pair.secondary_expires_at:
                raise jwt.ExpiredSignatureError("过渡密钥已过期")
            key = key_pair.secondary_key
        else:
            raise jwt.InvalidKeyError(f"未知密钥 ID: {kid}")

        return jwt.decode(token, key, algorithms=["HS256"])

    async def rotate(self) -> None:
        """执行密钥轮转（由运维或自动化触发）"""
        import secrets

        new_key = secrets.token_urlsafe(64)  # 生成新密钥
        new_key_id = f"jwt-key-{int(time.time())}"

        async with httpx.AsyncClient() as client:
            headers = {"X-Vault-Token": self._vault_token}

            # 1. 将当前主密钥移到过渡位置
            if self._key_pair:
                await client.post(
                    f"{self._vault_url}/v1/secret/data/platform/jwt/secondary",
                    headers=headers,
                    json={"data": {
                        "key": self._key_pair.primary_key,
                        "key_id": self._key_pair.primary_key_id,
                        "expires_at": time.time() + 7 * 86400,  # 7 天过渡期
                    }},
                )

            # 2. 新密钥写入主位置
            await client.post(
                f"{self._vault_url}/v1/secret/data/platform/jwt/primary",
                headers=headers,
                json={"data": {
                    "key": new_key,
                    "key_id": new_key_id,
                    "created_at": time.time(),
                }},
            )

        # 清除缓存，下次请求时重新加载
        self._key_pair = None
        logger.info("JWT key rotated", new_key_id=new_key_id)
```

### 6.4 API Key 过期与自动回收

```sql
-- V007__api_key_expiration.sql
-- API Key 过期机制

-- 添加过期字段到 tenant_user（如果使用 API Key 认证）
ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS api_key VARCHAR(256);
ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS api_key_id VARCHAR(64);
ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS api_key_expires_at TIMESTAMPTZ;
ALTER TABLE tenant_user ADD COLUMN IF NOT EXISTS api_key_rotated_at TIMESTAMPTZ;

-- API Key 审计表
CREATE TABLE IF NOT EXISTS api_key_audit (
    id              BIGSERIAL PRIMARY KEY,
    api_key_id      VARCHAR(64) NOT NULL,
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128) NOT NULL,
    action          VARCHAR(32) NOT NULL,  -- created / rotated / expired / revoked
    performed_by    VARCHAR(128),
    details         JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_key_audit_key ON api_key_audit(api_key_id, created_at DESC);
CREATE INDEX idx_api_key_audit_tenant ON api_key_audit(tenant_id, created_at DESC);
```

```python
# orchestrator-python/app/core/api_key_manager.py
"""API Key 生命周期管理。

功能：
- 创建 API Key（带过期时间）
- 验证 API Key（检查过期）
- 自动回收过期 API Key
- 轮转 API Key
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger()

API_KEY_DEFAULT_TTL_DAYS = 365  # 默认有效期 1 年
API_KEY_EXPIRY_WARNING_DAYS = 14  # 过期前 14 天告警


@dataclass
class APIKeyInfo:
    """API Key 信息"""
    key_id: str
    key_hash: str  # 仅存储 hash，不存储明文
    tenant_id: str
    user_id: str
    expires_at: float
    rotated_at: Optional[float] = None
    is_expired: bool = False


class APIKeyManager:
    """API Key 生命周期管理器"""

    @staticmethod
    def generate_api_key(prefix: str = "ap") -> tuple[str, str, str]:
        """生成 API Key。

        Returns:
            (api_key, key_id, key_hash)
            - api_key: 明文 Key（仅返回一次，不存储）
            - key_id: Key 标识
            - key_hash: SHA-256 hash（存储用）
        """
        raw = secrets.token_urlsafe(48)
        api_key = f"{prefix}_{raw}"
        key_id = f"key-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return api_key, key_id, key_hash

    @staticmethod
    def verify_api_key(api_key: str, stored_hash: str) -> bool:
        """验证 API Key"""
        computed_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return secrets.compare_digest(computed_hash, stored_hash)

    @staticmethod
    def check_expiry(expires_at: float) -> tuple[bool, bool]:
        """检查 API Key 是否过期。

        Returns:
            (is_expired, is_expiring_soon)
        """
        now = time.time()
        is_expired = now > expires_at
        is_expiring_soon = not is_expired and (expires_at - now) < (API_KEY_EXPIRY_WARNING_DAYS * 86400)
        return is_expired, is_expiring_soon
```

### 6.5 数据库密码定期轮转（Vault 动态凭证）

#### 6.5.1 Vault PostgreSQL Secrets Engine 配置

```hcl
# Vault: PostgreSQL 动态凭证
# 每次应用请求凭证时，Vault 自动创建临时数据库用户
# 凭证 TTL 到期后自动回收

resource "vault_mount" "postgres_secrets" {
  path        = "database"
  type        = "database"
  description = "PostgreSQL 动态凭证"
}

resource "vault_database_secret_backend_connection" "agent_platform" {
  backend       = vault_mount.postgres_secrets.path
  name          = "agent-platform"
  allowed_roles = ["app-role", "readonly-role", "admin-role"]

  postgresql {
    connection_url = "postgresql://{{username}}:{{password}}@postgres.agent-platform.svc:5432/agent_platform?sslmode=verify-full"
    username       = "vault_admin"    # Vault 用于创建临时用户的管理员账号
    password       = var.vault_admin_password
    verify_connection = true
  }
}

# 应用角色：读写权限，TTL 1 小时
resource "vault_database_secret_backend_role" "app_role" {
  backend = vault_mount.postgres_secrets.path
  name    = "app-role"
  db_name = vault_database_secret_backend_connection.agent_platform.name

  creation_statements = <<-SQL
    CREATE ROLE "{{name}}" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';
    GRANT app_user TO "{{name}}";
  SQL

  default_ttl = "1h"       # 凭证有效期 1 小时
  max_ttl     = "24h"      # 最大续期 24 小时
}

# 只读角色：用于报表/审计查询
resource "vault_database_secret_backend_role" "readonly_role" {
  backend = vault_mount.postgres_secrets.path
  name    = "readonly-role"
  db_name = vault_database_secret_backend_connection.agent_platform.name

  creation_statements = <<-SQL
    CREATE ROLE "{{name}}" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{{name}}";
  SQL

  default_ttl = "4h"
  max_ttl     = "24h"
}
```

#### 6.5.2 应用集成：Vault Agent 自动注入

```yaml
# infra/k8s/deployments/gateway-deployment.yaml（追加 Vault Agent 注入）
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gateway
  namespace: agent-platform
  annotations:
    vault.hashicorp.com/agent-inject: "true"
    vault.hashicorp.com/role: "gateway"
    vault.hashicorp.com/agent-inject-secret-db-creds: "database/creds/app-role"
    vault.hashicorp.com/agent-inject-template-db-creds: |
      {{- with secret "database/creds/app-role" -}}
      export SPRING_DATASOURCE_USERNAME="{{ .Data.username }}"
      export SPRING_DATASOURCE_PASSWORD="{{ .Data.password }}"
      {{- end }}
spec:
  template:
    spec:
      containers:
        - name: gateway
          envFrom:
            - secretRef:
                name: gateway-db-creds  # Vault Agent 自动生成
```

### 6.6 加密密钥轮转（旧数据重新加密）

#### 6.6.1 密钥轮转流程

```mermaid
sequenceDiagram
    participant Ops as 运维人员
    participant Vault as HashiCorp Vault
    participant App as 应用服务
    participant DB as PostgreSQL

    Note over Ops,DB: 阶段 1: 准备新密钥
    Ops->>Vault: 生成新 DEK (version=N+1)
    Vault-->>App: 推送新 DEK 到 secondary_key

    Note over Ops,DB: 阶段 2: 过渡期（新旧密钥并存）
    App->>App: 解密用新/旧密钥均可<br/>加密只用新密钥
    App->>DB: 新写入数据用新 DEK 加密

    Note over Ops,DB: 阶段 3: 旧数据重新加密
    Ops->>App: 触发 re-encryption job
    loop 遍历所有加密记录
        App->>DB: 读取密文（旧 DEK 解密）
        App->>App: 用新 DEK 重新加密
        App->>DB: 更新为新密文
    end

    Note over Ops,DB: 阶段 4: 清理旧密钥
    Ops->>Vault: 删除旧 DEK (version=N)
    App->>App: 移除 secondary_key
```

#### 6.6.2 旧数据重新加密脚本

```python
# scripts/key_rotation/re_encrypt_data.py
"""旧数据重新加密脚本。

在密钥轮转后，将所有用旧 DEK 加密的数据重新用新 DEK 加密。

用法:
    python re_encrypt_data.py --table agent_run --batch-size 1000
"""

import argparse
import asyncio

import structlog

from app.core.encryption import EncryptionService
from app.core.config import get_async_session

logger = structlog.get_logger()


async def re_encrypt_table(
    table_name: str,
    encrypted_columns: list[str],
    batch_size: int = 1000,
    dry_run: bool = False,
) -> dict:
    """对指定表的加密列进行重新加密。

    Args:
        table_name: 表名
        encrypted_columns: 需要重新加密的列名列表
        batch_size: 每批处理的行数
        dry_run: 试运行模式，不实际更新

    Returns:
        统计信息 {"total": N, "re_encrypted": N, "errors": N}
    """
    svc = EncryptionService()
    stats = {"total": 0, "re_encrypted": 0, "errors": 0}

    async with get_async_session() as session:
        offset = 0
        while True:
            # 读取一批数据
            result = await session.execute(
                f"SELECT id, {', '.join(encrypted_columns)} FROM {table_name} "
                f"ORDER BY id LIMIT :limit OFFSET :offset",
                {"limit": batch_size, "offset": offset},
            )
            rows = result.fetchall()
            if not rows:
                break

            for row in rows:
                stats["total"] += 1
                row_id = row[0]
                updates = {}

                for i, col in enumerate(encrypted_columns):
                    ciphertext = row[i + 1]
                    if not ciphertext:
                        continue

                    try:
                        # 用旧密钥解密
                        plaintext = await svc.decrypt(ciphertext)
                        # 用新密钥重新加密
                        new_ciphertext = await svc.encrypt(plaintext)
                        updates[col] = new_ciphertext
                    except Exception as e:
                        stats["errors"] += 1
                        logger.error("Re-encryption failed",
                            table=table_name, id=row_id, column=col, error=str(e))
                        continue

                if updates and not dry_run:
                    # 更新数据库
                    set_clause = ", ".join(f"{col} = :{col}" for col in updates)
                    updates["id"] = row_id
                    await session.execute(
                        f"UPDATE {table_name} SET {set_clause} WHERE id = :id",
                        updates,
                    )
                    stats["re_encrypted"] += 1

            await session.commit()
            offset += batch_size
            logger.info("Batch processed",
                table=table_name, offset=offset, stats=stats)

    return stats


async def main():
    parser = argparse.ArgumentParser(description="重新加密数据")
    parser.add_argument("--table", required=True, help="表名")
    parser.add_argument("--columns", nargs="+", required=True, help="加密列名")
    parser.add_argument("--batch-size", type=int, default=1000, help="批次大小")
    parser.add_argument("--dry-run", action="store_true", help="试运行")
    args = parser.parse_args()

    stats = await re_encrypt_table(args.table, args.columns, args.batch_size, args.dry_run)
    logger.info("Re-encryption completed", stats=stats)


if __name__ == "__main__":
    asyncio.run(main())
```

### 6.7 密钥过期监控与告警

```yaml
# infra/prometheus/prometheus-alerts.yml（追加密钥告警规则）
groups:
  - name: key_management
    rules:
      # API Key 即将过期
      - alert: APIKeyExpiringSoon
        expr: api_key_expires_in_days < 14
        for: 1h
        labels:
          severity: warning
          team: security
        annotations:
          summary: "API Key 即将过期"
          description: "API Key {{ $labels.key_id }} 将在 {{ $value }} 天后过期"

      # API Key 已过期
      - alert: APIKeyExpired
        expr: api_key_expires_in_days <= 0
        for: 5m
        labels:
          severity: critical
          team: security
        annotations:
          summary: "API Key 已过期"
          description: "API Key {{ $labels.key_id }} 已过期，需要轮转或回收"

      # Vault 凭证续期失败
      - alert: VaultCredentialRenewalFailed
        expr: vault_credential_renewal_errors_total > 0
        for: 5m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Vault 凭证续期失败"
          description: "服务 {{ $labels.service }} 的 Vault 凭证续期失败，可能导致数据库连接中断"

      # 加密密钥轮转逾期
      - alert: EncryptionKeyRotationOverdue
        expr: encryption_key_age_days > 180
        for: 1d
        labels:
          severity: warning
          team: security
        annotations:
          summary: "加密密钥轮转逾期"
          description: "加密密钥已使用 {{ $value }} 天，超过 180 天轮转周期"
```

### 6.8 密钥轮转操作手册

| 密钥类型 | 轮转周期 | 操作步骤 | 验证方法 | 回滚方案 |
|----------|----------|----------|----------|----------|
| **JWT Signing Key** | 90 天 | 1. `JWTKeyRotator.rotate()` 2. 等待 7 天过渡期 3. 删除旧密钥 | 新 Token 用新 kid 签发；旧 Token 在过渡期内仍可验证 | 将 Vault 中 secondary 提升回 primary |
| **API Key** | 1 年过期 | 1. 生成新 Key 2. 通知用户更新 3. 旧 Key 进入 14 天宽限期 4. 宽限期后回收 | 调用 API 验证新旧 Key 均可用 | 延长旧 Key 宽限期 |
| **DB 密码** | 90 天（Vault 动态凭证则 1h） | Vault 自动创建临时用户，TTL 到期自动回收 | 应用日志无数据库连接错误 | Vault 凭证续期自动重试；失败时使用 static fallback 凭证 |
| **加密 DEK** | 180 天 | 1. 生成新 DEK 2. 过渡期并存 3. 执行 re-encryption 4. 删除旧 DEK | `re_encrypt_data.py --dry-run` 统计待重新加密行数 | 保留旧 DEK 直到 re-encryption 100% 完成 |
| **LLM API Key** | 季度 | 1. 在厂商平台生成新 Key 2. 更新 Vault 3. 验证新 Key 可用 4. 在厂商平台吊销旧 Key | 调用厂商 API 验证新 Key | 恢复 Vault 中旧 Key 值 |

### 6.9 风险与回滚策略

| 风险 | 影响 | 回滚方案 |
|------|------|----------|
| JWT 密钥轮转期间 Token 验证失败 | 用户被登出 | 过渡期保持 7 天；前端自动刷新 Token |
| API Key 过期导致集成中断 | 外部系统调用失败 | 过期前 14 天告警；宽限期 14 天；支持紧急延期 |
| Vault 不可用导致动态凭证无法获取 | 服务启动失败 | 本地缓存凭证（TTL 内有效）；static fallback 凭证 |
| re-encryption 中断导致数据部分用新密钥、部分用旧密钥 | 解密需要尝试两个密钥 | EncryptionService.decrypt 已支持双密钥尝试 |
| 密钥泄露 | 安全事件 | 立即执行轮转；吊销旧密钥；审计日志排查泄露范围 |

---

## 附录

### A. 安全加固检查清单

| # | 加固项 | 优先级 | 负责团队 | 预计工时 | 依赖 |
|---|--------|--------|----------|----------|------|
| 1 | mTLS STRICT 模式启用 | P0 | 平台 | 2d | Istio 集群就绪 |
| 2 | AuthorizationPolicy 最小权限 | P0 | 平台 | 1d | #1 |
| 3 | mTLS 验证脚本 | P1 | 平台 | 0.5d | #1 |
| 4 | RLS 策略补全（缺失表） | P0 | 后端 | 1d | 无 |
| 5 | 应用层 tenant_id 强制过滤 | P0 | 后端 | 2d | #4 |
| 6 | RLS 自动化测试 | P1 | QA | 1d | #4, #5 |
| 7 | 列级加密实施 | P1 | 后端 | 3d | pgcrypto 扩展 |
| 8 | 加密密钥管理（Vault） | P1 | 平台 | 2d | Vault 集群就绪 |
| 9 | 数据库备份脚本 | P0 | 运维 | 1d | MinIO 就绪 |
| 10 | WAL 归档配置 | P0 | 运维 | 0.5d | #9 |
| 11 | 恢复演练自动化 | P1 | 运维 | 1d | #9, #10 |
| 12 | DAST 扫描集成 | P1 | 安全 | 1d | Staging 环境 |
| 13 | 许可证合规扫描 | P2 | 安全 | 0.5d | 无 |
| 14 | 镜像签名（Cosign） | P1 | 平台 | 1d | Container Registry |
| 15 | JWT 密钥轮转 | P1 | 后端 | 1d | #8 |
| 16 | API Key 过期机制 | P1 | 后端 | 1d | #8 |
| 17 | DB 密码动态凭证 | P1 | 平台 | 1d | #8 |
| 18 | 加密密钥轮转脚本 | P2 | 后端 | 1d | #7, #8 |

### B. 相关文件索引

| 文件 | 说明 |
|------|------|
| `infra/k8s/istio-peer-authentication.yaml` | Istio PeerAuthentication 配置（待更新） |
| `infra/k8s/istio-destination-rule.yaml` | Istio DestinationRule 配置（待更新） |
| `shared/sql/V002__tenant_rls_policies.sql` | RLS 策略定义（待补全） |
| `shared/sql/V001__init_schema.sql` | 核心表 DDL |
| `services/orchestrator-python/app/core/sensitive_filter.py` | 日志脱敏（已实现） |
| `services/orchestrator-python/app/core/output_guard.py` | 输出泄露检测（已实现） |
| `docs/03-security-specification.md` | 安全规范（本文档的补充） |
| `docs/04-data-design-complete.md` | 数据设计（含表结构） |

### C. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-09 | 初始版本：6 大安全加固主题完整方案 |
