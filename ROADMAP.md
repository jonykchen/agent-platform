# Agent Platform 路线图

> 本文档描述项目的开发计划和里程碑。
> 详细技术方案见 [docs/](docs/00-index.md)。

---

## Phase 1: MVP（已完成）✅

**目标**：核心链路打通，验证架构可行性。

| 模块 | 状态 | 说明 |
|------|------|------|
| Gateway (Java) | ✅ 已完成 | API 入口 + JWT 认证 + 租户隔离 |
| Orchestrator (Python) | ✅ 已完成 | LangGraph 状态机 + ReAct 模式 |
| Model Gateway (Python) | ✅ 已完成 | 多 LLM 接入 + 流式输出 |
| Tool Bus (Java) | ✅ 已完成 | 工具注册 + 执行 + 五层权限 |
| Governance (Java) | ✅ 已完成 | 风控引擎 + 审批流 |
| Knowledge (Python) | ✅ 已完成 | RAG + 向量检索 + 文档处理 |
| 前端 (React) | ✅ 已完成 | 对话界面 + 管理后台 |

---

## Phase 2: 生产加固（已完成）✅

**目标**：达到生产环境部署标准。

| 模块 | 状态 | 说明 |
|------|------|------|
| CI/CD 流水线 | ✅ 已完成 | Lint → Test → Security → Docker → Deploy |
| 安全加固 | ✅ 已完成 | mTLS / RLS / 敏感信息脱敏 / 加密存储 |
| 可观测性 | ✅ 已完成 | OTel + Prometheus + Grafana |
| 测试体系 | ✅ 已完成 | 931 个测试文件 |
| 文档体系 | ✅ 已完成 | 13 个核心文档全部已实施 |

---

## Phase 3: 能力增强（规划中）📋

**目标**：提升平台能力和用户体验。

| 模块 | 优先级 | 说明 |
|------|--------|------|
| 多模型灰度发布 | P1 | 模型 A/B 测试、成本对比、自动降级 |
| 高级 RAG | P1 | 多路召回、重排序优化、知识图谱 |
| 插件系统 | P2 | 工具热插拔、自定义工具 SDK |
| 会话记忆增强 | P2 | 长期记忆、跨会话上下文、个性化 |
| 多语言支持 | P3 | i18n 国际化 |
| 模型评测 | P3 | 自动化评测框架、评测集管理 |

---

## Phase 4: 规模化（规划中）📋

**目标**：支持大规模企业部署。

| 模块 | 优先级 | 说明 |
|------|--------|------|
| 多租户 RLS 增强 | P1 | 行级安全策略完善、租户数据隔离验证 |
| 配额管理 | P1 | Token 用量限制、API 调用频率控制 |
| 水平扩展 | P2 | K8s HPA 自动扩缩容、负载均衡优化 |
| 私有化部署 | P2 | Helm Chart、离线安装包、一键部署脚本 |
| 合规认证 | P3 | 等保三级、SOC 2、ISO 27001 |

---

## 贡献

欢迎社区参与！请阅读 [贡献指南](CONTRIBUTING.md) 了解如何参与项目开发。

如有建议或想法，请提交 [Feature Request](https://github.com/jonychen/agent-platform/issues/new?template=feature_request.md)。
