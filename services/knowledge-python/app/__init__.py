"""
Knowledge Service - RAG 知识库服务

【核心概念】
本服务实现企业级 RAG (Retrieval-Augmented Generation) 知识库，为 Agent 提供外部知识检索能力。
RAG 通过检索相关文档片段并注入 LLM 上下文，有效解决 LLM 的知识截止和幻觉问题。

【架构定位】
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator (Python)                    │
│                    ┌─────────────────────┐                  │
│                    │   Knowledge Tool    │                  │
│                    └──────────┬──────────┘                  │
└───────────────────────┬───────┴─────────────────────────────┘
                        │ gRPC/HTTP
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Knowledge Service (本服务)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Document API │  │ Search API   │  │ Indexer      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Processors   │  │ Retrievers   │  │ Embedding    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└───────────────────────┬─────────────────────────────────────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │PostgreSQL│  │  Redis   │  │ Storage  │
    │(pgvector)│  │ (Cache)  │  │ (S3/OSS) │
    └──────────┘  └──────────┘  └──────────┘

【RAG Pipeline 流程】
1. 索引阶段（离线）：
   文档上传 → 格式解析 → 文本提取 → 分块 (Chunking)
   → Embedding 向量化 → 存储到 pgvector

2. 检索阶段（在线）：
   用户查询 → Query Embedding → 向量检索/混合检索
   → 重排序 (Rerank) → Top-K 结果返回

3. 生成阶段（由 Orchestrator 执行）：
   检索结果 + 用户问题 → LLM 生成回答

【技术选型对比】

| 组件 | 选型 | 备选方案 | 选型理由 |
|------|------|----------|----------|
| 向量数据库 | pgvector | Milvus, Pinecone | 与现有 PostgreSQL 集成，运维成本低 |
| Embedding | Model Gateway | OpenAI, Cohere | 统一网关管理，支持国产模型 |
| 分块策略 | 段落感知 | 固定窗口, 语义分块 | 兼顾效率与上下文完整性 |
| 检索策略 | 混合检索 | 纯向量, 纯关键词 | 向量语义 + 关键词精确匹配 |
| 文档解析 | unstructured | PyPDF, python-docx | 多格式支持，生产级稳定性 |

【模块结构】
- api/          : FastAPI 路由层（文档管理、检索）
- core/         : 配置、异常、常量
- indexers/     : 向量索引器（pgvector 封装）
- processors/   : 文档处理器（PDF/DOCX/TXT 解析）
- retrievers/   : 检索器（向量检索、混合检索）
- schemas/      : Pydantic 数据模型

【关键指标】
- 索引吞吐量: ≥ 100 chunks/s
- 检索延迟 P95: < 200ms
- 检索召回率: ≥ 85% (Top-10)

【参考文档】
- docs/04-data-design-complete.md: 知识库表结构设计
- docs/05-performance-optimization.md: 向量检索优化策略
"""

__version__ = "1.0.0"
