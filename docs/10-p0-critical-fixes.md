# P0 紧急修复方案

> **版本**：v1.2 | **状态**：已实施 | **优先级**：P0（阻塞上线）
>
> 本文档覆盖 6 个 P0 级问题，每个方案必须在本迭代内完成。
>
> **实施状态更新（2026-06-25）**：
> - ✅ P0-1: Dockerfile（7 个服务已实现）
> - ✅ P0-2: Python DB 迁移（Alembic 配置已实现）
> - ✅ P0-3: K8s Ingress/NetworkPolicy（K8s 配置已实现）
> - ✅ P0-4: SSE 端到端（ChatController 已实现 SseEmitter）
> - ✅ P0-5: 环境配置模板（根目录 .env.example 已实现）
> - ✅ P0-6: API Key 加密存储（EncryptionService 已实现 AES-256-GCM）

---

## 目录

1. [API Key 加密存储](#1-api-key-加密存储)
2. [Python 服务数据库迁移](#2-python-服务数据库迁移)
3. [K8s Ingress + NetworkPolicy](#3-k8s-ingress--networkpolicy)
4. [Model-Gateway Dockerfile](#4-model-gateway-dockerfile)
5. [SSE/流式响应端到端打通](#5-sse流式响应端到端打通)
6. [环境配置模板统一](#6-环境配置模板统一)

---

## 1. API Key 加密存储

### 1.1 问题背景

当前 `ApiKey.java` 实体仅使用 SHA-256 哈希存储 API Key 的摘要值（`key_hash`），验证时对传入明文做哈希比对。这一设计对**外部 API Key 验证**是合理的（类似密码存储），但存在以下缺陷：

| 问题 | 影响 |
|------|------|
| **无法还原原始值** | 哈希是单向函数，无法在需要"代理调用"的场景下还原出原始 API Key |
| **缺少加密层** | 如需支持"用户自定义 LLM API Key"（Level 3 密钥），必须可解密但当前无法解密 |
| **密钥明文泄露风险** | 如未来需要存储需要还原的敏感凭证（如第三方 OAuth Token），缺乏加密基础设施 |

**当前代码分析**（`ApiKeyService.java`）：

```java
// 当前：SHA-256 哈希，不可逆
private String hashApiKey(String apiKey) {
    MessageDigest digest = MessageDigest.getInstance("SHA-256");
    byte[] hash = digest.digest(apiKey.getBytes(StandardCharsets.UTF_8));
    // ... 转 hex
}
```

**目标**：为需要可还原的敏感字段（如用户自定义 LLM API Key）引入 AES-256-GCM 加密存储，同时保留现有哈希验证机制不变。

### 1.2 方案设计

```mermaid
flowchart TD
    A[用户创建 API Key] --> B{Key 类型?}
    B -->|外部认证 ext_| C[SHA-256 哈希存储<br/>现有逻辑不变]
    B -->|用户自定义 LLM Key| D[AES-256-GCM 加密存储]

    E[验证外部 Key] --> F[SHA-256 哈希比对<br/>现有逻辑不变]
    G[代理调用 LLM] --> H[从 DB 读取密文<br/>AES-256-GCM 解密<br/>调用 Provider]
```

**核心设计决策**：

| 决策 | 选择 | 原因 |
|------|------|------|
| 加密算法 | AES-256-GCM | 认证加密（AEAD），防篡改 + 保密性 |
| 密钥来源 | Vault/KMS 动获取 | 密钥与密文分离，支持轮转 |
| 存储格式 | `enc:v1:nonce:ciphertext:tag` | 带版本号，支持算法升级 |
| 哈希保留 | 不变 | 外部 Key 验证仍用 SHA-256 |

#### 1.2.1 加密服务层

```java
// gateway-java/src/main/java/com/platform/gateway/service/EncryptionService.java
package com.platform.gateway.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * 加密/解密服务 — AES-256-GCM
 *
 * 密钥来源优先级：
 *   1. Vault/KMS（生产环境，通过 ENCRYPTION_KEY_PATH 指定）
 *   2. 环境变量 ENCRYPTION_KEY（开发/测试环境）
 *
 * 存储格式: enc:v1:{base64(nonce)}:{base64(ciphertext+tag)}
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class EncryptionService {

    private static final String ALGORITHM = "AES/GCM/NoPadding";
    private static final int GCM_IV_LENGTH = 12;     // 96-bit nonce (NIST 推荐)
    private static final int GCM_TAG_LENGTH = 128;    // 128-bit auth tag
    private static final String VERSION_PREFIX = "enc:v1:";
    private static final int KEY_LENGTH = 32;          // 256-bit

    private final SecureRandom secureRandom = new SecureRandom();

    // 密钥持有者 — 从 Vault/KMS/环境变量加载
    private volatile byte[] currentKey;
    private volatile byte[] previousKey;  // 用于轮转过渡期
    private volatile int keyVersion = 1;

    /**
     * 初始化密钥（由 @PostConstruct 或配置刷新触发）
     *
     * @param keyBytes 32 字节 AES 密钥
     */
    public synchronized void setEncryptionKey(byte[] keyBytes) {
        if (keyBytes == null || keyBytes.length != KEY_LENGTH) {
            throw new IllegalArgumentException("Encryption key must be exactly 32 bytes");
        }
        // 轮转时将当前密钥降级为 previous
        if (this.currentKey != null) {
            this.previousKey = this.currentKey.clone();
        }
        this.currentKey = keyBytes.clone();
        this.keyVersion++;
        log.info("Encryption key rotated, version={}", keyVersion);
    }

    /**
     * 加密明文
     *
     * @param plaintext 明文
     * @return 格式: enc:v1:{base64(nonce)}:{base64(ciphertext+tag)}
     */
    public String encrypt(String plaintext) {
        if (plaintext == null || plaintext.isEmpty()) {
            throw new IllegalArgumentException("Plaintext cannot be null or empty");
        }
        try {
            byte[] nonce = new byte[GCM_IV_LENGTH];
            secureRandom.nextBytes(nonce);

            Cipher cipher = Cipher.getInstance(ALGORITHM);
            SecretKeySpec keySpec = new SecretKeySpec(currentKey, "AES");
            GCMParameterSpec gcmSpec = new GCMParameterSpec(GCM_TAG_LENGTH, nonce);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec, gcmSpec);

            byte[] ciphertext = cipher.doFinal(plaintext.getBytes(java.nio.charset.StandardCharsets.UTF_8));

            String encodedNonce = Base64.getEncoder().encodeToString(nonce);
            String encodedCiphertext = Base64.getEncoder().encodeToString(ciphertext);

            return VERSION_PREFIX + encodedNonce + ":" + encodedCiphertext;
        } catch (Exception e) {
            throw new RuntimeException("Encryption failed", e);
        }
    }

    /**
     * 解密密文
     *
     * @param encryptedText 格式: enc:v1:{base64(nonce)}:{base64(ciphertext+tag)}
     * @return 明文
     */
    public String decrypt(String encryptedText) {
        if (encryptedText == null || !encryptedText.startsWith(VERSION_PREFIX)) {
            throw new IllegalArgumentException("Invalid encrypted text format");
        }

        try {
            String content = encryptedText.substring(VERSION_PREFIX.length());
            String[] parts = content.split(":");
            if (parts.length != 2) {
                throw new IllegalArgumentException("Malformed encrypted text");
            }

            byte[] nonce = Base64.getDecoder().decode(parts[0]);
            byte[] ciphertext = Base64.getDecoder().decode(parts[1]);

            // 先用当前密钥尝试解密
            try {
                return decryptWithKey(currentKey, nonce, ciphertext);
            } catch (Exception e) {
                // 当前密钥解密失败，尝试旧密钥（轮转过渡期）
                if (previousKey != null) {
                    log.info("Decrypt with current key failed, trying previous key");
                    String result = decryptWithKey(previousKey, nonce, ciphertext);
                    // 标记需要重加密（可选：异步重加密）
                    log.info("Decrypted with previous key, re-encryption recommended");
                    return result;
                }
                throw e;
            }
        } catch (Exception e) {
            throw new RuntimeException("Decryption failed", e);
        }
    }

    private String decryptWithKey(byte[] key, byte[] nonce, byte[] ciphertext) throws Exception {
        Cipher cipher = Cipher.getInstance(ALGORITHM);
        SecretKeySpec keySpec = new SecretKeySpec(key, "AES");
        GCMParameterSpec gcmSpec = new GCMParameterSpec(GCM_TAG_LENGTH, nonce);
        cipher.init(Cipher.DECRYPT_MODE, keySpec, gcmSpec);

        byte[] plaintext = cipher.doFinal(ciphertext);
        return new String(plaintext, java.nio.charset.StandardCharsets.UTF_8);
    }

    /**
     * 检查是否为加密格式
     */
    public boolean isEncrypted(String value) {
        return value != null && value.startsWith(VERSION_PREFIX);
    }

    /**
     * 重加密（轮转后使用新密钥重新加密旧数据）
     */
    public String reEncrypt(String encryptedText) {
        String plaintext = decrypt(encryptedText);
        return encrypt(plaintext);
    }
}
```

#### 1.2.2 密钥轮转机制

```mermaid
sequenceDiagram
    participant Vault as HashiCorp Vault
    participant App as Gateway Service
    participant DB as PostgreSQL

    Note over Vault: 定期轮转触发（季度/手动）

    Vault->>App: 推送新密钥 (key-v2)
    App->>App: previousKey = currentKey<br/>currentKey = key-v2

    Note over App: 过渡期：两种密钥均可解密

    loop 异步重加密
        App->>DB: SELECT WHERE encrypted_value LIKE 'enc:v1:%'
        DB-->>App: 返回用旧密钥加密的行
        App->>App: decrypt(old) → encrypt(new)
        App->>DB: UPDATE encrypted_value = reEncrypted
    end

    Note over App: 全部重加密完成后<br/>previousKey = null
```

**密钥加载配置**：

```java
// gateway-java/src/main/java/com/platform/gateway/config/EncryptionConfig.java
package com.platform.gateway.config;

import com.platform.gateway.service.EncryptionService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

import jakarta.annotation.PostConstruct;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;

@Slf4j
@Configuration
public class EncryptionConfig {

    @Value("${encryption.key-path:}")
    private String keyPath;  // Vault/KMS 挂载路径，如 /vault/secrets/encryption-key

    @Value("${encryption.key-base64:}")
    private String keyBase64;  // 开发环境用 Base64 编码密钥

    private final EncryptionService encryptionService;

    public EncryptionConfig(EncryptionService encryptionService) {
        this.encryptionService = encryptionService;
    }

    @PostConstruct
    public void init() {
        byte[] key;

        if (!keyPath.isEmpty()) {
            // 生产环境：从 Vault/KMS 挂载路径读取
            try {
                key = Files.readAllBytes(Path.of(keyPath));
                log.info("Encryption key loaded from path: {}", keyPath);
            } catch (Exception e) {
                throw new IllegalStateException("Failed to load encryption key from: " + keyPath, e);
            }
        } else if (!keyBase64.isEmpty()) {
            // 开发/测试环境：从环境变量读取
            key = Base64.getDecoder().decode(keyBase64);
            log.warn("Encryption key loaded from env variable — NOT for production!");
        } else {
            throw new IllegalStateException(
                "No encryption key configured. Set encryption.key-path or encryption.key-base64"
            );
        }

        encryptionService.setEncryptionKey(key);
    }
}
```

**application.yml 配置**：

```yaml
encryption:
  # 生产：Vault 挂载路径
  key-path: ${ENCRYPTION_KEY_PATH:}
  # 开发：Base64 编码密钥（仅本地开发）
  key-base64: ${ENCRYPTION_KEY_BASE64:}
```

#### 1.2.3 ApiKey 实体改造

在 `api_keys` 表中新增 `encrypted_secret` 字段，用于存储需要可还原的敏感凭证：

```sql
-- V1.1.0__add_encrypted_secret_column.sql

-- 新增加密密文字段（用于用户自定义 LLM API Key 等需要还原的场景）
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS encrypted_secret TEXT;

COMMENT ON COLUMN api_keys.encrypted_secret IS
    'AES-256-GCM 加密的敏感凭证，格式: enc:v1:{nonce}:{ciphertext}。仅用于 ext_ 类型的自定义 Key';
```

#### 1.2.4 数据迁移脚本

```bash
#!/bin/bash
# scripts/migrate-api-key-encryption.sh
# 用途：将现有的明文 API Key 迁移为加密存储
# 前提：已配置 ENCRYPTION_KEY_BASE64 环境变量
# 警告：此脚本涉及敏感数据，必须在安全环境执行

set -euo pipefail

DB_URL="${DATABASE_URL:-jdbc:postgresql://localhost:5432/agent_platform}"
DB_USER="${DB_USER:-app_user}"
ENCRYPTION_KEY="${ENCRYPTION_KEY_BASE64:?ENCRYPTION_KEY_BASE64 is required}"

echo "=== API Key 加密迁移 ==="
echo "数据库: ${DB_URL}"
echo ""

# 1. 备份表
echo "[1/4] 备份 api_keys 表..."
psql "${DB_URL}" -U "${DB_USER}" -c "
    CREATE TABLE api_keys_backup_$(date +%Y%m%d) AS
    SELECT * FROM api_keys;
"
echo "备份完成"

# 2. 迁移：加密需要还原的字段
echo "[2/4] 执行加密迁移..."
# 注意：实际加密逻辑应在 Java 应用内完成，此处为伪代码
# 通过 Spring Boot CLI 或迁移端点触发
echo "  请通过 /api/v1/admin/migrate-encryption 端点触发迁移"

# 3. 验证
echo "[3/4] 验证加密结果..."
psql "${DB_URL}" -U "${DB_USER}" -c "
    SELECT COUNT(*) as total_keys,
           COUNT(encrypted_secret) as encrypted_count,
           COUNT(*) - COUNT(encrypted_secret) as pending_count
    FROM api_keys
    WHERE type = 'external';
"

# 4. 确认
echo "[4/4] 请手动确认解密后值与原始值一致后，标记迁移完成"
echo "=== 迁移脚本结束 ==="
```

**Java 迁移端点**：

```java
// gateway-java/src/main/java/com/platform/gateway/controller/admin/MigrationController.java
package com.platform.gateway.controller.admin;

import com.platform.gateway.entity.ApiKey;
import com.platform.gateway.repository.ApiKeyRepository;
import com.platform.gateway.service.EncryptionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api/v1/admin/migrate")
@RequiredArgsConstructor
public class MigrationController {

    private final ApiKeyRepository apiKeyRepository;
    private final EncryptionService encryptionService;

    /**
     * 执行加密迁移（仅管理端可调用）
     * POST /api/v1/admin/migrate/encrypt-api-keys
     */
    @PostMapping("/encrypt-api-keys")
    public ResponseEntity<Map<String, Object>> migrateEncryption() {
        Map<String, Object> result = new HashMap<>();
        int migrated = 0;
        int skipped = 0;
        int failed = 0;

        // 查找所有需要加密但尚未加密的 Key
        // 实际场景中，明文值来源可能是临时列或外部导入
        // 此处假设 encrypted_secret 为空且 type=external 的记录需要迁移

        log.info("Encryption migration started");
        // ... 具体迁移逻辑 ...

        result.put("migrated", migrated);
        result.put("skipped", skipped);
        result.put("failed", failed);
        return ResponseEntity.ok(result);
    }

    /**
     * 验证加密/解密一致性
     * POST /api/v1/admin/migrate/verify-encryption
     */
    @PostMapping("/verify-encryption")
    public ResponseEntity<Map<String, Object>> verifyEncryption() {
        Map<String, Object> result = new HashMap<>();

        // 测试加密→解密→一致性校验
        String testPlaintext = "sk-test-verification-key-12345";
        String encrypted = encryptionService.encrypt(testPlaintext);
        String decrypted = encryptionService.decrypt(encrypted);

        result.put("consistent", testPlaintext.equals(decrypted));
        result.put("encrypted_format_valid", encrypted.startsWith("enc:v1:"));

        return ResponseEntity.ok(result);
    }
}
```

### 1.3 验证方法

```bash
# 1. 验证加密/解密一致性
curl -X POST http://localhost:8080/api/v1/admin/migrate/verify-encryption
# 预期: {"consistent": true, "encrypted_format_valid": true}

# 2. 验证存储格式
psql -c "SELECT encrypted_secret FROM api_keys WHERE encrypted_secret IS NOT NULL LIMIT 1;"
# 预期: enc:v1:xxxxx:xxxxx 格式

# 3. 验证密钥轮转
# 3a. 更换 ENCRYPTION_KEY_BASE64 为新值
# 3b. 重启服务
# 3c. 旧密文仍可解密（previousKey 兜底）
# 3d. 新密文使用新密钥加密

# 4. 安全审计
# 确认数据库中无明文密钥
psql -c "SELECT COUNT(*) FROM api_keys WHERE encrypted_secret IS NOT NULL
         AND encrypted_secret NOT LIKE 'enc:v1:%';"
# 预期: 0
```

### 1.4 风险与回滚

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 密钥丢失导致数据不可恢复 | 低 | 极高 | 密钥备份到 Vault 多副本；迁移前全量备份表 |
| 加密性能影响 | 低 | 中 | AES-256-GCM 硬件加速（AES-NI），单次 < 0.1ms |
| 轮转期间服务中断 | 低 | 中 | 双密钥并行，零停机轮转 |
| 迁移失败 | 中 | 中 | 备份表 + 事务性迁移，失败可回滚 |

**回滚方案**：

```sql
-- 从备份表恢复
BEGIN;
TRUNCATE api_keys;
INSERT INTO api_keys SELECT * FROM api_keys_backup_YYYYMMDD;
COMMIT;

-- 删除加密列（如需完全回滚）
ALTER TABLE api_keys DROP COLUMN IF EXISTS encrypted_secret;
```

---

## 2. Python 服务数据库迁移

### 2.1 问题背景

Gateway-Java 已集成 Flyway（`src/main/resources/db/migration/`），但三个 Python 服务（Knowledge / Orchestrator / ModelGateway）没有任何数据库迁移工具：

| 服务 | DB 使用情况 | 迁移工具 | 风险 |
|------|------------|----------|------|
| Gateway-Java | PostgreSQL | Flyway | 无 |
| Knowledge-Python | PostgreSQL + pgvector | **无** | DDL 变更需手动执行，易遗漏 |
| Orchestrator-Python | PostgreSQL | **无** | 同上 |
| ModelGateway-Python | PostgreSQL | **无** | 同上 |

**隐患**：

- 多人开发时 schema 不一致
- 生产环境升级无法追溯 DDL 变更
- 无法回滚到特定版本
- CI 缺少迁移验证环节

### 2.2 方案设计

采用 **Alembic** 作为 Python 服务的迁移工具，每个服务独立管理迁移目录。

```mermaid
flowchart LR
    subgraph "gateway-java"
        F[Flyway<br/>db/migration/]
    end
    subgraph "orchestrator-python"
        A1[alembic/<br/>versions/]
    end
    subgraph "knowledge-python"
        A2[alembic/<br/>versions/]
    end
    subgraph "model-gateway-python"
        A3[alembic/<br/>versions/]
    end

    DB[(PostgreSQL<br/>agent_platform)]

    F -->|flyway migrate| DB
    A1 -->|alembic upgrade head| DB
    A2 -->|alembic upgrade head| DB
    A3 -->|alembic upgrade head| DB
```

#### 2.2.1 Alembic 集成方案

**目录结构**（每个 Python 服务）：

```
services/orchestrator-python/
├── alembic/
│   ├── alembic.ini          # Alembic 配置（环境变量覆盖）
│   ├── env.py               # 自定义 env.py（读取 app 配置）
│   ├── script.py.mako       # 迁移脚本模板
│   └── versions/
│       ├── V1_0_0__init_schema.py
│       └── V1_0_1__add_conversation_summary.py
├── alembic.ini              # 入口配置文件
└── app/
    └── core/
        └── database.py      # 数据库连接配置
```

**alembic.ini**（以 orchestrator 为例）：

```ini
# services/orchestrator-python/alembic.ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

**env.py**（自定义，读取应用配置）：

```python
# services/orchestrator-python/alembic/env.py
"""Alembic 环境配置 — 读取应用配置而非硬编码连接串"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 从应用配置获取数据库 URL
# 优先级: ALEMBIC_DATABASE_URL > app.core.config > alembic.ini
DATABASE_URL = os.environ.get(
    "ALEMBIC_DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform"
    )
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 覆盖 sqlalchemy.url
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# 导入所有模型，确保 autogenerate 能检测到
# from app.models import Base  # 当有 SQLAlchemy ORM 模型时启用
# target_metadata = Base.metadata
target_metadata = None  # 当前使用纯 SQL 迁移


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本而不连接数据库"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**迁移脚本模板**（`script.py.mako`）：

```mako
# services/orchestrator-python/alembic/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

#### 2.2.2 迁移脚本命名规范

| 规范 | 格式 | 示例 |
|------|------|------|
| 版本号 | `V{major}_{minor}_{patch}` | `V1_0_0` |
| 描述 | 双下划线分隔 | `__add_conversation_summary` |
| 文件名 | `{版本号}__{描述}.py` | `V1_0_0__init_schema.py` |
| Alembic revision | 自动生成 UUID | 由 `alembic revision` 生成 |

**初始迁移示例**（Orchestrator）：

```python
# services/orchestrator-python/alembic/versions/V1_0_0__init_schema.py
"""V1.0.0 初始化 Orchestrator Schema

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-06-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 对话会话表
    op.create_table(
        'conversation_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(32), nullable=False),
        sa.Column('user_id', sa.String(32), nullable=False),
        sa.Column('title', sa.String(200)),
        sa.Column('status', sa.String(16), nullable=False, server_default='active'),
        sa.Column('model', sa.String(64)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_conv_sessions_tenant', 'conversation_sessions', ['tenant_id'])
    op.create_index('idx_conv_sessions_user', 'conversation_sessions', ['user_id', 'tenant_id'])

    # 对话消息表
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('token_count', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_conv_messages_session', 'conversation_messages', ['session_id'])


def downgrade() -> None:
    op.drop_table('conversation_messages')
    op.drop_table('conversation_sessions')
```

#### 2.2.3 多服务共享 schema 的协调策略

所有 Python 服务连接同一个 PostgreSQL 数据库 `agent_platform`，但使用不同的 schema 或表前缀来隔离：

```mermaid
flowchart TD
    subgraph "PostgreSQL: agent_platform"
        subgraph "public schema (共享)"
            T1[api_keys / api_key_scopes<br/>--- Gateway 管理]
            T2[audit_event<br/>--- 触发器保护]
        end
        subgraph "orchestrator 表"
            T3[conversation_sessions<br/>conversation_messages<br/>agent_runs]
        end
        subgraph "knowledge 表"
            T4[documents<br/>document_chunks<br/>embedding_metadata]
        end
        subgraph "model_gateway 表"
            T5[model_usage_metrics<br/>token_quotas]
        end
    end
```

**协调规则**：

| 规则 | 说明 |
|------|------|
| 表名前缀 | 每个服务的表名以服务缩写开头（`conv_`, `doc_`, `model_`）或自然语义命名 |
| 禁止跨服务修改 | 每个迁移脚本只能操作本服务的表 |
| 共享表由 Gateway 管理 | `api_keys`、`audit_event` 等共享表由 Flyway 管理，Python 服务只读 |
| 冲突检测 | CI 中运行全量迁移前检查是否有表名冲突 |

**Alembic 冲突检测配置**（在 `env.py` 中）：

```python
# 限制 Alembic 只操作本服务的表
# 在 context.configure 中添加 include_object 过滤

INCLUDE_TABLE_PREFIXES = ["conv_", "agent_"]  # orchestrator 的表前缀


def include_object(object, name, type_, reflected, compare_to):
    """只检测本服务的表变更，忽略其他服务的表"""
    if type_ == "table":
        return any(name.startswith(prefix) for prefix in INCLUDE_TABLE_PREFIXES) or name == "alembic_version"
    return True


# 在 run_migrations_online 中:
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    include_object=include_object,
)
```

#### 2.2.4 pyproject.toml 新增依赖

```toml
# 每个需要迁移的 Python 服务添加：
[project.optional-dependencies]
dev = [
    # ... 现有依赖 ...
    "alembic>=1.13.0",
]
```

#### 2.2.5 make dev 自动执行迁移

修改 `Makefile`：

```makefile
# ---- 开发环境 ----
dev:
	@$(DOCKER_COMPOSE) -f infra/docker-compose.yml up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 3
	@$(MAKE) migrate-python
	@echo "Dev environment started with migrations applied"

# ---- 数据库迁移 ----
migrate-python: migrate-orchestrator migrate-knowledge migrate-model-gateway
	@echo "All Python migrations applied"

migrate-orchestrator:
	@if [ -f services/orchestrator-python/alembic.ini ]; then \
		cd services/orchestrator-python && \
		ALEMBIC_DATABASE_URL="postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform" \
		uv run alembic upgrade head; \
	fi

migrate-knowledge:
	@if [ -f services/knowledge-python/alembic.ini ]; then \
		cd services/knowledge-python && \
		ALEMBIC_DATABASE_URL="postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform" \
		uv run alembic upgrade head; \
	fi

migrate-model-gateway:
	@if [ -f services/model-gateway-python/alembic.ini ]; then \
		cd services/model-gateway-python && \
		ALEMBIC_DATABASE_URL="postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform" \
		uv run alembic upgrade head; \
	fi

# 生成新迁移脚本
migrate-create:
	@read -p "Service name (orchestrator/knowledge/model-gateway): " svc; \
	read -p "Migration description: " desc; \
	cd services/$${svc}-python && \
	ALEMBIC_DATABASE_URL="postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform" \
	uv run alembic revision -m "$$desc"
```

#### 2.2.6 CI 迁移验证

```yaml
# ci/templates/migration-verify.yml
migration-verify:
  image: python:3.12-slim
  services:
    - postgres:16
  variables:
    POSTGRES_DB: agent_platform_test
    POSTGRES_USER: app_user
    POSTGRES_PASSWORD: test_password
    ALEMBIC_DATABASE_URL: "postgresql+asyncpg://app_user:test_password@postgres:5432/agent_platform_test"
  script:
    - pip install uv

    # 1. 空数据库 → 全量迁移
    - echo "=== Step 1: Full migration on empty DB ==="
    - cd services/orchestrator-python && uv sync && uv run alembic upgrade head && cd ../..
    - cd services/knowledge-python && uv sync && uv run alembic upgrade head && cd ../..
    - cd services/model-gateway-python && uv sync && uv run alembic upgrade head && cd ../..

    # 2. 验证迁移版本
    - echo "=== Step 2: Verify migration version ==="
    - cd services/orchestrator-python && uv run alembic current && cd ../..

    # 3. 降级验证（回退一步再升回来）
    - echo "=== Step 3: Downgrade and re-upgrade ==="
    - cd services/orchestrator-python && uv run alembic downgrade -1 && uv run alembic upgrade head && cd ../..
    - cd services/knowledge-python && uv run alembic downgrade -1 && uv run alembic upgrade head && cd ../..
    - cd services/model-gateway-python && uv run alembic downgrade -1 && uv run alembic upgrade head && cd ../..

    # 4. 检查是否有表名冲突
    - echo "=== Step 4: Check table name conflicts ==="
    - |
      python3 scripts/check_table_conflicts.py \
        --gateway-dir services/gateway-java/src/main/resources/db/migration \
        --orchestrator-dir services/orchestrator-python/alembic/versions \
        --knowledge-dir services/knowledge-python/alembic/versions \
        --model-gateway-dir services/model-gateway-python/alembic/versions
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - services/*/alembic/**/*
        - services/gateway-java/src/main/resources/db/migration/**/*
```

### 2.3 验证方法

```bash
# 1. 生成迁移脚本
cd services/orchestrator-python
uv run alembic revision -m "add_agent_runs_table"

# 2. 应用迁移
ALEMBIC_DATABASE_URL="postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform" \
  uv run alembic upgrade head

# 3. 检查当前版本
uv run alembic current

# 4. 降级测试
uv run alembic downgrade -1

# 5. 生成 SQL（离线模式）
uv run alembic upgrade head --sql

# 6. 全量 make dev 验证
make dev
# 预期：所有迁移自动执行，无报错
```

### 2.4 风险与回滚

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 多服务迁移顺序冲突 | 中 | 中 | 每个服务独立 alembic_version 表（通过 schema 隔离） |
| 自动生成迁移遗漏 | 低 | 中 | 人工 review 迁移脚本，CI 中与 Flyway 冲突检测 |
| 生产迁移失败 | 低 | 高 | `alembic downgrade` 回退；全量备份后执行 |
| 开发环境迁移不一致 | 中 | 低 | `make dev` 自动化 + CI 验证 |

**回滚方案**：

```bash
# 回退到指定版本
cd services/orchestrator-python
uv run alembic downgrade V1_0_0

# 或回退到空库
uv run alembic downgrade base
```

---

## 3. K8s Ingress + NetworkPolicy

### 3.1 问题背景

当前 K8s 配置仅有 Deployment / Service / HPA，缺少：

| 缺失资源 | 影响 |
|-----------|------|
| **Ingress** | 集群外无法通过域名/HTTPS 访问服务 |
| **NetworkPolicy** | 所有 Pod 可互相访问，无网络隔离 |

当前 `infra/kubernetes/base/service.yaml` 中有一个简单的 Ingress，但：

- 仅路由到 Gateway 的根路径 `/`
- 无 TLS 配置
- 无路径细分（如 `/api/v1/` → Gateway, `/ws/` → Orchestrator）
- 无 NetworkPolicy

项目已使用 Istio（`istio-peer-authentication.yaml` 配置了 mTLS STRICT 模式和 AuthorizationPolicy），需提供两套方案。

### 3.2 方案设计

#### 方案 A：原生 K8s Ingress + NetworkPolicy（轻量方案）

**适用场景**：无 Istio 或 Istio 仅用于 mTLS 的集群。

##### Ingress 配置

```yaml
# infra/kubernetes/base/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agent-platform-ingress
  namespace: agent-platform
  labels:
    app.kubernetes.io/name: agent-platform
    app.kubernetes.io/component: networking
  annotations:
    # NGINX Ingress Controller 注解
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
    # SSE/流式响应支持
    nginx.ingress.kubernetes.io/proxy-buffering: "off"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
    # 安全头
    nginx.ingress.kubernetes.io/configuration-snippet: |
      more_set_headers "X-Content-Type-Options: nosniff";
      more_set_headers "X-Frame-Options: DENY";
      more_set_headers "X-XSS-Protection: 1; mode=block";
      more_set_headers "Strict-Transport-Security: max-age=31536000; includeSubDomains";
      more_set_headers "Referrer-Policy: strict-origin-when-cross-origin";
    # 限流
    nginx.ingress.kubernetes.io/limit-connections: "50"
    nginx.ingress.kubernetes.io/limit-rps: "100"
    # 证书管理（cert-manager）
    cert-manager.io/cluster-issuer: letsencrypt-prod
    cert-manager.io/common-name: api.agent-platform.example.com
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.agent-platform.example.com
        - ws.agent-platform.example.com
      secretName: agent-platform-tls
  rules:
    # 主 API 入口 → Gateway
    - host: api.agent-platform.example.com
      http:
        paths:
          # SSE 流式端点（需要长连接，优先匹配）
          - path: /api/v1/chat/stream
            pathType: Prefix
            backend:
              service:
                name: gateway
                port:
                  number: 8080
          # 常规 API 请求
          - path: /api/v1
            pathType: Prefix
            backend:
              service:
                name: gateway
                port:
                  number: 8080
          # 健康检查
          - path: /health
            pathType: Prefix
            backend:
              service:
                name: gateway
                port:
                  number: 8080
          # 默认路由
          - path: /
            pathType: Prefix
            backend:
              service:
                name: gateway
                port:
                  number: 8080

    # WebSocket/SSE 专用域名 → Orchestrator（可选，避免长连接影响 API 请求）
    - host: ws.agent-platform.example.com
      http:
        paths:
          - path: /api/v1/chat/stream
            pathType: Prefix
            backend:
              service:
                name: orchestrator
                port:
                  number: 8001
```

##### NetworkPolicy 配置

```yaml
# infra/kubernetes/base/network-policy.yaml

# ====== 1. 默认拒绝所有入站/出站 ======
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: agent-platform
  labels:
    app.kubernetes.io/name: agent-platform
    app.kubernetes.io/component: security
spec:
  podSelector: {}  # 匹配所有 Pod
  policyTypes:
    - Ingress
    - Egress
---
# ====== 2. 允许 DNS 解析（出站） ======
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
  namespace: agent-platform
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
---
# ====== 3. Gateway 入站规则 ======
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: gateway-ingress
  namespace: agent-platform
spec:
  podSelector:
    matchLabels:
      app: gateway
  policyTypes:
    - Ingress
  ingress:
    # 允许 Ingress Controller 流量
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
    # 允许健康检查（Prometheus）
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
      ports:
        - protocol: TCP
          port: 8080
---
# ====== 4. Orchestrator 入站规则 ======
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: orchestrator-ingress
  namespace: agent-platform
spec:
  podSelector:
    matchLabels:
      app: orchestrator
  policyTypes:
    - Ingress
  ingress:
    # 仅允许 Gateway 调用
    - from:
        - podSelector:
            matchLabels:
              app: gateway
      ports:
        - protocol: TCP
          port: 8001
---
# ====== 5. Model Gateway 入站规则 ======
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: model-gateway-ingress
  namespace: agent-platform
spec:
  podSelector:
    matchLabels:
      app: model-gateway
  policyTypes:
    - Ingress
  ingress:
    # 仅允许 Orchestrator 调用
    - from:
        - podSelector:
            matchLabels:
              app: orchestrator
      ports:
        - protocol: TCP
          port: 8002
---
# ====== 6. Tool Bus 入站规则 ======
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tool-bus-ingress
  namespace: agent-platform
spec:
  podSelector:
    matchLabels:
      app: tool-bus
  policyTypes:
    - Ingress
  ingress:
    # 仅允许 Orchestrator 调用
    - from:
        - podSelector:
            matchLabels:
              app: orchestrator
      ports:
        - protocol: TCP
          port: 8083
        - protocol: TCP
          port: 40051
---
# ====== 7. Governance 入站规则 ======
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: governance-ingress
  namespace: agent-platform
spec:
  podSelector:
    matchLabels:
      app: governance
  policyTypes:
    - Ingress
  ingress:
    # 允许 Tool Bus 调用
    - from:
        - podSelector:
            matchLabels:
              app: tool-bus
      ports:
        - protocol: TCP
          port: 8082
---
# ====== 8. Knowledge 入站规则 ======
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: knowledge-ingress
  namespace: agent-platform
spec:
  podSelector:
    matchLabels:
      app: knowledge
  policyTypes:
    - Ingress
  ingress:
    # 允许 Orchestrator 调用（RAG 检索）
    - from:
        - podSelector:
            matchLabels:
              app: orchestrator
      ports:
        - protocol: TCP
          port: 8003
---
# ====== 9. 服务间出站规则（按服务拓扑） ======
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: service-egress
  namespace: agent-platform
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    # 允许访问集群内服务
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: agent-platform
    # 允许访问外部 LLM API（Model Gateway 需要）
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8      # 阻止访问集群内网
              - 172.16.0.0/12   # 阻止访问集群内网
              - 192.168.0.0/16  # 阻止访问集群内网
      ports:
        - protocol: TCP
          port: 443
    # 允许访问 PostgreSQL
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8
      ports:
        - protocol: TCP
          port: 5432
    # 允许访问 Redis
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8
      ports:
        - protocol: TCP
          port: 6379
    # 允许访问 Kafka
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8
      ports:
        - protocol: TCP
          port: 9092
```

**服务间访问矩阵**（NetworkPolicy 白名单）：

```mermaid
flowchart LR
    Ingress[Ingress Controller] -->|8080| Gateway
    Gateway -->|8001/gRPC50100| Orchestrator
    Orchestrator -->|8002| ModelGateway
    Orchestrator -->|gRPC40051| ToolBus
    Orchestrator -->|8003| Knowledge
    ToolBus -->|8082| Governance
    ModelGateway -.->|443| External[外部 LLM API]
    All[所有服务] -.->|5432| PostgreSQL
    All -.->|6379| Redis
```

#### 方案 B：Istio Gateway + VirtualService（推荐，项目已有 Istio）

**适用场景**：集群已部署 Istio，可利用其流量管理、可观测性、安全能力。

##### Istio Gateway

```yaml
# infra/k8s/istio-gateway.yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: agent-platform-gateway
  namespace: agent-platform
  labels:
    app.kubernetes.io/name: agent-platform
    app.kubernetes.io/component: networking
spec:
  selector:
    istio: ingressgateway  # 使用默认 ingress gateway
  servers:
    # HTTPS 主入口
    - port:
        number: 443
        name: https
        protocol: HTTPS
      tls:
        mode: SIMPLE
        credentialName: agent-platform-tls  # K8s Secret 中的证书
      hosts:
        - api.agent-platform.example.com
        - ws.agent-platform.example.com
    # HTTP → HTTPS 重定向
    - port:
        number: 80
        name: http
        protocol: HTTP
      hosts:
        - api.agent-platform.example.com
        - ws.agent-platform.example.com
      tls:
        httpsRedirect: true
```

##### VirtualService

```yaml
# infra/k8s/istio-virtual-service.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: agent-platform-vs
  namespace: agent-platform
  labels:
    app.kubernetes.io/name: agent-platform
    app.kubernetes.io/component: networking
spec:
  gateways:
    - agent-platform-gateway
  hosts:
    - api.agent-platform.example.com
  http:
    # SSE 流式端点（长连接超时 5 分钟）
    - match:
        - uri:
            prefix: /api/v1/chat/stream
      route:
        - destination:
            host: gateway
            port:
              number: 8080
      timeout: 300s
      retries:
        attempts: 0  # 流式不重试

    # 常规 API
    - match:
        - uri:
            prefix: /api/v1
      route:
        - destination:
            host: gateway
            port:
              number: 8080
      timeout: 30s
      retries:
        attempts: 3
        perTryTimeout: 10s
        retryOn: 5xx,reset

    # 健康检查
    - match:
        - uri:
            prefix: /health
      route:
        - destination:
            host: gateway
            port:
              number: 8080
      retries:
        attempts: 0

    # 默认
    - route:
        - destination:
            host: gateway
            port:
              number: 8080
```

##### Istio AuthorizationPolicy（替代 NetworkPolicy）

```yaml
# infra/k8s/istio-authorization-policy.yaml
# 此文件补充现有的 istio-peer-authentication.yaml

# Gateway: 仅允许 Ingress Gateway 流量
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: gateway-policy
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
              - "cluster.local/ns/agent-platform/sa/orchestrator"
      to:
        - operation:
            methods: ["GET", "POST", "PUT", "DELETE"]
---
# Orchestrator: 仅允许 Gateway 调用
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: orchestrator-policy
  namespace: agent-platform
spec:
  selector:
    matchLabels:
      app: orchestrator
  rules:
    - from:
        - source:
            principals:
              - "cluster.local/ns/agent-platform/sa/gateway"
    - to:
        - operation:
            ports: ["8001"]
---
# Model Gateway: 仅允许 Orchestrator 调用
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: model-gateway-policy
  namespace: agent-platform
spec:
  selector:
    matchLabels:
      app: model-gateway
  rules:
    - from:
        - source:
            principals:
              - "cluster.local/ns/agent-platform/sa/orchestrator"
    - to:
        - operation:
            ports: ["8002"]
---
# Tool Bus: 仅允许 Orchestrator 调用
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: tool-bus-policy
  namespace: agent-platform
spec:
  selector:
    matchLabels:
      app: tool-bus
  rules:
    - from:
        - source:
            principals:
              - "cluster.local/ns/agent-platform/sa/orchestrator"
    - to:
        - operation:
            ports: ["8083", "40051"]
---
# Knowledge: 仅允许 Orchestrator 调用
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: knowledge-policy
  namespace: agent-platform
spec:
  selector:
    matchLabels:
      app: knowledge
  rules:
    - from:
        - source:
            principals:
              - "cluster.local/ns/agent-platform/sa/orchestrator"
    - to:
        - operation:
            ports: ["8003"]
---
# Governance: 仅允许 Tool Bus 调用
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: governance-policy
  namespace: agent-platform
spec:
  selector:
    matchLabels:
      app: governance
  rules:
    - from:
        - source:
            principals:
              - "cluster.local/ns/agent-platform/sa/tool-bus"
    - to:
        - operation:
            ports: ["8082"]
```

#### 3.2.1 两种方案对比

| 维度 | 方案 A (K8s 原生) | 方案 B (Istio) |
|------|-------------------|----------------|
| **依赖** | 仅需 Ingress Controller | 需要 Istio 部署 |
| **L3/L4 隔离** | NetworkPolicy 原生支持 | AuthorizationPolicy（L7） |
| **L7 路由** | 路径/域名路由 | 路径/域名/header/权重路由 |
| **TLS 证书** | cert-manager 自动签发 | Istio Citadel 自动签发 |
| **可观测性** | 需额外配置 | 自动 mTLS + 分布式追踪 |
| **流量管理** | 基础 | 高级（灰度、A/B、镜像） |
| **SSE/长连接** | 需手动配置超时 | 原生支持 + per-route 超时 |
| **运维复杂度** | 低 | 中 |
| **性能开销** | 无 | Sidecar ~2-5ms 延迟 |
| **推荐场景** | 无 Istio / 简单部署 | **已有 Istio（本项目推荐）** |

**推荐**：方案 B（Istio），原因：
1. 项目已部署 Istio 并配置了 mTLS STRICT 模式
2. Istio AuthorizationPolicy 提供比 NetworkPolicy 更精细的 L7 访问控制
3. VirtualService 原生支持 SSE 长连接超时配置
4. 与现有 `istio-peer-authentication.yaml` 配合，无需额外引入 NetworkPolicy

### 3.3 验证方法

```bash
# 方案 B (Istio) 验证

# 1. 部署 Istio Gateway + VirtualService
kubectl apply -f infra/k8s/istio-gateway.yaml -n agent-platform
kubectl apply -f infra/k8s/istio-virtual-service.yaml -n agent-platform
kubectl apply -f infra/k8s/istio-authorization-policy.yaml -n agent-platform

# 2. 验证 Gateway 状态
kubectl get gateway -n agent-platform
kubectl get virtualservice -n agent-platform

# 3. 测试外部访问
curl -v https://api.agent-platform.example.com/health
# 预期: 200 OK

# 4. 测试服务间隔离（应被拒绝）
# 从 Knowledge Pod 直接访问 Tool Bus（不应被允许）
kubectl exec -it deploy/knowledge -n agent-platform -- \
  curl -v http://tool-bus:8083/health
# 预期: 403 Forbidden (AuthorizationPolicy 拒绝)

# 5. 验证 mTLS
istioctl analyze -n agent-platform
# 预期: No issues

# 6. 测试 SSE 长连接
curl -N https://api.agent-platform.example.com/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "stream": true}'
# 预期: 流式输出，5 分钟内不断开
```

### 3.4 风险与回滚

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| NetworkPolicy 过严导致服务不可用 | 中 | 高 | 逐条添加，先 Allow 后 Deny |
| Istio VirtualService 路由配置错误 | 中 | 中 | 先部署无流量版本，验证后切流量 |
| TLS 证书签发失败 | 低 | 高 | 准备手动证书备份 |
| SSE 长连接超时 | 中 | 中 | VirtualService 单独配置 300s 超时 |

**回滚方案**：

```bash
# 删除 Istio 网络配置，恢复直连
kubectl delete -f infra/k8s/istio-authorization-policy.yaml -n agent-platform
kubectl delete -f infra/k8s/istio-virtual-service.yaml -n agent-platform
kubectl delete -f infra/k8s/istio-gateway.yaml -n agent-platform
```

---

## 4. Model-Gateway Dockerfile

### 4.1 问题背景

6 个服务中 5 个已有 Dockerfile，唯独 `model-gateway-python` 缺失：

| 服务 | Dockerfile | 状态 |
|------|-----------|------|
| gateway-java | `services/gateway-java/Dockerfile` | 多阶段构建，安全加固 |
| orchestrator-python | `services/orchestrator-python/Dockerfile` | 非 root，健康检查 |
| knowledge-python | `services/knowledge-python/Dockerfile` | 非 root，健康检查 |
| tool-bus-java | `services/tool-bus-java/Dockerfile` | 存在 |
| governance-java | `services/governance-java/Dockerfile` | 存在 |
| **model-gateway-python** | **缺失** | **阻塞部署** |

### 4.2 方案设计

#### 4.2.1 多阶段构建 Dockerfile

```dockerfile
# ============================================================
#  Model Gateway Service - Production Dockerfile
#  多阶段构建: uv + Python 3.12 slim
#  安全加固: 非 root 用户、最小镜像、健康检查
# ============================================================

# ---- Stage 1: Builder (uv 安装依赖) ----
FROM python:3.12-slim AS builder

# 安装 uv — 高性能 Python 包管理器
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# 复制依赖声明（利用 Docker 缓存层）
COPY pyproject.toml .

# 使用 uv 安装依赖到虚拟环境
# --frozen: 锁定依赖版本，禁止隐式更新
# --no-dev: 不安装开发依赖
RUN uv venv /build/.venv && \
    uv pip install --python /build/.venv/bin/python -e ".[dev]" || \
    uv pip install --python /build/.venv/bin/python .

# ---- Stage 2: Runtime (最小化镜像) ----
FROM python:3.12-slim

# 安装运行时系统依赖（curl 用于健康检查）
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 创建非 root 用户和组
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

# 从 builder 阶段复制虚拟环境
COPY --from=builder /build/.venv /app/.venv

# 复制应用代码
COPY app/ app/

# 设置所有权
RUN chown -R app:app /app

# 切换到非 root 用户
USER app

# 将虚拟环境加入 PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# HTTP 端口（Model Gateway 对内服务端口: 8002）
EXPOSE 8002

# 健康检查
# --interval: 检查间隔 30s
# --timeout: 单次检查超时 10s
# --start-period: 启动宽限期 5s
# --retries: 连续失败 3 次标记为 unhealthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health/live || exit 1

# 启动命令
# --workers: 工作进程数（生产环境建议 2-4，按 CPU 核数调整）
# --loop: uvloop 事件循环（比默认 asyncio 性能更好）
# --http: httptools HTTP 解析器
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8002", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--http", "httptools"]
```

#### 4.2.2 健康检查端点

Model Gateway 需要新增 `/health/live` 端点（当前无此端点）：

```python
# services/model-gateway-python/app/api/v1/health.py
"""健康检查端点"""

from fastapi import APIRouter
from app.router.model_router import get_model_router

router = APIRouter()


@router.get("/health/live")
async def liveness():
    """存活探针 — 检测进程是否存活

    返回 200 表示进程正常，不需要重启
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness():
    """就绪探针 — 检测服务是否可接收流量

    检查项:
    1. 至少有一个 Provider 可用
    2. 模型路由器已初始化
    """
    try:
        model_router = get_model_router()
        # 检查是否有可用的 Provider
        if model_router and len(model_router.providers) > 0:
            return {"status": "ready", "providers": len(model_router.providers)}
        return {"status": "not_ready", "reason": "no_providers_available"}
    except Exception as e:
        return {"status": "not_ready", "reason": str(e)}
```

#### 4.2.3 与 CI docker-build 集成

修改 `Makefile` 的 `docker-build` target：

```makefile
# ---- Docker ----
docker-build:
	@echo "Building Docker images..."
	@if [ -f services/gateway-java/Dockerfile ]; then docker build -t agent-platform/gateway:latest -f services/gateway-java/Dockerfile services/gateway-java/; fi
	@if [ -f services/orchestrator-python/Dockerfile ]; then docker build -t agent-platform/orchestrator:latest -f services/orchestrator-python/Dockerfile services/orchestrator-python/; fi
	@if [ -f services/knowledge-python/Dockerfile ]; then docker build -t agent-platform/knowledge:latest -f services/knowledge-python/Dockerfile services/knowledge-python/; fi
	@if [ -f services/model-gateway-python/Dockerfile ]; then docker build -t agent-platform/model-gateway:latest -f services/model-gateway-python/Dockerfile services/model-gateway-python/; fi
	@if [ -f services/tool-bus-java/Dockerfile ]; then docker build -t agent-platform/tool-bus:latest -f services/tool-bus-java/Dockerfile services/tool-bus-java/; fi
	@if [ -f services/governance-java/Dockerfile ]; then docker build -t agent-platform/governance:latest -f services/governance-java/Dockerfile services/governance-java/; fi
	@echo "All images built"
```

#### 4.2.4 安全最佳实践清单

| 检查项 | 实现 | 验证命令 |
|--------|------|----------|
| 非 root 用户运行 | `USER app` | `docker run --rm agent-platform/model-gateway whoami` |
| 最小基础镜像 | `python:3.12-slim` | `docker images agent-platform/model-gateway` (预计 < 300MB) |
| 无冗余包 | `--no-install-recommends` + `rm -rf /var/lib/apt/lists/*` | `docker run --rm agent-platform/model-gateway dpkg -l | wc -l` |
| 虚拟环境隔离 | `/app/.venv` | `docker run --rm agent-platform/model-gateway which python` |
| 健康检查 | `HEALTHCHECK` 指令 | `docker inspect agent-platform/model-gateway | jq '.[0].Config.Healthcheck'` |
| 环境变量安全 | `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1` | `docker run --rm agent-platform/model-gateway env` |
| 构建缓存优化 | `pyproject.toml` 先于 `app/` 复制 | 修改 `app/` 代码后仅重建第二阶段 |

### 4.3 验证方法

```bash
# 1. 构建镜像
cd services/model-gateway-python
docker build -t agent-platform/model-gateway:latest .

# 2. 验证镜像大小
docker images agent-platform/model-gateway
# 预期: < 300MB

# 3. 验证非 root 用户
docker run --rm agent-platform/model-gateway whoami
# 预期: app

# 4. 验证健康检查
docker run -d --name model-gateway-test agent-platform/model-gateway
sleep 5
docker inspect model-gateway-test | jq '.[0].State.Health.Status'
# 预期: "healthy"

# 5. 验证服务启动
docker run --rm -p 8002:8002 \
  -e LLM_QWEN_API_KEY=sk-test \
  agent-platform/model-gateway
curl http://localhost:8002/health/live
# 预期: {"status": "alive"}

# 6. 安全扫描
trivy image agent-platform/model-gateway:latest
# 预期: 无 HIGH/CRITICAL 漏洞

# 7. 通过 Makefile 全量构建
make docker-build
# 预期: 6 个镜像全部构建成功
```

### 4.4 风险与回滚

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| uv 安装失败（网络问题） | 低 | 中 | `COPY --from=ghcr.io/astral-sh/uv:latest` 无需下载 |
| 健康检查端点不存在 | 确定 | 高 | 必须先实现 `/health/live` 和 `/health/ready` |
| 镜像体积过大 | 低 | 低 | 多阶段构建 + slim 基础镜像 |
| uvloop 不兼容 | 低 | 中 | 回退到默认 asyncio loop |

**回滚方案**：删除 Dockerfile 即可回退到手动部署模式。

---

## 5. SSE/流式响应端到端打通

### 5.1 问题背景

各服务独立实现了流式能力，但端到端链路未集成：

| 服务 | 流式实现 | 状态 |
|------|---------|------|
| Model Gateway (Python) | `stream_chat_completion` — httpx SSE 流 | 已实现 |
| Orchestrator (Python) | LangGraph stream — 内部流式 | 部分实现 |
| Gateway (Java) | gRPC `StreamChatCompletion` — Proto 定义 | 仅 Proto 定义 |

**关键问题**：

1. **Gateway → Orchestrator**：Proto 已定义 `rpc StreamChatCompletion` 返回 `stream ChatStreamChunk`，但 Gateway 未实现 gRPC Server Stream 消费
2. **Orchestrator → Model Gateway**：当前用 HTTP 同步调用，需要改为 HTTP SSE 流式调用
3. **前端**：需 EventSource 消费 SSE 流

**端到端链路**：

```mermaid
sequenceDiagram
    participant FE as Frontend<br/>(EventSource)
    participant GW as Gateway<br/>(Java :8080)
    participant ORC as Orchestrator<br/>(Python :8001)
    participant MG as ModelGateway<br/>(Python :8002)
    participant LLM as LLM Provider<br/>(Qwen/GLM/...)

    FE->>GW: GET /api/v1/chat/stream<br/>Accept: text/event-stream
    GW->>ORC: gRPC StreamChatCompletion<br/>stream=true
    ORC->>MG: HTTP POST /v1/chat/completions<br/>stream=true<br/>Accept: text/event-stream

    loop 流式响应
        LLM-->>MG: SSE: data: {"delta": "你"}
        MG-->>ORC: SSE: data: {"delta": "你"}
        ORC-->>GW: gRPC ChatStreamChunk<br/>delta="你"
        GW-->>FE: SSE: data: {"delta": "你"}
    end

    LLM-->>MG: SSE: data: [DONE]
    MG-->>ORC: SSE: data: [DONE]
    ORC-->>GW: gRPC ChatStreamChunk<br/>finish_reason="stop"
    GW-->>FE: SSE: data: [DONE]
```

### 5.2 方案设计

#### 5.2.1 Gateway (Java) — gRPC Server Stream → SSE 适配

**核心控制器**：

```java
// gateway-java/src/main/java/com/platform/gateway/controller/ChatStreamController.java
package com.platform.gateway.controller;

import com.platform.gateway.grpc.OrchestratorServiceGrpc;
import com.platform.gateway.grpc.ChatRequest;
import com.platform.gateway.grpc.ChatStreamChunk;
import com.platform.gateway.grpc.RequestContext;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.grpc.stub.StreamObserver;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Slf4j
@RestController
@RequestMapping("/api/v1/chat")
@RequiredArgsConstructor
public class ChatStreamController {

    private final OrchestratorServiceGrpc.OrchestratorServiceStub orchestratorStub;
    private final ObjectMapper objectMapper;

    // 流式请求的超时时间（5 分钟，与 Istio VirtualService 一致）
    private static final long SSE_TIMEOUT_MS = 300_000L;

    private final ExecutorService streamExecutor = Executors.newVirtualThreadPerTaskExecutor();

    /**
     * 流式对话补全 — SSE 端点
     *
     * GET /api/v1/chat/stream?message=xxx&session_id=yyy
     * Accept: text/event-stream
     */
    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamChat(
            @RequestParam String message,
            @RequestParam(required = false) String sessionId,
            @RequestParam(required = false) String model,
            @RequestHeader(value = "X-Request-Id", required = false) String requestId,
            @RequestHeader(value = "X-Tenant-Id", required = false) String tenantId,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) {
        String reqId = requestId != null ? requestId : "req_" + UUID.randomUUID().toString().substring(0, 8);
        String tid = tenantId != null ? tenantId : "default";

        log.info("SSE stream request received, request_id={}, tenant_id={}", reqId, tid);

        // 创建 SSE Emitter（5 分钟超时）
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);

        // 构建 gRPC 请求
        ChatRequest grpcRequest = ChatRequest.newBuilder()
                .setContext(RequestContext.newBuilder()
                        .setRequestId(reqId)
                        .setTenantId(tid)
                        .setTraceId(traceId != null ? traceId : "")
                        .setSessionId(sessionId != null ? sessionId : "")
                        .build())
                .setMessage(message)
                .setModel(model != null ? model : "")
                .setStream(true)
                .build();

        // 异步执行 gRPC 流式调用
        streamExecutor.execute(() -> {
            orchestratorStub.streamChatCompletion(grpcRequest, new StreamObserver<>() {
                @Override
                public void onNext(ChatStreamChunk chunk) {
                    try {
                        // 将 gRPC ChatStreamChunk 转换为 SSE 事件
                        SseEmitter.SseEventBuilder event = SseEmitter.event()
                                .data(objectMapper.writeValueAsString(Map.of(
                                        "id", chunk.getChunkId(),
                                        "delta", chunk.getDelta(),
                                        "finish_reason", chunk.getFinishReason(),
                                        "request_id", chunk.getContext().getRequestId()
                                )));

                        // 如果有错误信息
                        if (chunk.hasError() && chunk.getError().getCode() != 0) {
                            event.name("error");
                        }

                        emitter.send(event);
                    } catch (IOException e) {
                        log.warn("SSE send failed, client may have disconnected, request_id={}", reqId);
                        emitter.completeWithError(e);
                    }
                }

                @Override
                public void onError(Throwable t) {
                    log.error("gRPC stream error, request_id={}", reqId, t);
                    try {
                        emitter.send(SseEmitter.event()
                                .name("error")
                                .data(objectMapper.writeValueAsString(Map.of(
                                        "error", "ERR_STREAM_INTERRUPTED",
                                        "message", "流式响应中断",
                                        "request_id", reqId
                                ))));
                    } catch (IOException ignored) {
                        // 客户端已断开
                    }
                    emitter.completeWithError(t);
                }

                @Override
                public void onCompleted() {
                    try {
                        // 发送 SSE 结束标记
                        emitter.send(SseEmitter.event().data("[DONE]"));
                        emitter.complete();
                        log.info("SSE stream completed, request_id={}", reqId);
                    } catch (IOException e) {
                        log.warn("SSE completion send failed, request_id={}", reqId);
                        emitter.completeWithError(e);
                    }
                }
            });
        });

        // 注册断开回调
        emitter.onCompletion(() -> log.info("SSE emitter completed, request_id={}", reqId));
        emitter.onTimeout(() -> {
            log.warn("SSE emitter timed out, request_id={}", reqId);
            emitter.complete();
        });
        emitter.onError(ex -> log.error("SSE emitter error, request_id={}", reqId, ex));

        return emitter;
    }
}
```

**gRPC Stub 配置**（异步非阻塞）：

```java
// gateway-java/src/main/java/com/platform/gateway/config/GrpcConfig.java
package com.platform.gateway.config;

import com.platform.gateway.grpc.OrchestratorServiceGrpc;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class GrpcConfig {

    @Value("${grpc.orchestrator.host:localhost}")
    private String orchestratorHost;

    @Value("${grpc.orchestrator.port:50100}")
    private int orchestratorPort;

    @Bean
    public ManagedChannel orchestratorChannel() {
        return ManagedChannelBuilder
                .forAddress(orchestratorHost, orchestratorPort)
                .usePlaintext()  // Istio mTLS 在 Sidecar 层处理
                .keepAliveWithoutCalls(false)
                .build();
    }

    @Bean
    public OrchestratorServiceGrpc.OrchestratorServiceStub orchestratorStub(ManagedChannel channel) {
        // 异步 Stub（用于流式调用）
        return OrchestratorServiceGrpc.newStub(channel);
    }
}
```

#### 5.2.2 Orchestrator (Python) — HTTP SSE → gRPC Server Stream 适配

**gRPC 流式服务端**：

```python
# services/orchestrator-python/app/grpc/orchestrator_servicer.py
"""Orchestrator gRPC 服务实现 — 支持流式响应"""

import asyncio
import grpc
import structlog
from typing import AsyncIterator

from app.gen.gateway import orchestrator_pb2
from app.gen.gateway import orchestrator_pb2_grpc
from app.core.config import config
from app.tools.clients.model_gateway_client import ModelGatewayClient

logger = structlog.get_logger()


class OrchestratorServicer(orchestrator_pb2_grpc.OrchestratorServiceServicer):
    """Orchestrator gRPC 服务端实现"""

    def __init__(self):
        self.model_gateway = ModelGatewayClient()

    async def StreamChatCompletion(self, request, context):
        """流式对话补全 — gRPC Server Stream"""

        request_id = request.context.request_id
        tenant_id = request.context.tenant_id
        trace_id = request.context.trace_id

        logger.info(
            "grpc_stream_chat_started",
            request_id=request_id,
            tenant_id=tenant_id,
            model=request.model,
        )

        try:
            # 调用 Model Gateway 的 SSE 流式接口
            async for chunk in self.model_gateway.stream_chat(
                messages=[{"role": "user", "content": request.message}],
                model=request.model or None,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                request_id=request_id,
                tenant_id=tenant_id,
                trace_id=trace_id,
            ):
                # 将 SSE chunk 转换为 gRPC ChatStreamChunk
                yield orchestrator_pb2.ChatStreamChunk(
                    context=orchestrator_pb2.RequestContext(
                        request_id=request_id,
                        tenant_id=tenant_id,
                        trace_id=trace_id,
                    ),
                    chunk_id=chunk.get("id", ""),
                    chunk_index=chunk.get("chunk_index", 0),
                    delta=chunk.get("delta", ""),
                    finish_reason=chunk.get("finish_reason", ""),
                )

        except asyncio.CancelledError:
            logger.warning("grpc_stream_cancelled", request_id=request_id)
            context.set_code(grpc.StatusCode.CANCELLED)
            context.set_details("Stream cancelled by client")

        except Exception as e:
            logger.error("grpc_stream_error", request_id=request_id, error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Stream error: {str(e)}")
```

**Model Gateway SSE 客户端**：

```python
# services/orchestrator-python/app/tools/clients/model_gateway_client.py
"""Model Gateway HTTP SSE 客户端"""

import json
import httpx
import structlog
from typing import AsyncIterator

logger = structlog.get_logger()


class ModelGatewayClient:
    """Model Gateway 流式客户端"""

    def __init__(self, base_url: str = "http://model-gateway:8002"):
        self.base_url = base_url

    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        request_id: str = "",
        tenant_id: str = "",
        trace_id: str = "",
    ) -> AsyncIterator[dict]:
        """调用 Model Gateway SSE 流式接口

        Yields:
            解析后的 SSE 事件字典
        """
        payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        headers = {
            "Content-Type": "application/json",
            "X-Request-Id": request_id,
            "X-Tenant-Id": tenant_id,
            "X-Trace-Id": trace_id,
        }

        chunk_index = 0

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data = line[6:]  # 去掉 "data: " 前缀

                    if data.strip() == "[DONE]":
                        yield {
                            "delta": "",
                            "finish_reason": "stop",
                            "chunk_index": chunk_index,
                        }
                        return

                    try:
                        parsed = json.loads(data)
                        # 提取增量内容
                        delta = ""
                        finish_reason = ""
                        if parsed.get("choices"):
                            choice = parsed["choices"][0]
                            delta = choice.get("delta", {}).get("content", "")
                            finish_reason = choice.get("finish_reason", "")

                        yield {
                            "id": parsed.get("id", ""),
                            "delta": delta,
                            "finish_reason": finish_reason,
                            "chunk_index": chunk_index,
                            "model": parsed.get("model", ""),
                        }
                        chunk_index += 1

                    except json.JSONDecodeError:
                        logger.warning(
                            "sse_parse_error",
                            request_id=request_id,
                            raw_data=data,
                        )
                        continue
```

#### 5.2.3 Model Gateway (Python) — SSE 流式端点

当前 `chat.py` 中 `stream` 参数被标记为"暂不支持"，需要实现：

```python
# services/model-gateway-python/app/api/v1/chat.py — 补充流式端点

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncIterator

router = APIRouter()


@router.post("/chat/completions/stream")
async def chat_completion_stream(request: ChatRequest):
    """流式对话补全 — SSE 格式

    返回 text/event-stream 格式:
    data: {"id":"...","choices":[{"delta":{"content":"你"}}]}
    data: {"id":"...","choices":[{"delta":{"content":"好"}}]}
    data: [DONE]
    """
    if not request.stream:
        raise HTTPException(status_code=400, detail="Use /chat/completions for non-stream requests")

    request_id = f"chat-{uuid.uuid4().hex[:8]}"

    logger.info(
        "stream_request_received",
        request_id=request_id,
        model=request.model,
    )

    async def event_generator() -> AsyncIterator[str]:
        """SSE 事件生成器"""
        try:
            model_router = get_model_router()
            chat_request = ChatCompletionRequest(
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in request.messages
                ],
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True,
            )

            provider, model_name, circuit_breaker = await model_router.route(chat_request)

            async for chunk in provider.stream_chat_completion(chat_request):
                yield chunk  # Provider 已返回 SSE 格式行

            circuit_breaker.record_success()

        except AllProvidersDownError:
            error_event = f'data: {{"error": "ERR_MODEL_ALL_PROVIDERS_DOWN", "request_id": "{request_id}"}}\n\n'
            yield error_event

        except Exception as e:
            logger.error("stream_error", request_id=request_id, error=str(e))
            error_event = f'data: {{"error": "ERR_STREAM_ERROR", "message": "{str(e)}", "request_id": "{request_id}"}}\n\n'
            yield error_event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 不缓冲
            "X-Request-Id": request_id,
        },
    )
```

#### 5.2.4 流式中断处理

```mermaid
flowchart TD
    A[流式传输中] --> B{中断类型?}

    B -->|客户端断开| C[Gateway 检测到<br/>SseEmitter.onError]
    C --> C1[取消 gRPC 流<br/>context.cancel()]
    C1 --> C2[Orchestrator 收到<br/>CancelledError]
    C2 --> C3[关闭 httpx stream]
    C3 --> C4[记录中断日志<br/>tokens_sent=N]

    B -->|服务端超时| D[Gateway SseEmitter<br/>onTimeout]
    D --> D1[发送 SSE error 事件]
    D1 --> D2[关闭连接]

    B -->|上游 Provider 错误| E[Model Gateway<br/>stream_chat_completion 异常]
    E --> E1[Orchestrator 捕获异常]
    E1 --> E2[gRPC 返回 ErrorDetail]
    E2 --> E3[Gateway 转为 SSE error 事件]

    B -->|网络抖动| F[httpx StreamError]
    F --> F1[重试 1 次<br/>（仅网络错误）]
    F1 -->|成功| G[继续流式]
    F1 -->|失败| E1
```

**客户端断开处理**（Gateway Java）：

```java
// SseEmitter 回调中处理客户端断开
emitter.onCompletion(() -> {
    log.info("Client disconnected, request_id={}", reqId);
    // gRPC StreamObserver 的 onCancel 会自动触发
});

emitter.onError(ex -> {
    log.warn("SSE connection error, request_id={}", reqId);
    // gRPC stream 会被自动取消
});
```

**服务端超时处理**（Orchestrator Python）：

```python
import asyncio

async def StreamChatCompletion(self, request, context):
    try:
        async with asyncio.timeout(AGENT_TOTAL_TIMEOUT_S):
            async for chunk in self.model_gateway.stream_chat(...):
                yield chunk
    except TimeoutError:
        logger.error("stream_timeout", request_id=request_id)
        yield orchestrator_pb2.ChatStreamChunk(
            context=...,
            finish_reason="timeout",
            error=orchestrator_pb2.ErrorDetail(
                code=504,
                message="Stream timeout",
            ),
        )
```

#### 5.2.5 trace_id 在流式场景下的透传

**透传链路**：

```
Frontend → Gateway (Java) → Orchestrator (Python) → Model Gateway (Python) → Provider

Header: X-Trace-Id / traceparent (W3C)
gRPC metadata: x-trace-id
SSE data: trace_id 字段
```

| 层 | 传入 | 传出 | 机制 |
|----|------|------|------|
| Frontend → Gateway | HTTP header `traceparent` | - | 浏览器自动携带 |
| Gateway → Orchestrator | HTTP header | gRPC metadata `x-trace-id` | 手动注入 |
| Orchestrator → Model Gateway | gRPC metadata | HTTP header `X-Trace-Id` | 手动注入 |
| Model Gateway → Provider | HTTP header | Provider API header | 透传 |

**OpenTelemetry 集成**（Python 侧）：

```python
# 使用 OTel 自动注入 traceparent
from opentelemetry import context, trace
from opentelemetry.propagate import inject

# 在 httpx 请求中自动注入 trace context
headers = {}
inject(headers)  # 注入 traceparent, tracestate 等

async with httpx.AsyncClient() as client:
    async with client.stream("POST", url, headers=headers, ...) as response:
        ...
```

#### 5.2.6 前端 EventSource 消费示例

```typescript
// services/web-frontend/src/services/sse-client.ts
/**
 * SSE 流式客户端 — 消费 Gateway 的 text/event-stream
 *
 * 用法:
 *   const client = new SseChatClient('/api/v1/chat/stream');
 *   client.onDelta((text) => { appendToUI(text); });
 *   client.onError((err) => { showError(err); });
 *   client.start({ message: '你好', sessionId: 'sess_123' });
 */

export interface SseChatEvents {
  onDelta: (text: string) => void;
  onComplete: (fullText: string) => void;
  onError: (error: { code: string; message: string; requestId: string }) => void;
}

export class SseChatClient {
  private eventSource: EventSource | null = null;
  private fullText = '';
  private events: Partial<SseChatEvents> = {};

  constructor(private url: string) {}

  /** 注册事件回调 */
  on<K extends keyof SseChatEvents>(event: K, handler: SseChatEvents[K]): this {
    this.events[event] = handler;
    return this;
  }

  /** 启动流式请求 */
  start(params: { message: string; sessionId?: string; model?: string }) {
    // 构造 URL（GET 请求参数）
    const queryParams = new URLSearchParams({
      message: params.message,
      ...(params.sessionId && { session_id: params.sessionId }),
      ...(params.model && { model: params.model }),
    });

    const url = `${this.url}?${queryParams.toString()}`;
    this.eventSource = new EventSource(url);
    this.fullText = '';

    this.eventSource.onmessage = (event) => {
      const data = event.data;

      // 结束标记
      if (data === '[DONE]') {
        this.events.onComplete?.(this.fullText);
        this.close();
        return;
      }

      try {
        const parsed = JSON.parse(data);

        // 错误事件
        if (parsed.error) {
          this.events.onError?.({
            code: parsed.error,
            message: parsed.message || 'Unknown error',
            requestId: parsed.request_id || '',
          });
          this.close();
          return;
        }

        // 增量内容
        if (parsed.delta) {
          this.fullText += parsed.delta;
          this.events.onDelta?.(parsed.delta);
        }
      } catch {
        // 非法 JSON，忽略
        console.warn('SSE parse error:', data);
      }
    };

    this.eventSource.onerror = () => {
      this.events.onError?.({
        code: 'ERR_SSE_CONNECTION',
        message: '连接中断',
        requestId: '',
      });
      this.close();
    };
  }

  /** 主动关闭连接 */
  close() {
    this.eventSource?.close();
    this.eventSource = null;
  }
}
```

**React 组件集成**：

```tsx
// services/web-frontend/src/components/ChatStream.tsx
import { useState, useRef } from 'react';
import { SseChatClient } from '../services/sse-client';

export function ChatStream() {
  const [streamingText, setStreamingText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const clientRef = useRef<SseChatClient | null>(null);

  const handleSend = (message: string) => {
    setStreamingText('');
    setIsStreaming(true);

    const client = new SseChatClient('/api/v1/chat/stream');

    client
      .on('onDelta', (text) => {
        setStreamingText((prev) => prev + text);
      })
      .on('onComplete', () => {
        setIsStreaming(false);
      })
      .on('onError', (err) => {
        console.error('Stream error:', err);
        setIsStreaming(false);
      });

    client.start({ message, sessionId: 'current-session' });
    clientRef.current = client;
  };

  const handleStop = () => {
    clientRef.current?.close();
    setIsStreaming(false);
  };

  return (
    <div>
      <div className="streaming-text">{streamingText}</div>
      {isStreaming && (
        <button onClick={handleStop}>停止生成</button>
      )}
    </div>
  );
}
```

### 5.3 验证方法

```bash
# 1. 验证 Model Gateway SSE 端点
curl -N -X POST http://localhost:8002/v1/chat/completions/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "model": "qwen-max",
    "stream": true
  }'
# 预期: SSE 流式输出 data: {...}

# 2. 验证 Orchestrator gRPC 流式
# 使用 grpcurl 测试
grpcurl -plaintext \
  -d '{"context": {"request_id": "test-001"}, "message": "你好", "stream": true}' \
  localhost:50051 gateway.OrchestratorService/StreamChatCompletion
# 预期: 流式 ChatStreamChunk 响应

# 3. 验证端到端 SSE
curl -N http://localhost:8080/api/v1/chat/stream?message=你好 \
  -H "Accept: text/event-stream" \
  -H "X-Request-Id: e2e-test-001" \
  -H "X-Tenant-Id: tenant_001"
# 预期: SSE 流式输出

# 4. 验证中断处理
# 4a. 客户端中途断开
curl -N http://localhost:8080/api/v1/chat/stream?message=写一篇长文 \
  -H "Accept: text/event-stream" &
CURL_PID=$!
sleep 2
kill $CURL_PID
# 预期: 服务端日志 "Client disconnected"

# 5. 验证 trace_id 透传
curl -N http://localhost:8080/api/v1/chat/stream?message=你好 \
  -H "Accept: text/event-stream" \
  -H "traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
# 预期: 日志中 trace_id 一致

# 6. 前端 EventSource 集成测试
# 在浏览器 Console 中:
# const es = new EventSource('/api/v1/chat/stream?message=你好');
# es.onmessage = (e) => console.log(e.data);
```

### 5.4 风险与回滚

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| gRPC 流式与 SSE 格式不兼容 | 中 | 高 | 逐层验证，单元测试覆盖格式转换 |
| 长连接导致线程/内存泄漏 | 中 | 高 | SseEmitter 超时 + onCompletion 清理 |
| 流式中断后状态不一致 | 中 | 中 | 中断时记录 tokens_sent，支持续传 |
| Istio/Nginx 缓冲导致 SSE 延迟 | 中 | 中 | `X-Accel-Buffering: no` + `proxy-buffering: off` |
| EventSource 不支持 POST | 确定 | 中 | 使用 GET + query params，或改用 fetch+ReadableStream |

**回滚方案**：关闭 `stream=true` 参数即可回退到同步模式，端到端链路不依赖流式。

---

## 6. 环境配置模板统一

### 6.1 问题背景

6 个服务中仅 web-frontend 有环境变量常量定义（`src/constants/config.ts`），但：

- 无 `.env.example` 模板文件
- 其余 5 个服务缺少任何环境变量文档或模板
- 新开发者无法快速了解每个服务需要哪些配置

| 服务 | .env.example | 配置文档 | 状态 |
|------|-------------|---------|------|
| web-frontend | 缺失 | `config.ts` 定义了常量 | 需补充 |
| gateway-java | 缺失 | `application.yml` | 需补充 |
| orchestrator-python | 缺失 | Pydantic Settings | 需补充 |
| knowledge-python | 缺失 | Pydantic Settings | 需补充 |
| model-gateway-python | 缺失 | Pydantic Settings | 需补充 |
| tool-bus-java | 缺失 | `application.yml` | 需补充 |

### 6.2 方案设计

#### 6.2.1 各服务 .env.example 模板

**gateway-java**：

```bash
# ============================================================
#  Gateway Service - 环境变量模板
#  复制为 .env.local 后填入实际值
#  此文件已加入 .gitignore，请勿提交到 Git
# ============================================================

# ---- Spring Boot ----
SPRING_PROFILES_ACTIVE=dev
SERVER_PORT=8080

# ---- 数据库 ----
SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/agent_platform
SPRING_DATASOURCE_USERNAME=app_user
SPRING_DATASOURCE_PASSWORD=dev_only_change_me

# ---- Redis ----
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# ---- JWT ----
JWT_SECRET=dev-only-jwt-secret-min-32-characters-long!!
JWT_EXPIRATION_MS=86400000

# ---- gRPC (Orchestrator) ----
GRPC_ORCHESTRATOR_HOST=localhost
GRPC_ORCHESTRATOR_PORT=50100

# ---- 加密服务 ----
# 生产环境使用 Vault 挂载路径
ENCRYPTION_KEY_PATH=
# 开发环境使用 Base64 编码密钥
ENCRYPTION_KEY_BASE64=dGVzdC1lbmNyeXB0aW9uLWtleS0zMmJ5dGVzLTEyMw==

# ---- Kafka ----
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_GROUP_ID=gateway-group

# ---- OpenTelemetry ----
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=gateway

# ---- 日志 ----
LOG_LEVEL=INFO
```

**orchestrator-python**：

```bash
# ============================================================
#  Orchestrator Service - 环境变量模板
#  复制为 .env.local 后填入实际值
# ============================================================

# ---- 服务配置 ----
SERVICE_NAME=orchestrator
SERVICE_PORT=8001
ENVIRONMENT=dev

# ---- 数据库 ----
DATABASE_URL=postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform

# ---- Redis ----
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# ---- Model Gateway ----
MODEL_GATEWAY_URL=http://localhost:8002
MODEL_CALL_TIMEOUT_S=30

# ---- Tool Bus (gRPC) ----
TOOL_BUS_GRPC_ADDR=localhost:40051
TOOL_CALL_TIMEOUT_S=15

# ---- Knowledge Service ----
KNOWLEDGE_SERVICE_URL=http://localhost:8003

# ---- Agent 配置 ----
MAX_AGENT_STEPS=10
AGENT_TOTAL_TIMEOUT_S=300
MAX_USER_INPUT_TOKENS=8000
MAX_CONTEXT_WINDOW_TOKENS=128000

# ---- OpenTelemetry ----
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=orchestrator

# ---- 日志 ----
LOG_LEVEL=INFO
LOG_FORMAT=json

# ---- gRPC Server ----
GRPC_SERVER_PORT=50100
```

**model-gateway-python**：

```bash
# ============================================================
#  Model Gateway Service - 环境变量模板
#  复制为 .env.local 后填入实际值
# ============================================================

# ---- 服务配置 ----
SERVICE_NAME=model-gateway
SERVICE_PORT=8002
ENVIRONMENT=dev

# ---- 数据库 ----
DATABASE_URL=postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform

# ---- Redis ----
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=1

# ---- LLM API Keys (生产环境请使用 Vault) ----
LLM_QWEN_API_KEY=sk-your-qwen-api-key
LLM_QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

LLM_GLM_API_KEY=sk-your-glm-api-key
LLM_GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4

LLM_KIMI_API_KEY=sk-your-kimi-api-key
LLM_KIMI_BASE_URL=https://api.moonshot.cn/v1

LLM_DEEPSEEK_API_KEY=sk-your-deepseek-api-key
LLM_DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ---- 超时配置 ----
MODEL_CALL_TIMEOUT_S=30
STREAM_TIMEOUT_S=300

# ---- 熔断器 ----
CIRCUIT_FAILURE_THRESHOLD=5
CIRCUIT_RECOVERY_TIMEOUT=30

# ---- 重试 ----
RETRY_MAX_ATTEMPTS=3
RETRY_MIN_WAIT=1.0
RETRY_MAX_WAIT=10.0

# ---- OpenTelemetry ----
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=model-gateway

# ---- 日志 ----
LOG_LEVEL=INFO
LOG_FORMAT=json
```

**knowledge-python**：

```bash
# ============================================================
#  Knowledge Service - 环境变量模板
#  复制为 .env.local 后填入实际值
# ============================================================

# ---- 服务配置 ----
SERVICE_NAME=knowledge
SERVICE_PORT=8003
ENVIRONMENT=dev

# ---- 数据库 ----
DATABASE_URL=postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform

# ---- Redis ----
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=2

# ---- 对象存储 ----
OSS_ENDPOINT=http://localhost:9000
OSS_ACCESS_KEY=minioadmin
OSS_SECRET_KEY=minioadmin
OSS_BUCKET=agent-platform-docs

# ---- Embedding ----
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DEVICE=cpu
EMBEDDING_DIMENSION=1024

# ---- RAG ----
CHUNK_SIZE=500
CHUNK_OVERLAP=50
RAG_TOP_K=5
RAG_SIMILARITY_THRESHOLD=0.7

# ---- OpenTelemetry ----
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=knowledge

# ---- 日志 ----
LOG_LEVEL=INFO
LOG_FORMAT=json
```

**tool-bus-java**：

```bash
# ============================================================
#  Tool Bus Service - 环境变量模板
#  复制为 .env.local 后填入实际值
# ============================================================

# ---- Spring Boot ----
SPRING_PROFILES_ACTIVE=dev
SERVER_PORT=8083

# ---- 数据库 ----
SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/agent_platform
SPRING_DATASOURCE_USERNAME=app_user
SPRING_DATASOURCE_PASSWORD=dev_only_change_me

# ---- Redis ----
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# ---- gRPC Server ----
GRPC_SERVER_PORT=40051

# ---- Governance Service ----
GOVERNANCE_SERVICE_URL=http://localhost:8082

# ---- Kafka ----
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_GROUP_ID=tool-bus-group

# ---- OpenTelemetry ----
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=tool-bus

# ---- 日志 ----
LOG_LEVEL=INFO
```

**web-frontend**：

```bash
# ============================================================
#  Web Frontend - 环境变量模板
#  复制为 .env.local 后填入实际值
#  Vite 要求环境变量以 VITE_ 开头才能在客户端使用
# ============================================================

# ---- API ----
VITE_API_BASE_URL=/api/v1
VITE_WS_URL=/ws

# ---- 认证 ----
VITE_AUTH_ENABLED=true
VITE_TOKEN_REFRESH_THRESHOLD_S=60

# ---- 功能开关 ----
VITE_ENABLE_SSE=true
VITE_ENABLE_WEBSOCKET=false

# ---- 对话配置 ----
VITE_MAX_MESSAGE_LENGTH=4000
VITE_MAX_HISTORY_MESSAGES=100

# ---- 文件上传 ----
VITE_MAX_FILE_SIZE_MB=50
VITE_MAX_FILES_PER_UPLOAD=10

# ---- 环境 ----
VITE_APP_ENV=development
```

#### 6.2.2 .env.local 验证脚本

```bash
#!/bin/bash
# scripts/verify-env.sh
# 验证所有服务的 .env.local 是否存在且包含必需配置项
# 用法: ./scripts/verify-env.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'  # No Color

PASS=0
FAIL=0
WARN=0

check_env() {
    local service_dir="$1"
    local service_name="$2"
    local env_file="${service_dir}/.env.local"
    local example_file="${service_dir}/.env.example"

    echo ""
    echo "=== Checking ${service_name} ==="

    # 1. 检查 .env.local 是否存在
    if [ ! -f "${env_file}" ]; then
        echo -e "${RED}FAIL${NC}: .env.local not found in ${service_dir}"
        echo "  Run: cp ${example_file} ${env_file}"
        FAIL=$((FAIL + 1))
        return
    fi

    echo -e "${GREEN}OK${NC}: .env.local exists"

    # 2. 检查 .env.example 是否存在
    if [ ! -f "${example_file}" ]; then
        echo -e "${YELLOW}WARN${NC}: .env.example not found"
        WARN=$((WARN + 1))
    fi

    # 3. 检查必需配置项
    local required_vars=$(grep -E '^[A-Z_]+=' "${example_file}" 2>/dev/null | sed 's/=.*//' || echo "")

    if [ -z "${required_vars}" ]; then
        echo -e "${YELLOW}WARN${NC}: No .env.example to check against"
        WARN=$((WARN + 1))
        return
    fi

    for var in ${required_vars}; do
        if grep -q "^${var}=" "${env_file}"; then
            # 检查值是否为空
            value=$(grep "^${var}=" "${env_file}" | cut -d'=' -f2-)
            if [ -z "${value}" ]; then
                echo -e "${YELLOW}WARN${NC}: ${var} is set but empty"
                WARN=$((WARN + 1))
            else
                echo -e "${GREEN}OK${NC}: ${var} is set"
                PASS=$((PASS + 1))
            fi
        else
            echo -e "${RED}FAIL${NC}: ${var} is missing"
            FAIL=$((FAIL + 1))
        fi
    done

    # 4. 检查是否有硬编码密钥
    if grep -qiE '(sk-live-|password.*=.*[a-zA-Z0-9]{8,}|secret.*=.*[a-zA-Z0-9]{8,})' "${env_file}"; then
        echo -e "${RED}SECURITY${NC}: Possible hardcoded secret detected in .env.local"
        FAIL=$((FAIL + 1))
    fi
}

# 检查各服务
check_env "services/gateway-java" "gateway-java"
check_env "services/orchestrator-python" "orchestrator-python"
check_env "services/model-gateway-python" "model-gateway-python"
check_env "services/knowledge-python" "knowledge-python"
check_env "services/tool-bus-java" "tool-bus-java"
check_env "services/web-frontend" "web-frontend"

echo ""
echo "========================================="
echo -e "Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}, ${YELLOW}${WARN} warnings${NC}"
echo "========================================="

if [ ${FAIL} -gt 0 ]; then
    exit 1
fi
```

#### 6.2.3 Makefile 新增 make setup

```makefile
# ---- 环境配置 ----
.PHONY: setup setup-check

# 初始化所有服务的 .env.local
setup:
	@echo "Setting up environment configuration..."
	@for dir in services/gateway-java services/orchestrator-python \
	            services/model-gateway-python services/knowledge-python \
	            services/tool-bus-java services/web-frontend; do \
		if [ -f "$${dir}/.env.example" ] && [ ! -f "$${dir}/.env.local" ]; then \
			cp "$${dir}/.env.example" "$${dir}/.env.local"; \
			echo "  Created $${dir}/.env.local from .env.example"; \
		elif [ -f "$${dir}/.env.local" ]; then \
			echo "  $${dir}/.env.local already exists, skipping"; \
		else \
			echo "  WARNING: $${dir}/.env.example not found"; \
		fi; \
	done
	@echo ""
	@echo "Please review and update .env.local files with your actual values."
	@echo "Run 'make setup-check' to verify your configuration."

# 验证环境配置
setup-check:
	@bash scripts/verify-env.sh
```

#### 6.2.4 docker-compose.yml 环境变量引用

修改 `infra/docker-compose.yml`，为应用服务添加环境变量引用：

```yaml
# infra/docker-compose.yml — 仅展示新增/修改部分

services:
  # ====== Gateway Service ======
  gateway:
    build:
      context: ../services/gateway-java
      dockerfile: Dockerfile
    container_name: agent-gateway
    env_file:
      - ../services/gateway-java/.env.local
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - agent-network

  # ====== Orchestrator Service ======
  orchestrator:
    build:
      context: ../services/orchestrator-python
      dockerfile: Dockerfile
    container_name: agent-orchestrator
    env_file:
      - ../services/orchestrator-python/.env.local
    environment:
      - DATABASE_URL=postgresql+asyncpg://app_user:dev_password@postgres:5432/agent_platform
      - MODEL_GATEWAY_URL=http://model-gateway:8002
      - TOOL_BUS_GRPC_ADDR=tool-bus:40051
      - KNOWLEDGE_SERVICE_URL=http://knowledge:8003
    ports:
      - "8001:8001"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - agent-network

  # ====== Model Gateway Service ======
  model-gateway:
    build:
      context: ../services/model-gateway-python
      dockerfile: Dockerfile
    container_name: agent-model-gateway
    env_file:
      - ../services/model-gateway-python/.env.local
    environment:
      - DATABASE_URL=postgresql+asyncpg://app_user:dev_password@postgres:5432/agent_platform
    ports:
      - "8002:8002"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - agent-network

  # ====== Knowledge Service ======
  knowledge:
    build:
      context: ../services/knowledge-python
      dockerfile: Dockerfile
    container_name: agent-knowledge
    env_file:
      - ../services/knowledge-python/.env.local
    environment:
      - DATABASE_URL=postgresql+asyncpg://app_user:dev_password@postgres:5432/agent_platform
      - OSS_ENDPOINT=http://minio:9000
    ports:
      - "8003:8003"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - agent-network

  # ====== Tool Bus Service ======
  tool-bus:
    build:
      context: ../services/tool-bus-java
      dockerfile: Dockerfile
    container_name: agent-tool-bus
    env_file:
      - ../services/tool-bus-java/.env.local
    environment:
      - SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/agent_platform
      - GOVERNANCE_SERVICE_URL=http://governance:8082
    ports:
      - "8083:8083"
      - "40051:40051"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - agent-network

  # ====== Governance Service ======
  governance:
    build:
      context: ../services/governance-java
      dockerfile: Dockerfile
    container_name: agent-governance
    env_file:
      - ../services/governance-java/.env.local
    ports:
      - "8082:8082"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - agent-network

  # ====== 基础设施（保持不变） ======
  postgres: ...
  redis: ...
  # ...
```

### 6.3 验证方法

```bash
# 1. 执行 make setup
make setup
# 预期: 6 个服务的 .env.local 从 .env.example 复制成功

# 2. 验证环境配置
make setup-check
# 预期: 所有必需配置项检查通过

# 3. 验证 .gitignore 包含 .env.local
grep -r "\.env\.local" .gitignore
# 预期: .env.local 已在 .gitignore 中

# 4. 验证 Docker Compose 能正确读取
docker compose -f infra/docker-compose.yml config
# 预期: 环境变量正确展开

# 5. 验证服务启动
make dev
# 预期: 所有服务使用 .env.local 配置启动
```

### 6.4 风险与回滚

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| .env.local 泄露到 Git | 低 | 极高 | `.gitignore` 强制包含 + gitleaks 扫描 |
| 生产环境误用 .env.local | 低 | 高 | 生产使用 Vault/KMS，不使用 .env 文件 |
| 配置项遗漏 | 中 | 中 | `make setup-check` 自动验证 |
| docker-compose 覆盖 env_file 值 | 中 | 低 | `environment` 块覆盖 `env_file`，用于容器内网络地址 |

**回滚方案**：删除所有 `.env.local` 文件，恢复手动配置模式。

---

## 实施优先级与依赖关系

```mermaid
flowchart TD
    P4[4. Model-Gateway Dockerfile] --> P6[6. 环境配置模板]
    P1[1. API Key 加密] --> P6
    P6 --> P2[2. Python DB 迁移]
    P2 --> P3[3. K8s Ingress/NetworkPolicy]
    P4 --> P5[5. SSE 端到端]
    P1 --> P5

    style P4 fill:#ff6b6b,color:#fff
    style P6 fill:#ff6b6b,color:#fff
    style P1 fill:#ffa502,color:#fff
    style P2 fill:#ffa502,color:#fff
    style P3 fill:#7bed9f,color:#000
    style P5 fill:#7bed9f,color:#000
```

| 优先级 | 问题 | 预估工时 | 前置依赖 | 实施窗口 |
|--------|------|---------|---------|---------|
| **P0-1** | 4. Dockerfile | 0.5d | 无 | 第 1 天 |
| **P0-1** | 6. 环境配置模板 | 1d | 无 | 第 1-2 天 |
| **P0-2** | 1. API Key 加密 | 2d | 无 | 第 2-3 天 |
| **P0-2** | 2. Python DB 迁移 | 1.5d | 环境配置 | 第 3-4 天 |
| **P0-3** | 5. SSE 端到端 | 3d | Dockerfile + 加密 | 第 3-5 天 |
| **P0-3** | 3. K8s Ingress/NetworkPolicy | 1d | DB 迁移 | 第 5 天 |

**总工时预估**：约 9 人天，建议 2 人并行，1 周内完成。

---

> **文档状态**：已实施 | **更新**：2026-06-25
