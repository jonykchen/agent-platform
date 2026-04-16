# LLM 评测框架技术选型：Langfuse vs LangSmith

> 创建日期：2026-05-13
> 最后更新：2026-05-18
> 适用项目：Agent Platform（Python 编排 + Java 核心服务 + 国内 LLM）
> 数据来源：LangSmith 官方文档（docs.langchain.com）、Langfuse 官方文档（langfuse.com/docs）

---

## 1. 执行摘要

| 维度 | Langfuse | LangSmith | 推荐 |
|------|----------|-----------|------|
| **开源** | ✅ MIT（核心），EE 部分闭源 | ❌ 闭源商业 | Langfuse |
| **自托管** | ✅ Docker/K8s/Helm，所有层级免费 | 🟡 仅 Enterprise 支持（需 License） | Langfuse |
| **国内 LLM 支持** | ✅ Provider 无关，LiteLLM 集成 100+ 模型 | 🟡 框架无关，但偏向 OpenAI/Anthropic | Langfuse |
| **数据安全** | ✅ 自托管完全自主；Cloud 支持 US/EU/JP | 🟡 Cloud 存 LangChain 云端；Hybrid/Self-hosted 数据在私有云 | Langfuse |
| **评测功能** | ✅ Dataset/Eval/LLM-as-Judge/Annotation | ✅ 更成熟的离线+在线 Eval，Pairwise 对比，agentevals | LangSmith 优 |
| **Java 集成** | ✅ OpenTelemetry 原生 + REST API | ✅ OpenTelemetry 原生（SDK ≥ 0.4.25）+ REST API | 持平 |
| **Agent 部署** | ❌ 无内置 | ✅ Agent Server + Standalone Server | LangSmith |
| **定价** | 自托管免费；Cloud Hobby 免费（50k units） | Free $0；Plus 按席位计费；Enterprise 自托管 | Langfuse |
| **社区活跃度** | GitHub 27.1k stars，300+ 贡献者 | 闭源，LangChain 官方维护 | Langfuse |

**结论：推荐 Langfuse**

核心原因：开源自托管零门槛、国内 LLM 友好、成本可控、数据自主。

> ⚠️ **2026-05 重要更新**：LangSmith 已支持 OpenTelemetry（SDK ≥ 0.4.25），Java 集成难度与 Langfuse 持平。LangSmith 在 Evaluation 能力上明显领先（Online Eval 闭环、Pairwise、agentevals）。若预算充足且 Evaluation 是核心需求，可考虑 LangSmith Enterprise 或混合方案。详见 [7.3 备选方案](#73-备选方案)。

---

## 2. 框架概述

### 2.1 Langfuse

**定位**：开源 LLM 工程平台（YC W23），提供 Observability、Prompt Management、Evaluation、Dataset 管理、Playground。已被 ClickHouse 收购。

**核心特性**：
- **开源自托管**：MIT 协议（核心），EE 部分功能闭源；Docker Compose / K8s Helm / Terraform（AWS/Azure/GCP）一键部署
- **Provider 无关**：原生支持 OpenAI、Anthropic，通过 LiteLLM 集成 100+ 模型（含通义、文心、智谱等国内模型）
- **OpenTelemetry 原生**：支持 Java、Go 等语言的 OTel 协议接入，与项目现有 OTel 体系无缝衔接
- **完整可观测性**：Trace → Span → Generation 三层结构；Agent Graph 可视化；Session/User 追踪
- **评测体系**：Dataset + Experiment + LLM-as-Judge + Annotation Queue + 自定义评估函数
- **Prompt 管理**：版本控制 + 变量注入 + Playground 交互测试 + Protected Deployment Labels
- **SDK 支持**：Python、JS/TS（官方），OpenTelemetry（Java/Go/自定义），REST API（全语言）
- **50+ 框架集成**：LangChain、LlamaIndex、Haystack、CrewAI、Vercel AI SDK、Instructor、DSPy 等

**技术栈**：
```
Frontend: Next.js + Tailwind
Backend: Next.js API Routes + Prisma + ClickHouse
Database: PostgreSQL（元数据）+ ClickHouse（分析查询）
Cache: Redis（可选，用于集群部署）
Queue: BullMQ（Worker 进程）
```

**版本信息**：v3.174.0（截至 2026-05-13），7,006+ commits，561 releases

### 2.2 LangSmith

**定位**：LangChain 官方商业平台，已从"LangChain 专属"演进为框架无关的 AI 工程平台。提供 Observability、Evaluation、Prompt Engineering、Agent Deployment。

**核心特性**：
- **框架无关**：支持 OpenAI、Anthropic、CrewAI、Vercel AI SDK、Pydantic AI 等多种框架（不再是 LangChain 专属）
- **三种部署模式**：Cloud（SaaS）/ Hybrid（控制面在 LangChain 云，数据面在私有云）/ Self-hosted（全栈私有，仅 Enterprise）
- **评测能力**：离线评测 + 在线评测；LLM-as-Judge / 代码规则 / 人工标注 / Pairwise 对比
- **Agent Deployment**：Agent Server 一键部署，支持 GitHub CI/CD 集成
- **商业支持**：SOC2 Type II / ISO27001 / HIPAA 合规，企业级 SLA
- **Polly AI 助手**：内置 AI 分析助手，自动分析 trace 性能和问题
- **LangSmith Studio**：可视化 Agent 设计和调试界面

**限制**：
- Self-hosted 和 Hybrid 仅 Enterprise 可用，门槛高
- 无原生 Java SDK（需 REST API 或 LangChain Java）
- 闭源，无法审计代码或自行修复

---

## 3. 功能对比

### 3.1 Tracing & Observability

| 功能 | Langfuse | LangSmith |
|------|----------|-----------|
| Trace 结构 | ✅ Observation 层级（Trace/Span/Generation） | ✅ Run Tree |
| 自动埋点 | ✅ `@observe()` 装饰器 / LangChain Callback / OpenAI drop-in | ✅ LangChain Callback / SDK wrap |
| 手动埋点 | ✅ `@observe()` / `langfuse.trace()` | ✅ `traceable()` |
| OpenTelemetry | ✅ 原生支持（Java/Go/自定义） | ✅ **原生支持**（SDK ≥ 0.4.25，2026-05 新增） |
| 元数据标签 | ✅ metadata/tags | ✅ tags/metadata |
| 用户/会话追踪 | ✅ user_id/session_id | ✅ user/session/threads |
| Agent Graph 可视化 | ✅ 图形化展示 Agent 执行流程 | ✅ Studio 可视化 |
| Token 用量 | ✅ 详细记录 + 费用追踪 | ✅ 详细记录 + 费用追踪 |
| 延迟统计 | ✅ Dashboard P50/P95/P99 | ✅ Dashboard 延迟分布 |
| 导出 | ✅ CSV/JSON/API/Batch Export/Blob Storage | ✅ Bulk Export/API |
| Alerting | ✅ Dashboard + Webhook | ✅ Automation Rules + Webhook + Alerts |
| AI 辅助分析 | 🟡 Ask AI（文档级别） | ✅ Polly AI 助手（trace 级别智能分析） |

> 💡 **关键更新（2026-05）**：LangSmith 已支持 OpenTelemetry（SDK ≥ 0.4.25），Java 层可通过 OTel 接入。两者在 OTel 支持上已持平，Langfuse 的 OTel 优势不再。LangSmith 新增 Polly AI 助手可自动分析 trace 性能问题和根因。

### 3.2 Evaluation

| 功能 | Langfuse | LangSmith |
|------|----------|-----------|
| Dataset 管理 | ✅ 创建/导入/版本/SDK | ✅ 创建/管理/SDK |
| 离线评测 | ✅ Experiment（SDK + UI） | ✅ Experiment（SDK + UI） |
| 在线评测 | ✅ 在线 Eval + 自动评分 | ✅ **更成熟的在线 Eval**（采样率、过滤、自动触发、失败案例回填） |
| LLM-as-Judge | ✅ 内置 Evaluator（托管运行） | ✅ 内置 Evaluator |
| 自定义评估 | ✅ Python 函数 / SDK score | ✅ Evaluator 类 / SDK（Python/JS Code Evaluator） |
| 人工标注 | ✅ Annotation Queue（Pro 无限） | ✅ Annotation Queue |
| Pairwise 对比 | 🟡 手动对比实验 | ✅ **内置 Pairwise 对比**（evaluate-pairwise） |
| CI/CD 集成 | ✅ SDK/API + Experiments CI/CD | ✅ Pytest/Vitest/Jest 集成 + SDK |
| 评估指标 | ✅ 自定义 score（numeric/boolean/categorical） | ✅ 内置多种 Eval + 自定义 |
| 评测工作流 | ✅ Dataset → Experiment → Analyze | ✅ **更完善的闭环**：Online Eval → 失败案例自动回填 Dataset → 离线验证 → 重新部署 |
| Trajectory Eval | 🟡 需自行实现 | ✅ **agentevals 包**（Trajectory Match + LLM-as-Judge） |

> 💡 **关键差异**：LangSmith 在 Evaluation 上明显领先——Online Eval 自动闭环、Pairwise 对比、agentevals trajectory 评估、Code Evaluator（Python/JS 在 UI 中编写）。Langfuse 的 Eval 功能够用，但闭环自动化体验不如 LangSmith 成熟。

### 3.3 Prompt Management

| 功能 | Langfuse | LangSmith |
|------|----------|-----------|
| 版本控制 | ✅ Prompt 版本管理 | ✅ Prompt Hub |
| 变量注入 | ✅ Mustache 模板 | ✅ 模板变量 |
| A/B 测试 | ✅ Experiment 对比 | ✅ Prompt 实验 |
| **Playground** | ✅ 交互式 Playground，trace 直接跳转调试 | ✅ Studio 交互测试 |
| Deployment Labels | ✅ Protected Deployment Labels（生产/灰度） | 🟡 基础支持 |
| Prompt Caching | ✅ 服务端+客户端双重缓存 | 🟡 未明确 |
| 审批流程 | 🟡 基础支持 | 🟡 基础支持 |

### 3.4 Deployment

| 部署方式 | Langfuse | LangSmith |
|----------|----------|-----------|
| SaaS | ✅ Cloud（US/EU/JP 区域） | ✅ Cloud（LangChain 托管） |
| Self-hosted | ✅ **所有层级免费**（MIT 协议） | 🟡 仅 Enterprise |
| Hybrid | N/A（自托管即完全自主） | ✅ 控制面 LangChain 云 + 数据面私有云（Enterprise） |
| K8s 部署 | ✅ Helm Chart | ✅ Enterprise 支持 |
| Terraform | ✅ AWS/Azure/GCP 模板 | ✅ Enterprise 支持 |
| 离线部署 | ✅ 支持（Air-gapped） | ✅ Enterprise 支持 |
| 数据区域 | ✅ Cloud: US/EU/JP；自托管: 自主 | ✅ Cloud: LangChain 云；Hybrid: 数据在私有云 |

> ⚠️ **重要更正**：LangSmith 已支持 Self-hosted 和 Hybrid 部署，但**仅限 Enterprise 计划**，门槛和成本远高于 Langfuse 的开源自托管。

### 3.5 独有功能对比

| 仅 Langfuse 有 | 仅 LangSmith 有 |
|----------------|----------------|
| 完全开源可审计（MIT 协议） | Agent Server 部署（一键上线 Agent） |
| LiteLLM 集成（100+ 模型代理） | Polly AI 助手（trace 级智能分析）[^1] |
| ClickHouse 分析引擎 | LangSmith Studio（可视化 Agent 设计） |
| 自托管零成本（无 License 费用） | Online Eval 自动闭环（失败案例回填 Dataset）[^2] |
| — | Pairwise Comparison（A/B 对比评测）[^3] |
| — | agentevals（Agent Trajectory 评估）[^4] |
| — | Standalone Server（轻量 Agent 部署，无控制面）[^5] |

[^1]: LangSmith Polly AI 助手 - https://docs.langchain.com/langsmith/observability
[^2]: LangSmith Online Evaluation - https://docs.langchain.com/langsmith/evaluation-types
[^3]: LangSmith Pairwise Evaluation - https://docs.langchain.com/langsmith/evaluate-pairwise
[^4]: LangSmith Agent Trajectory Evals - https://docs.langchain.com/langsmith/trajectory-evals
[^5]: LangSmith Standalone Server - https://docs.langchain.com/langsmith/self-hosted

---

## 4. 架构适配分析

### 4.1 Agent Platform 架构回顾

```
Gateway (Java) → Orchestrator (Python) → Model Gateway (Python)
                      ↓
               Tool Bus (Java) → Governance (Java)
                      ↓
               Knowledge (Python)
```

**关键约束**：
- Python 编排层（LangGraph）需深度集成
- Java 服务层（3 个服务）需轻量集成，已有 OpenTelemetry 基础设施
- 国内 LLM（通义、文心、智谱）
- 数据安全要求高（金融/政务场景）
- 可能有离线/私有云部署需求
- 现有观测栈：OpenTelemetry + Prometheus + Grafana

### 4.2 集成方案对比

#### Langfuse 集成

```python
# Python 编排层（LangGraph）— 方式一：@observe 装饰器
from langfuse.decorators import observe, langfuse_context

@observe(capture_input=True, capture_output=True)
async def thinking_node(state: AgentState) -> dict:
    result = await model.ainvoke(state["messages"])
    langfuse_context.update_current_observation(
        metadata={"model": "qwen-max", "tokens": result.usage}
    )
    return {"messages": [result]}

# Python 编排层 — 方式二：LangChain Callback（零代码改造）
from langfuse.langchain import CallbackHandler
langfuse_handler = CallbackHandler()
# 直接传入 config 即可，无需修改业务代码
result = await graph.ainvoke(state, config={"callbacks": [langfuse_handler]})
```

```java
// Java 服务层 — 方式一：OpenTelemetry（推荐，零改造）
// 项目已用 OTel，只需配置 OTel Exporter 指向 Langfuse
// 在 OTel Collector 中添加 Langfuse exporter 即可

// Java 服务层 — 方式二：REST API
@PostMapping("/trace")
public void createTrace(@RequestBody TraceRequest request) {
    // Langfuse 提供完整的 OpenAPI spec，可生成类型安全的 client
    HttpPost httpPost = new HttpPost(LANGFUSE_API_URL + "/api/public/traces");
    httpPost.setHeader("Authorization", "Bearer " + langfuseApiKey);
    httpPost.setEntity(new StringEntity(objectMapper.writeValueAsString(request)));
    httpClient.execute(httpPost);
}
```

#### LangSmith 集成

```python
# Python 编排层 — 方式一：LangChain 原生 Callback（最简集成）
from langchain.callbacks.tracers import LangChainTracer
tracer = LangChainTracer(project_name="agent-platform")
chain.invoke(input, config={"callbacks": [tracer]})

# Python 编排层 — 方式二：SDK wrap（非 LangChain 框架）
from langsmith import traceable
@traceable(run_type="llm", name="thinking")
async def thinking_node(state: AgentState) -> dict:
    ...
```

```java
// Java 服务层 — 方式一：OpenTelemetry（推荐，SDK ≥ 0.4.25）
// 配置 OTel Exporter 指向 LangSmith
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.smith.langchain.com/otel
OTEL_EXPORTER_OTLP_HEADERS="x-api-key=<your langsmith api key>"

// Java 服务层 — 方式二：REST API（备选）
HttpPost httpPost = new HttpPost("https://api.smith.langchain.com/api/v1/runs");
httpPost.setHeader("x-api-key", langsmithApiKey);
```

**对比结论**：

| 维度 | Langfuse | LangSmith |
|------|----------|-----------|
| Python 集成成本 | 低（`@observe` 或 LangChain Callback） | 极低（LangChain 原生 Callback） |
| Java 集成成本 | 极低（OTel 原生 / REST API + OpenAPI spec） | **极低**（OTel 原生，SDK ≥ 0.4.25）[^6] |
| 国内 LLM 集成 | 极低（LiteLLM / 任意 Provider） | 中（需包装为 GenAI 标准格式） |
| 非侵入式集成 | ✅ LangChain Callback / OTel | ✅ LangChain Callback / OTel |
| 租户隔离 | ✅ metadata + session_id | ✅ metadata + session |

[^6]: LangSmith OpenTelemetry 支持 - https://docs.langchain.com/langsmith/trace-with-opentelemetry

> 💡 **架构适配结论（2026-05 更新）**：LangSmith 已支持 OpenTelemetry，Java 层集成成本与 Langfuse 持平。两者均可通过 OTel Collector 接入，与项目现有观测栈完全兼容。Langfuse 在国内 LLM 集成上仍有优势（LiteLLM），LangSmith 在 LangChain/LangGraph 生态内体验更原生。

---

## 5. 成本分析

### 5.1 Langfuse 定价（2026-05 最新）

**Self-hosted（推荐）**：开源免费，无功能限制。

**Cloud 方案**：

| 方案 | 费用 | 包含用量 | 数据保留 | 用户数 | 适用场景 |
|------|------|----------|----------|--------|----------|
| **Hobby** | $0/月 | 50k units/月 | 30 天 | 2 人 | 个人/POC |
| **Core** | $29/月 | 100k units/月 | 90 天 | 无限 | 小团队生产 |
| **Pro** | $199/月 | 100k units/月 | 3 年 | 无限 | 规模化项目 |
| **Enterprise** | $2,499/月 | 100k units/月 | 3 年 | 无限 | 大型企业 |

> 超出用量：$8/100k units（阶梯递减，100k-1M $8，1M-10M $7，10M-50M $6.5，50M+ $6）
> 折扣：初创公司 50% off，教育/研究最高免费，开源项目 $300 credits/月

**Self-hosted 成本估算**：
```
AWS c6i.xlarge (4vCPU, 8GB): $150/月
PostgreSQL RDS db.t3.medium: $50/月
ClickHouse（分析查询加速）: $80/月（可选）
S3 Storage (100GB): $2.3/月
Network: ~$20/月
────────────────────────────────
Total: ~$220-300/月（支持百万级 traces）
```

### 5.2 LangSmith 定价

| 方案 | 费用 | 限制 |
|------|------|------|
| **Free** | $0 | 5k traces/月，个人使用 |
| **Plus** | 按席位 + 用量订阅 | 100k traces/月 |
| **Enterprise** | 定制（高） | 无限 traces，Self-hosted/Hybrid 需此层级 |

> LangSmith 未公开详细定价，Enterprise 门槛较高（需联系销售）。

### 5.3 年度成本对比

**场景假设**：10 个开发者，100k traces/月，需要数据自主管控

| 方案 | 年费用 | 数据位置 | 自托管 |
|------|--------|----------|--------|
| **Langfuse Self-hosted** | ~$2,640-3,600（基础设施） | 完全自主 | ✅ |
| Langfuse Cloud Core | ~$348（$29×12）+ 用量 | Langfuse Cloud（US/EU/JP） | ❌ |
| Langfuse Cloud Pro | ~$2,388（$199×12）+ 用量 | Langfuse Cloud（US/EU/JP） | ❌ |
| **LangSmith Cloud** | 估算 $10,000+（Plus 按席位） | LangChain Cloud | ❌ |
| **LangSmith Enterprise** | 估算 $30,000+（含 Self-hosted） | 私有云 | ✅ |

> 💡 **成本结论**：Langfuse Self-hosted 成本最可控（纯基础设施成本），LangSmith Enterprise 自托管成本比 Langfuse 高一个数量级。

---

## 6. 风险与限制

### 6.1 Langfuse

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| ClickHouse 收购影响 | 中 | MIT 协议可 fork；收购后资源更多，但需关注方向 |
| EE 功能闭源 | 低 | 核心功能（Tracing/Eval/Prompt）均开源，EE 主要是 SSO/审计日志 |
| 企业支持体系 | 中 | 提供 Enterprise 计划（$2,499/月），有专属支持 |
| 大规模部署经验 | 中 | 社区有百万级 traces 实践；企业级 SLA 仅 Cloud Enterprise |
| Java SDK 非官方 | 低 | **OpenTelemetry 原生支持**比 Java SDK 更标准；REST API 有 OpenAPI spec |
| 自托管运维 | 中 | Docker Compose 简单；K8s Helm 生产级；需维护 PostgreSQL/ClickHouse |

### 6.2 LangSmith

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 供应商锁定 | **高** | 闭源，无替代方案；数据导出可降低迁移成本 |
| 数据主权（Cloud） | **高** | Hybrid/Self-hosted 仅 Enterprise，门槛高 |
| 成本不可控 | **高** | Cloud 按席位+用量计费；Enterprise 价格不透明 |
| 国内访问 | 中 | Cloud 需网络代理；Self-hosted 无此问题但成本高 |
| 国内 LLM 适配 | 中 | 需包装为 GenAI 标准格式；社区案例较少 |
| Java 集成薄弱 | 低 | ~~无 OTel 支持，无 Java SDK~~ **已修正**：OTel 支持（SDK ≥ 0.4.25）[^6] |
| LangChain 依赖 | 低 | 已声明 framework-agnostic，但深度功能仍偏 LangChain 生态 |

### 6.3 共同风险

| 风险 | 说明 |
|------|------|
| 评测定义困难 | LLM 输出质量评估本身是开放问题，工具只是载体 |
| 性能开销 | 两个框架均增加约 5-15ms 延迟（SDK 埋点），可通过异步 flush 缓解 |
| 数据膨胀 | Traces 数据增长快，需定期归档或设置 TTL |
| 评估者偏差 | LLM-as-Judge 存在位置偏差/冗余偏差，需对抗性测试 |

---

## 7. 推荐方案

### 7.1 最终推荐：Langfuse

**核心原因**：

| # | 原因 | 详述 |
|---|------|------|
| 1 | **开源自托管零门槛** | MIT 协议，Docker Compose 5 分钟部署，无 Enterprise License 门槛 |
| 2 | **成本可控** | 自托管仅基础设施成本（~$220-300/月），无用量焦虑，无 License 费用 |
| 3 | **国内 LLM 友好** | LiteLLM 集成 100+ 模型，通义/文心/智谱开箱即用 |
| 4 | **合规安全** | 自托管数据完全自主，满足金融/政务合规要求 |
| 5 | **架构适配** | Python SDK + OTel（Java）+ REST API（全语言），覆盖全部服务 |
| 6 | **代码可审计** | 开源可审计安全漏洞，可自行修复或 fork |

> ⚠️ **2026-05 重要更新**：LangSmith 已支持 OpenTelemetry（SDK ≥ 0.4.25），"OTel 原生"不再是 Langfuse 独有优势。推荐 Langfuse 的核心原因调整为：**开源免费自托管** + **国内 LLM 友好** + **成本可控**。若团队预算充足且 Evaluation 成熟度是首要考量，可考虑 LangSmith Enterprise。

### 7.2 实施路线

```
Phase 1: 基础集成（1 周）
├── 部署 Langfuse Self-hosted（Docker Compose → 后续迁移 K8s Helm）
├── Python SDK 集成到 Orchestrator（@observe 装饰器 + LangChain Callback）
├── OTel Collector 配置 → Langfuse Exporter（Java 服务零改造接入）
└── 基础 Tracing 覆盖（Agent 全链路追踪）

Phase 2: 评测体系（2 周）
├── Dataset 创建（历史对话、标注数据、合成数据）
├── Evaluation Pipeline 搭建（LLM-as-Judge + 自定义 Python 评估函数）
├── Annotation Queue 配置（人工标注工作流）
└── 实验对比框架（Dataset → Experiment → Analyze）

Phase 3: Prompt 管理（1 周）
├── Prompt 版本管理 + Deployment Labels（生产/灰度隔离）
├── 模板变量注入（Mustache 模板）
├── Playground 交互测试（trace 问题直接跳转调试）
└── A/B 测试流程（Experiment 对比不同 Prompt 版本）

Phase 4: 监控 & 告警（1 周）
├── Dashboard 搭建（延迟/P95/Token 费用/错误率）
├── Webhook 告警（异常检测 → 飞书/企微通知）
└── 审计日志关联（Langfuse traces ↔ 现有审计表）

Phase 5: CI/CD 集成（1 周）
├── 自动化评测 Pipeline（PR 触发 → Dataset 回归测试）
├── 质量门禁（Eval score 阈值卡点）
└── Batch Export → Blob Storage（长期归档）
```

### 7.3 备选方案

#### 方案 B：LangSmith（Enterprise 自托管）

如果团队满足以下条件，可考虑 LangSmith：
- ✅ 预算充足（Enterprise 年费估算 $30,000+）
- ✅ 需要最成熟的 Evaluation 闭环（Online Eval 自动化）
- ✅ 需要 Agent 一键部署能力
- ✅ 已深度绑定 LangChain/LangGraph 生态

#### 方案 C：混合方案（Langfuse Observability + LangSmith Evaluation）

如果团队特别看重 Evaluation 成熟度但不需要 LangSmith 自托管：
- **Langfuse** 做 Observability + Prompt Management（Java OTel 集成 + 自托管）
- **LangSmith Cloud** 做 Evaluation（仅 Python 层，按量付费）
- 两者通过 Dataset 同步关联

> 混合方案增加了运维复杂度，建议先只用 Langfuse，评估不够时再引入 LangSmith。

---

## 8. 评估实操对比（帮助你快速上手）

### 8.1 Langfuse 评测工作流

```python
# Step 1: 创建 Dataset
from langfuse import Langfuse
langfuse = Langfuse()

dataset = langfuse.create_dataset(name="agent-qa-eval")

# 添加测试样本
dataset.create_item(
    input={"question": "查询订单状态"},
    expected_output={"answer": "调用 query_order_status 工具"},
)

# Step 2: 定义评估函数
from langfuse.decorators import observe

@observe()
def my_app(input_data):
    # 你的 Agent 调用逻辑
    return agent.run(input_data)

def custom_evaluator(output, expected):
    # 自定义评估逻辑
    return 1.0 if output["tool_calls"] else 0.0

# Step 3: 运行实验
from langfuse.eval import evaluate

evaluate(
    name="agent-v1-eval",
    data=dataset,
    task=my_app,
    evaluators=[custom_evaluator],
)

# Step 4: 在 UI 中查看结果 → Dataset → Experiments → 对比分析
```

### 8.2 LangSmith 评测工作流

```python
# Step 1: 创建 Dataset
from langsmith import Client
client = Client()

dataset = client.create_dataset("agent-qa-eval")
client.create_examples(
    dataset_id=dataset.id,
    inputs=[{"question": "查询订单状态"}],
    outputs=[{"answer": "调用 query_order_status 工具"}],
)

# Step 2: 定义评估函数
from langsmith.evaluation import evaluate as ls_evaluate

def custom_evaluator(run, example):
    # LangSmith Evaluator 接口
    return {"score": 1.0 if run.outputs.get("tool_calls") else 0.0}

# Step 3: 运行实验
ls_evaluate(
    target=my_app,
    data="agent-qa-eval",
    evaluators=[custom_evaluator],
)

# Step 4: 在 UI 中查看 → Compare experiments → Pairwise 对比
```

> 💡 两者评测工作流类似，LangSmith 的 API 更简洁，Langfuse 的 `@observe` 装饰器与 Tracing 集成更紧密。

---

## 10. 个人开发者学习建议

> 面向个人开发者、学习者、研究者的选择建议。

### 免费方案对比

| 维度 | Langfuse Hobby | LangSmith Free |
|------|----------------|----------------|
| **费用** | $0 | $0 |
| **用量限制** | 50k units/月 | 5k traces/月 |
| **数据保留** | 30 天 | 有限 |
| **用户数** | 2 人 | 个人 |
| **部署方式** | Cloud（US/EU/JP）或自托管 | Cloud SaaS |

### 选择建议

**推荐 LangSmith Free 的场景**：
- 正在学习 LangChain/LangGraph（原生集成，零配置）
- 想体验 Online Eval、Pairwise 对比、agentevals 等高级功能
- 短期 POC 或个人项目

**推荐 Langfuse 的场景**：
- 想研究源码或自托管学习架构实现
- 本地 Docker 部署体验完整平台
- 用量较大（50k vs 5k 限制）
- 长期学习或开源贡献

### 快速上手

**LangSmith（最简集成）**：
```bash
pip install langsmith
export LANGSMITH_API_KEY="your-key"
export LANGSMITH_TRACING=true
# 直接用 LangChain，自动追踪
```

**Langfuse（自托管学习）**：
```bash
# Docker Compose 一键部署
git clone https://github.com/langfuse/langfuse.git
cd langfuse
docker compose up

# Python SDK
pip install langfuse
from langfuse.decorators import observe

@observe()
def my_agent(input):
    return model.invoke(input)
```

---

## 11. 参考资源

### Langfuse

- [Langfuse 官方文档](https://langfuse.com/docs)
- [Langfuse GitHub](https://github.com/langfuse/langfuse)（27.1k stars）
- [Langfuse Self-hosting 指南](https://langfuse.com/docs/self-hosting)
- [Langfuse OpenTelemetry 集成](https://langfuse.com/docs/integrations/opentelemetry)
- [Langfuse 定价](https://langfuse.com/pricing)

### LangSmith

- [LangSmith 官方文档](https://docs.langchain.com/langsmith/home)
- [LangSmith Self-hosted 部署](https://docs.langchain.com/langsmith/self-hosted)（仅 Enterprise）
- [LangSmith OpenTelemetry 支持](https://docs.langchain.com/langsmith/trace-with-opentelemetry)（SDK ≥ 0.4.25）
- [LangSmith Online Evaluation](https://docs.langchain.com/langsmith/evaluation-types)
- [LangSmith Pairwise 对比](https://docs.langchain.com/langsmith/evaluate-pairwise)
- [LangSmith Agent Trajectory Evals](https://docs.langchain.com/langsmith/trajectory-evals)
- [LangSmith Pytest 集成](https://docs.langchain.com/langsmith/test-react-agent-pytest)

---

## 12. 文档更新记录

| 日期 | 版本 | 更新内容 | 来源 |
|------|------|----------|------|
| 2026-05-18 | v1.1 | 修正：LangSmith 已支持 OpenTelemetry；新增：agentevals、Standalone Server、个人开发者建议 | LangSmith 官方文档（2026-05） |
| 2026-05-13 | v1.0 | 初版 | Langfuse/LangSmith 官方文档 |
