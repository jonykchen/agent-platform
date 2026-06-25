# Agent Platform 架构图

> 本文档包含系统架构的可视化图表，帮助新成员快速理解系统设计。

## 系统架构图

```mermaid
graph TB
    subgraph "用户层"
        User[用户/客户端]
    end

    subgraph "接入层"
        Gateway[Gateway<br/>Java 17 + Spring Boot<br/>:8080/:9091]
    end

    subgraph "编排层"
        Orchestrator[Orchestrator<br/>Python 3.12 + FastAPI + LangGraph<br/>:8001/:50100]
    end

    subgraph "模型层"
        ModelGateway[Model Gateway<br/>Python 3.12 + FastAPI<br/>:8002]
        subgraph "LLM Providers"
            Qwen[通义千问]
            Zhipu[智谱 AI]
            Deepseek[DeepSeek]
        end
    end

    subgraph "工具层"
        ToolBus[Tool Bus<br/>Java 21 + Spring Boot<br/>:8083/:40051]
        ExternalTools[外部工具/API]
    end

    subgraph "治理层"
        Governance[Governance<br/>Java 21 + Spring Boot<br/>:8082]
        Approval[人工审批]
    end

    subgraph "知识层"
        Knowledge[Knowledge<br/>Python 3.12 + FastAPI<br/>:8003]
        RAG[RAG 知识库]
        Embedding[Embedding<br/>text-embedding-v3<br/>1024 维]
    end

    subgraph "数据层"
        PostgreSQL[(PostgreSQL 16<br/>pgvector)]
        Redis[(Redis 7)]
        Kafka[[Kafka 3.6]]
        MinIO[(MinIO)]
    end

    subgraph "可观测性"
        OTel[OpenTelemetry Collector<br/>:4317]
        Prometheus[(Prometheus<br/>:9090)]
        Grafana[(Grafana<br/>:3000)]
    end

    User --> Gateway
    Gateway -->|gRPC| Orchestrator
    Orchestrator -->|HTTP| ModelGateway
    ModelGateway --> Qwen
    ModelGateway --> Zhipu
    ModelGateway --> Deepseek
    Orchestrator -->|gRPC| ToolBus
    ToolBus --> ExternalTools
    Orchestrator -->|HTTP| Governance
    Governance --> Approval
    Orchestrator -->|HTTP| Knowledge
    Knowledge --> RAG
    Knowledge -->|Embedding API| ModelGateway
    Knowledge --> PostgreSQL
    Orchestrator --> PostgreSQL
    Orchestrator --> Redis
    Orchestrator --> Kafka
    Knowledge --> MinIO
    Orchestrator --> OTel
    OTel --> Prometheus
    Prometheus --> Grafana

    style Gateway fill:#E8F5E9
    style Orchestrator fill:#E3F2FD
    style ModelGateway fill:#FFF3E0
    style ToolBus fill:#F3E5F5
    style Governance fill:#FFEBEE
    style Knowledge fill:#E0F7FA
```

## Agent 执行流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant G as Gateway
    participant O as Orchestrator
    participant M as Model Gateway
    participant T as Tool Bus
    participant Gov as Governance

    U->>G: 发送消息
    G->>O: gRPC 转发
    O->>O: 创建 AgentState
    O->>M: 调用 LLM

    loop ReAct 循环
        M-->>O: 返回响应（可能含工具调用）
        alt 需要工具调用
            O->>T: gRPC 调用工具
            T->>T: 五层权限检查
            alt 高风险工具
                T->>Gov: 请求审批
                Gov-->>T: 审批结果
            end
            T-->>O: 工具结果
            O->>M: 继续推理
        else 最终响应
            O-->>G: 返回结果
        end
    end

    G-->>U: 返回响应
```

## RAG 知识库流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant O as Orchestrator
    participant K as Knowledge
    participant M as Model Gateway
    participant DB as PostgreSQL<br/>(pgvector)

    rect rgb(232, 245, 233)
        Note over K,DB: 文档索引流程
        U->>K: 上传文档
        K->>K: 分块 (chunk_size=500)
        K->>M: Embedding 请求<br/>text-embedding-v3
        M-->>K: 返回 1024 维向量
        K->>DB: 存储 chunk + embedding<br/>HNSW 索引
    end

    rect rgb(227, 242, 253)
        Note over O,DB: RAG 检索流程
        U->>O: 用户提问
        O->>O: thinking 节点<br/>判断需要知识检索
        O->>K: 语义检索请求
        K->>M: Query Embedding
        M-->>K: Query 向量
        K->>DB: pgvector 余弦相似度搜索<br/>top-k + 重排序
        K-->>O: 返回相关文档片段
        O->>O: 将检索结果注入上下文
        O->>M: 带上下文的 LLM 调用
        M-->>O: 增强回答
        O-->>U: 返回结果
    end
```

## 数据流向图

```mermaid
graph LR
    subgraph "输入"
        UserInput[用户输入]
        SystemPrompt[系统提示词]
    end

    subgraph "处理"
        TokenCounter[Token 计数]
        ContextTruncation[上下文截断]
        LLMCall[LLM 调用]
        ToolExecution[工具执行]
    end

    subgraph "输出"
        Response[响应]
        Streaming[流式输出]
        ToolResults[工具结果]
    end

    subgraph "存储"
        ConversationHistory[对话历史]
        LongTermMemory[长期记忆]
        KnowledgeBase[知识库]
        VectorDB[(pgvector<br/>1024 维)]
    end

    UserInput --> TokenCounter
    SystemPrompt --> TokenCounter
    TokenCounter --> ContextTruncation
    ContextTruncation --> LLMCall
    LLMCall --> Response
    LLMCall --> Streaming
    LLMCall --> ToolExecution
    ToolExecution --> ToolResults
    Response --> ConversationHistory
    ToolResults --> ConversationHistory
    ConversationHistory --> LongTermMemory
    KnowledgeBase --> VectorDB
    VectorDB -->|余弦相似度| LLMCall
```

## 部署架构图

```mermaid
graph TB
    subgraph "Kubernetes 集群"
        subgraph "Ingress"
            IngressController[Ingress Controller<br/>Nginx/Traefik]
        end

        subgraph "应用层 (Deployment)"
            GatewayPod[Gateway Pod<br/>replicas: 3]
            OrchestratorPod[Orchestrator Pod<br/>replicas: 3]
            ModelGWPod[Model GW Pod<br/>replicas: 2]
            ToolBusPod[Tool Bus Pod<br/>replicas: 2]
            GovernancePod[Governance Pod<br/>replicas: 2]
            KnowledgePod[Knowledge Pod<br/>replicas: 2]
            FrontendPod[Frontend Pod<br/>replicas: 2]
        end

        subgraph "数据层 (StatefulSet)"
            PostgreSQLPod[(PostgreSQL<br/>Primary + Replica)]
            RedisPod[(Redis<br/>Sentinel)]
            KafkaPod[[Kafka<br/>3 Brokers]]
            MinIOPod[(MinIO<br/>4 Disks)]
        end

        subgraph "可观测性"
            OTelPod[OTel Collector]
            PrometheusPod[Prometheus]
            GrafanaPod[Grafana]
        end

        subgraph "Config & Secrets"
            ConfigMap[ConfigMap]
            Secrets[Secrets]
        end
    end

    IngressController --> GatewayPod
    GatewayPod --> OrchestratorPod
    OrchestratorPod --> ModelGWPod
    OrchestratorPod --> ToolBusPod
    OrchestratorPod --> GovernancePod
    OrchestratorPod --> KnowledgePod
    OrchestratorPod --> PostgreSQLPod
    OrchestratorPod --> RedisPod
    OrchestratorPod --> KafkaPod
    KnowledgePod --> PostgreSQLPod
    KnowledgePod --> MinIOPod

    ConfigMap --> GatewayPod
    ConfigMap --> OrchestratorPod
    Secrets --> GatewayPod
    Secrets --> OrchestratorPod

    OrchestratorPod --> OTelPod
    OTelPod --> PrometheusPod
    PrometheusPod --> GrafanaPod

    style IngressController fill:#90CAF9
    style PostgreSQLPod fill:#A5D6A7
    style RedisPod fill:#FFCC80
    style KafkaPod fill:#CE93D8
```

## 相关文档

- [技术方案总览](00-index.md)
- [数据设计](04-data-design-complete.md)
- [部署指南](06-operability-guide.md)
