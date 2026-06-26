# 生产环境部署指南

> **版本**: v1.0
> **更新**: 2026-06-26
> **状态**: 已验证

本文档记录 Agent Platform 生产环境部署的完整流程和已知问题修复。

---

## 目录

1. [环境要求](#环境要求)
2. [快速部署](#快速部署)
3. [配置说明](#配置说明)
4. [已知问题与修复](#已知问题与修复)
5. [运维手册](#运维手册)

---

## 环境要求

### 最低配置（2GB 内存）

| 服务 | 内存 | CPU | 说明 |
|------|------|-----|------|
| PostgreSQL | 512M | 1核 | 数据库 |
| Redis | 256M | 0.5核 | 缓存 |
| Gateway | 512M | 0.5核 | Java API 网关 |
| Orchestrator | 512M | 0.5核 | Python Agent 编排 |
| Model Gateway | 256M | 0.25核 | Python 模型网关 |
| Knowledge | 256M | 0.25核 | Python 知识库 |
| Tool Bus | 384M | 0.5核 | Java 工具总线 |
| Governance | 384M | 0.5核 | Java 风控审批 |
| Web Frontend | 64M | 0.125核 | Nginx 前端 |
| **总计** | **~3G** | **~4核** | |

### 推荐配置

| 场景 | 内存 | CPU | 说明 |
|------|------|-----|------|
| 开发测试 | 4G | 2核 | 腾讯云轻量 |
| 生产环境 | 8G | 4核 | 腾讯云 CVM |
| 高可用 | 16G+ | 8核+ | 多节点部署 |

---

## 快速部署

### 1. 服务器准备

```bash
# SSH 登录服务器
ssh root@YOUR_SERVER_IP

# 安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker
apt install docker-compose-plugin git -y
```

### 2. 拉取代码

```bash
cd /opt
git clone https://github.com/jonykchen/agent-platform.git
cd agent-platform
```

### 3. 配置环境变量

```bash
cp .env.prod.example .env.prod
vim .env.prod
```

**必须配置的变量**：

```bash
# 数据库
POSTGRES_USER=app_user
POSTGRES_PASSWORD=<生成随机密码>
POSTGRES_DB=agent_platform

# Redis
REDIS_PASSWORD=<生成随机密码>

# JWT
JWT_SECRET=<生成64位随机字符串>

# 加密
ENCRYPTION_KEY=<生成32位Base64编码字符串>

# LLM
LLM_API_KEY=<你的LLM API密钥>
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_DEFAULT_MODEL=qwen-max

# Grafana（可选）
GRAFANA_ADMIN_PASSWORD=<生成强密码>
```

### 4. 部署服务

```bash
# 使用精简版部署（2GB 内存）
docker compose -f infra/docker-compose.deploy.yml up -d --build

# 或使用全量版部署（8GB+ 内存）
docker compose -f infra/docker-compose.prod.yml up -d --build
```

### 5. 初始化数据库

```bash
# 执行初始化脚本
docker exec -i agent-postgres psql -U app_user -d agent_platform < scripts/init-prod-data.sql
```

### 6. 验证部署

```bash
# 检查服务状态
docker ps --format "table {{.Names}}\t{{.Status}}"

# 测试健康检查
curl http://localhost:8080/actuator/health

# 测试登录
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

---

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 | 必需 |
|------|------|--------|------|
| `POSTGRES_USER` | 数据库用户 | app_user | ✅ |
| `POSTGRES_PASSWORD` | 数据库密码 | - | ✅ |
| `POSTGRES_DB` | 数据库名 | agent_platform | ✅ |
| `REDIS_PASSWORD` | Redis 密码 | - | ✅ |
| `JWT_SECRET` | JWT 签名密钥 | - | ✅ |
| `ENCRYPTION_KEY` | 数据加密密钥 | - | ✅ |
| `LLM_API_KEY` | LLM API 密钥 | - | ✅ |
| `LLM_BASE_URL` | LLM API 地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 | ✅ |
| `LLM_DEFAULT_MODEL` | 默认模型 | qwen-max | ✅ |
| `CORS_ALLOWED_ORIGINS` | CORS 白名单 | - | 生产必需 |
| `DB_HOST` | 数据库主机 | postgres | ✅ |
| `REDIS_HOST` | Redis 主机 | redis | ✅ |
| `GRPC_AUTH_SECRET` | gRPC 认证密钥 | - | Java 服务必需 |
| `SERVICE_AUTH_SECRET` | 服务认证密钥 | - | Governance 必需 |

### 端口配置

| 服务 | HTTP 端口 | gRPC 端口 | 说明 |
|------|----------|----------|------|
| Gateway | 8080 | 9091 | API 入口 |
| Orchestrator | 8001 | 50100 | Agent 编排 |
| Model Gateway | 8002 | - | 模型网关 |
| Knowledge | 8003 | - | 知识库 |
| Tool Bus | 8083 | 40051 | 工具总线 |
| Governance | 8082 | - | 风控审批 |
| Web Frontend | 80 | - | 前端 |

---

## 已知问题与修复

### 1. Flyway 迁移冲突

**问题**: Gateway 启动时报 `constraint "uk_tenant_user" does not exist`

**原因**: 数据库已通过 `shared/sql` 初始化，但 Gateway 的 Flyway 迁移冲突

**修复**:
```yaml
# docker-compose.deploy.yml
environment:
  SPRING_FLYWAY_ENABLED: "false"
  SPRING_JPA_HIBERNATE_DDL_AUTO: update
```

### 2. Redis 序列化类型丢失

**问题**: `ClassCastException: LinkedHashMap cannot be cast to TenantConfigResponse`

**原因**: `GenericJackson2JsonRedisSerializer` 反序列化时丢失类型信息

**修复**: 禁用有问题的缓存，或在 `CacheConfig` 中注册 `JavaTimeModule`

```java
ObjectMapper objectMapper = new ObjectMapper();
objectMapper.registerModule(new JavaTimeModule());
objectMapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

new GenericJackson2JsonRedisSerializer(objectMapper)
```

### 3. tenant 表缺少 tier 列

**问题**: `column t1_0.tier does not exist`

**修复**: 
```sql
ALTER TABLE tenant ADD COLUMN IF NOT EXISTS tier VARCHAR(32) DEFAULT 'basic';
```

### 4. CORS 配置

**问题**: 前端请求被 CORS 策略阻止

**修复**: 在 docker-compose 中配置 CORS 白名单
```yaml
environment:
  CORS_ALLOWED_ORIGINS: http://YOUR_SERVER_IP,http://YOUR_SERVER_IP:80
```

### 5. Knowledge 端口不匹配

**问题**: Dockerfile 硬编码 8081 端口，但 docker-compose 映射 8003

**修复**: Dockerfile 使用环境变量
```dockerfile
EXPOSE ${APP_PORT:-8003}
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8003}"]
```

### 6. 默认 tenant_id 不一致

**问题**: AuthService 默认 `tenant_001`，但数据库是 `default`

**修复**: 修改 AuthService.java
```java
String tenantId = request.getTenantId() != null ? request.getTenantId() : "default";
```

### 7. BCrypt 密码哈希

**问题**: 前端登录报 `用户名或密码错误`

**原因**: 数据库中密码哈希格式不正确

**修复**: 使用正确的 BCrypt 哈希
```python
import bcrypt
hashed = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode()
# 存储: $2b$12$...
```

### 8. Java 服务认证密钥

**问题**: `GRPC_AUTH_SECRET is empty` 或 `SERVICE_AUTH_SECRET is empty`

**修复**: 在 docker-compose 中配置
```yaml
environment:
  GRPC_AUTH_SECRET: ${JWT_SECRET}
  SERVICE_AUTH_SECRET: ${JWT_SECRET}
```

---

## 运维手册

### 常用命令

```bash
# 查看服务状态
docker ps --format "table {{.Names}}\t{{.Status}}"

# 查看日志
docker logs -f agent-gateway
docker logs -f agent-orchestrator

# 重启服务
docker compose -f infra/docker-compose.deploy.yml restart gateway

# 停止所有服务
docker compose -f infra/docker-compose.deploy.yml down

# 更新代码并重启
git pull && docker compose -f infra/docker-compose.deploy.yml up -d --build
```

### 数据库备份

```bash
# 手动备份
docker exec agent-postgres pg_dump -U app_user agent_platform > backup_$(date +%Y%m%d).sql

# 恢复备份
docker exec -i agent-postgres psql -U app_user -d agent_platform < backup.sql
```

### 监控

```bash
# 查看资源使用
docker stats --no-stream

# 查看健康状态
curl http://localhost:8080/actuator/health
curl http://localhost:8083/actuator/health
curl http://localhost:8082/actuator/health
```

---

## 测试账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |
| operator | operator123 | 操作员 |
| viewer | viewer123 | 只读用户 |

### 测试 API Key

| 名称 | Key | 权限 |
|------|-----|------|
| 管理员测试Key | sk-test-admin-key-2026 | 全部 |
| 普通用户测试Key | sk-test-user-key-2026 | 对话+工具+知识库 |
| 只读测试Key | sk-test-readonly-key-2026 | 仅对话 |

---

## 相关文档

- [架构概览](architecture-overview.md)
- [API 参考](api-reference.md)
- [安全规范](03-security-specification.md)
- [运维指南](06-operability-guide.md)
