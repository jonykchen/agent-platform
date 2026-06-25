"""
Knowledge Service 配置管理

【核心概念】
基于 Pydantic Settings 实现类型安全的配置管理，支持环境变量覆盖和配置校验。
所有配置项通过 AppConfig 类集中管理，避免分散在代码中硬编码。

【配置加载优先级】
环境变量 > .env 文件 > 默认值

【技术选型对比】

| 特性 | Pydantic Settings | Dynaconf | python-dotenv |
|------|-------------------|----------|---------------|
| 类型安全 | ✅ 自动类型转换 | ✅ | ❌ |
| 校验 | ✅ Pydantic 校验 | ✅ | ❌ |
| 环境变量 | ✅ 自动读取 | ✅ | ✅ |
| IDE 支持 | ✅ 自动补全 | ❌ | ❌ |
| 学习成本 | 低 | 中 | 低 |

【配置分类】

1. 基础配置
   - environment: 运行环境（local/staging/production）
   - debug: 调试模式开关
   - port: 服务端口

2. 数据存储配置
   - database_url: PostgreSQL 连接（支持 asyncpg 驱动）
   - redis_url: Redis 连接（用于缓存）

3. Embedding 配置
   - embedding_service_url: Embedding 服务地址（指向 Model Gateway）
   - embedding_model: 模型名称（如 text-embedding-ada-002）
   - embedding_dimension: 向量维度（需与模型匹配）
   - embedding_batch_size: 批量嵌入大小

4. 文档处理配置
   - chunk_size: 分块大小（字符数）
   - chunk_overlap: 分块重叠（保持上下文连贯性）
   - max_file_size_mb: 文件大小限制

5. 检索配置
   - default_top_k: 默认返回数量
   - max_top_k: 最大返回数量（防止资源耗尽）
   - rerank_top_k: 重排序候选数量

【RAG Pipeline 配置要点】

索引阶段：
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  文档上传   │ ──▶ │  分块处理   │ ──▶ │  向量化存储 │
│ (max_file)  │     │(chunk_size) │     │(batch_size) │
└─────────────┘     └─────────────┘     └─────────────┘

检索阶段：
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  查询处理   │ ──▶ │  向量检索   │ ──▶ │  结果重排   │
│ (embedding) │     │ (top_k)     │     │ (rerank)    │
└─────────────┘     └─────────────┘     └─────────────┘

【安全注意事项】
- database_url 包含密码，标记为 [SECRET]
- 生产环境必须通过环境变量注入，禁止硬编码
- 敏感配置项禁止写入日志

【使用示例】
    from app.core.config import config

    # 获取配置值
    db_url = config.database_url
    chunk_size = config.chunk_size

    # 环境变量覆盖
    # export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db"
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """
    知识库服务配置类

    【设计模式】
    使用 Pydantic BaseSettings 实现配置绑定：
    - 自动从环境变量读取（命名转换：database_url → DATABASE_URL）
    - 支持类型转换和校验
    - 支持默认值

    【配置项说明】
    详见各字段的 docstring 和注释。
    """

    # ==================== 基础配置 ====================

    environment: str = "local"
    """运行环境：local / staging / production"""

    debug: bool = False
    """调试模式：开启后输出详细日志，生产环境必须关闭"""

    port: int = 8003
    """HTTP 服务端口，知识库服务默认 8003"""

    # ==================== 数据库配置 ====================

    database_url: str = Field(
        default="postgresql+asyncpg://app_user:CHANGE_ME@localhost:5432/agent_platform",
        description="[SECRET] PostgreSQL 连接 URL（通过 DATABASE_URL 环境变量覆盖）",
    )

    database_pool_size: int = 10
    """数据库连接池大小，根据并发量调整"""

    # ==================== Redis 配置 ====================

    redis_url: str = "redis://:CHANGE_ME@localhost:6379/2"
    """Redis 连接 URL（通过 REDIS_URL 环境变量覆盖）"""

    # ==================== Embedding 配置 ====================

    embedding_service_url: str = "http://localhost:8002"
    """Embedding 服务地址，指向 Model Gateway 统一管理"""

    embedding_model: str = "text-embedding-v3"
    """
    Embedding 模型名称

    平台统一使用通义千问 text-embedding-v3（国内 LLM，1024 维），
    与 Model Gateway / Orchestrator 长时记忆保持一致。

    可选模型：
    - text-embedding-v3: 通义千问，1024 维（平台默认）
    - bge-large-zh: 国产，1024 维，中文效果好

    注意：更换模型需同步更新 embedding_dimension 与数据库 vector(dim)
    """

    embedding_dimension: int = 1024
    """
    向量维度，必须与 embedding_model 及数据库 knowledge_chunk.embedding 维度一致

    常见模型维度：
    - text-embedding-v3: 1024（平台默认）
    - bge-large-zh / glm-embedding: 1024
    - ada-002: 1536
    """

    embedding_batch_size: int = 100
    """批量 Embedding 请求数量，平衡吞吐与延迟"""

    # ==================== 模型网关配置 ====================

    model_gateway_url: str = "http://localhost:8002"
    """模型网关地址，用于 Query 改写等 LLM 能力"""

    default_model: str = "qwen-plus"
    """默认 LLM 模型，用于 Query 改写、摘要生成等"""

    # ==================== 文档处理配置 ====================

    chunk_size: int = 500
    """
    分块大小（字符数）

    选型依据：
    - 太小：语义被切断，检索效果差
    - 太大：检索精度下降，Token 消耗增加
    - 推荐：300-800 字符，根据文档类型调整

    学术论文：800-1000
    技术文档：500-800
    FAQ/问答：300-500
    """

    chunk_overlap: int = 50
    """
    分块重叠大小（字符数）

    作用：保持跨块上下文连贯性
    推荐：chunk_size 的 10-15%

    示例：
    chunk_size=500, overlap=50
    [0-500] -> [450-950] -> [900-1400]
    """

    max_file_size_mb: int = 50
    """
    最大文件大小（MB）

    限制原因：
    - 防止内存溢出
    - 控制处理时间
    - 可根据服务器配置调整
    """

    # ==================== 检索配置 ====================

    default_top_k: int = 10
    """默认返回结果数量，平衡召回率和响应时间"""

    max_top_k: int = 100
    """
    最大返回结果数量

    限制原因：
    - 防止资源耗尽
    - 控制响应时间
    - LLM 上下文窗口有限，过多结果反而降低质量
    """

    rerank_top_k: int = 20
    """
    重排序前的候选数量

    流程：
    1. 向量检索取 rerank_top_k 个候选
    2. 可选：关键词检索补充
    3. 重排序模型精排
    4. 返回 top_k 个最终结果
    """

    enable_rerank: bool = True
    """是否在混合检索后自动执行 Cross-Encoder 重排序（默认开启，提升召回精度）"""

    enable_query_rewrite: bool = False
    """是否在检索前对查询做 LLM 改写/扩展（默认关闭，开启会增加一次 LLM 调用延迟）"""

    # ==================== 存储配置 ====================

    storage_type: str = "local"
    """
    存储类型：local / s3 / oss

    - local: 本地文件系统（开发环境）
    - s3: AWS S3（海外生产环境）
    - oss: 阿里云 OSS（国内生产环境）
    """

    storage_path: str = "./uploads"
    """本地存储路径（storage_type=local 时使用）"""

    @lru_cache
    def get_config(self) -> AppConfig:
        """
        获取配置单例

        【实现说明】
        使用 lru_cache 装饰器实现单例模式，避免重复解析配置。

        Returns:
            AppConfig: 配置实例
        """
        return self


# 全局配置实例
config = AppConfig()
