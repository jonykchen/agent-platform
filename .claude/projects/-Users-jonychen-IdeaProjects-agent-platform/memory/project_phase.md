---
name: project_phase
description: 项目当前开发阶段和里程碑追踪
type: project
---

# Agent Platform 项目阶段

**当前阶段**: Phase 1 - MVP 开发
**更新时间**: 2026-05-09

## Phase 1: MVP (第 1-4 周) 🔄 进行中

### 核心交付物
- [ ] Gateway Service (Java) - 统一 API 入口
- [ ] Orchestrator (Python) - Agent 编排引擎
- [ ] Model Gateway (Python) - 模型统一网关
- [ ] Tool Bus (Java) - 工具总线 (Mock 版本)

### 成功标准
- E2E 跑通完整链路
- request_id 全链路贯穿
- 基础对话功能可用

### 当前进度
- ✅ 工程基础设施搭建完成 (Makefile, buf, editorconfig)
- ✅ 技术方案文档 v2.1 完成
- 🔄 Gateway Service 开发中
- ⏳ Orchestrator 待启动

## Phase 2: 业务闭环 (第 5-12 周) ⏳ 待开始

- 真实工具接入
- 风控 + 审批流程
- Kafka 回调恢复
- Gold Set 评测 (≥30条)

## Phase 3: 能力增强 (第 13-20 周) ⏳ 待开始

- RAG 知识库
- 多模态支持
- 评测体系
- 灰度发布

## Phase 4: 规模化 (第 21 周+) ⏳ 待开始

- 多租户完整隔离
- 成本治理
- 自进化能力

---
**How to apply**: 开发任务优先级按 Phase 顺序，Phase 1 未完成前不进入 Phase 2。
