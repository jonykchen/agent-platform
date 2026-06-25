# 生产部署指南

> **版本**: v1.0
> **状态**: 已批准
> **所有者**: Platform Team
> **更新**: 2026-06-24

本文档提供 Agent Platform 的完整生产部署指南，包括环境准备、部署步骤、验证清单、回滚流程和监控配置。

---

## 目录

1. [环境准备](#环境准备)
2. [部署步骤](#部署步骤)
3. [部署后验证](#部署后验证)
4. [回滚流程](#回滚流程)
5. [监控和告警](#监控和告警)
6. [灾备方案](#灾备方案)
7. [常见问题](#常见问题)

---

## 环境准备

### 1. 硬件要求

| 组件 | 最低配置 | 推荐配置 | 说明 |
|------|---------|---------|------|
| **Kubernetes 集群** | 3 节点 | 5+ 节点 | 高可用 |
| **CPU** | 8 核 | 16+ 核 | 所有服务总计 |
| **内存** | 16 GB | 32+ GB | 所有服务总计 |
| **存储** | 100 GB SSD | 500+ GB SSD | 数据库 + 日志 |

### 2. 软件依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| Kubernetes | 1.28+ | 容器编排 |
| Helm | 3.12+ | 包管理 |
| kubectl | 最新 | 集群管理 |
| Docker | 24+ | 镜像构建 |

### 3. 外部服务

| 服务 | 版本 | 说明 |
|------|------|------|
| PostgreSQL | 16+ | 主数据库 |
| Redis | 7+ | 缓存 |
| Kafka | 3.6+ | 消息队列 |
| MinIO | 最新 | 对象存储 |

### 4. 域名和证书

- [ ] 准备域名（如 `agent-platform.example.com`）
- [ ] 配置 DNS 解析
- [ ] 准备 TLS 证书（推荐 Let's Encrypt）

### 5. GitHub Secrets 配置

在 GitHub 仓库设置中配置以下 Secrets：

| Secret | 用途 | 必需 |
|--------|------|------|
| `KUBE_CONFIG` | Kubernetes 配置 | ✅ |
| `DOCKER_USERNAME` | Docker Hub 用户名 | ✅ |
| `DOCKER_PASSWORD` | Docker Hub 密码 | ✅ |
| `DATABASE_URL` | PostgreSQL 连接串 | ✅ |
| `REDIS_URL` | Redis 连接串 | ✅ |
| `JWT_SECRET` | JWT 签名密钥 | ✅ |
| `LLM_API_KEY` | LLM 服务密钥 | ✅ |
| `SEMGREP_APP_TOKEN` | Semgrep SAST | 可选 |

---

## 部署步骤

### 步骤 1: 准备命名空间

```bash
# 创建命名空间
kubectl create namespace agent-platform

# 设置默认命名空间
kubectl config set-context --current --namespace=agent-platform
```

### 步骤 2: 创建 Secrets

```bash
# 创建数据库 Secret
kubectl create secret generic db-secret \
  --from-literal=url='postgresql://user:password@host:5432/agent_platform' \
  --namespace agent-platform

# 创建 Redis Secret
kubectl create secret generic redis-secret \
  --from-literal=url='redis://host:6379/0' \
  --namespace agent-platform

# 创建应用 Secret
kubectl create secret generic app-secret \
  --from-literal=jwt-secret='your-jwt-secret' \
  --from-literal=llm-api-key='your-llm-api-key' \
  --namespace agent-platform
```

### 步骤 3: 部署基础设施

```bash
# 部署 PostgreSQL（如果没有外部服务）
helm install postgres bitnami/postgresql \
  --namespace agent-platform \
  --set auth.postgresPassword=your-password \
  --set auth.database=agent_platform

# 部署 Redis
helm install redis bitnami/redis \
  --namespace agent-platform \
  --set auth.password=your-redis-password

# 部署 Kafka
helm install kafka bitnami/kafka \
  --namespace agent-platform
```

### 步骤 4: 配置 Kustomize

```bash
# 编辑生产配置
cd infra/kubernetes/overlays/prod

# 更新 kustomization.yaml 中的镜像标签
# 更新 secret-generator.yaml 中的密钥
```

### 步骤 5: 部署应用

```bash
# 使用 Kustomize 部署
kubectl apply -k infra/kubernetes/overlays/prod

# 或使用 Makefile
make deploy-prod
```

### 步骤 6: 配置 Ingress

```bash
# 部署 Ingress Controller（如果没有）
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace agent-platform \
  --set controller.replicaCount=2

# 应用 Ingress 配置
kubectl apply -f infra/kubernetes/base/ingress.yaml
```

---

## 部署后验证

### 健康检查清单

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| Pod 状态 | `kubectl get pods` | 所有 Pod Running |
| 服务状态 | `kubectl get svc` | 所有服务存在 |
| Ingress 状态 | `kubectl get ingress` | ADDRESS 已分配 |
| 日志检查 | `kubectl logs -f deployment/gateway` | 无错误日志 |

### API 测试

```bash
# 测试健康检查
curl -X GET https://agent-platform.example.com/health

# 测试认证
curl -X POST https://agent-platform.example.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# 测试对话接口
curl -X POST https://agent-platform.example.com/api/v1/chat/completions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "stream": false}'
```

### 性能测试

```bash
# 使用 k6 进行负载测试
k6 run --vus 100 --duration 5m scripts/load-test.js

# 监控指标
kubectl top pods
kubectl top nodes
```

---

## 回滚流程

### 自动回滚

```bash
# 查看部署历史
kubectl rollout history deployment/gateway

# 回滚到上一个版本
kubectl rollout undo deployment/gateway

# 回滚到指定版本
kubectl rollout undo deployment/gateway --to-revision=2
```

### 手动回滚

1. **停止当前部署**
   ```bash
   kubectl rollout pause deployment/gateway
   ```

2. **恢复旧版本镜像**
   ```bash
   kubectl set image deployment/gateway \
     gateway=agent-platform/gateway:previous-tag
   ```

3. **验证回滚**
   ```bash
   kubectl rollout status deployment/gateway
   kubectl get pods -l app=gateway
   ```

### 数据库回滚

```bash
# 连接数据库
psql -h host -U user -d agent_platform

# 执行回滚迁移
alembic downgrade -1
```

---

## 监控和告警

### 监控栈

| 组件 | 用途 | 访问地址 |
|------|------|----------|
| Prometheus | 指标收集 | http://prometheus:9090 |
| Grafana | 可视化 | http://grafana:3000 |
| AlertManager | 告警管理 | http://alertmanager:9093 |

### 关键指标

| 指标 | 阈值 | 说明 |
|------|------|------|
| CPU 使用率 | > 80% | 扩容阈值 |
| 内存使用率 | > 85% | 扩容阈值 |
| 请求延迟 P95 | > 6s | 性能问题 |
| 错误率 | > 1% | 服务异常 |
| Pod 重启次数 | > 3 | 稳定性问题 |

### 告警规则

```yaml
# prometheus-alerts.yml
groups:
  - name: agent-platform
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 6
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
```

### 日志收集

```bash
# 查看实时日志
kubectl logs -f deployment/gateway --tail=100

# 使用 Stern 查看多 Pod 日志
stern -l app=gateway

# 导出日志
kubectl logs deployment/gateway > gateway.log
```

---

## 灾备方案

### 1. 数据库备份

```bash
# 自动备份（CronJob）
kubectl apply -f infra/kubernetes/base/backup-cronjob.yaml

# 手动备份
pg_dump -h host -U user agent_platform > backup_$(date +%Y%m%d).sql
```

### 2. 多区域部署

```yaml
# kustomization.yaml
replicas:
  - name: gateway
    count: 3
  - name: orchestrator
    count: 3
```

### 3. 灾难恢复

1. **恢复数据库**
   ```bash
   psql -h host -U user agent_platform < backup.sql
   ```

2. **恢复应用**
   ```bash
   kubectl apply -k infra/kubernetes/overlays/prod
   ```

3. **验证服务**
   ```bash
   kubectl get pods
   curl -X GET https://agent-platform.example.com/health
   ```

---

## 常见问题

### Q1: Pod 启动失败

**症状**: Pod 处于 `CrashLoopBackOff` 状态

**排查步骤**:
```bash
# 查看 Pod 详情
kubectl describe pod <pod-name>

# 查看日志
kubectl logs <pod-name> --previous

# 检查资源限制
kubectl top pod <pod-name>
```

**常见原因**:
- 资源不足（CPU/内存）
- 配置错误（环境变量、Secrets）
- 依赖服务不可用（数据库、Redis）

### Q2: 服务无法访问

**症状**: 外部无法访问服务

**排查步骤**:
```bash
# 检查 Ingress
kubectl get ingress
kubectl describe ingress <ingress-name>

# 检查 Service
kubectl get svc
kubectl describe svc <service-name>

# 检查 Endpoints
kubectl get endpoints
```

**常见原因**:
- Ingress 配置错误
- Service 端口不匹配
- Pod 未就绪

### Q3: 性能问题

**症状**: 响应延迟高

**排查步骤**:
```bash
# 查看资源使用
kubectl top pods
kubectl top nodes

# 查看 HPA 状态
kubectl get hpa

# 查看 Grafana 仪表板
```

**解决方案**:
- 调整 HPA 配置
- 增加副本数
- 优化数据库查询

---

## 附录

### A. 有用命令

```bash
# 查看所有资源
kubectl get all

# 查看 Pod 日志
kubectl logs -f <pod-name>

# 进入 Pod
kubectl exec -it <pod-name> -- /bin/sh

# 端口转发
kubectl port-forward svc/gateway 8080:8080

# 查看事件
kubectl get events --sort-by='.lastTimestamp'
```

### B. 配置文件位置

| 文件 | 用途 |
|------|------|
| `infra/kubernetes/base/` | 基础配置 |
| `infra/kubernetes/overlays/prod/` | 生产配置 |
| `infra/kubernetes/overlays/dev/` | 开发配置 |
| `.github/workflows/ci.yml` | CI/CD 配置 |

### C. 相关文档

- [技术方案总览](00-index.md)
- [运维指南](06-operability-guide.md)
- [架构图](architecture-overview.md)
- [安全规范](03-security-specification.md)
