# Agent Platform — 开发流程

> 通用 TDD/提交/审查流程见全局 CLAUDE.md，Agent/LLM 规则见 rules/agent-llm.md。
> 本文档只记录项目特有的开发流程。

---

## Agent 开发流程

### 新增 LangGraph 节点
1. 在 `app/graph/nodes/` 创建节点文件
2. 定义 State → TypedDict
3. 实现节点函数：`async def xxx_node(state: AgentState) -> dict`
4. 在 `graph/builder.py` 注册节点
5. 在 `graph/router.py` 定义路由条件
6. 添加单元测试 → 运行集成测试

### 新增工具
1. 在 `app/tools/` 创建工具文件
2. 定义 Tool Schema (Pydantic)
3. 实现工具逻辑
4. 在 `app/tools/__init__.py` 注册
5. 更新 `contracts/tool-schema/` JSON Schema
6. 添加单元测试 → Gold Set 测试用例

### 新增 LLM Provider
1. 在 `model-gateway/app/providers/` 创建 Provider 类
2. 继承 `BaseLLMProvider`，实现 `chat_completion` / `stream`
3. 添加认证和重试逻辑
4. 在 config 注册 → 添加测试 → 更新路由策略

---

## 性能基准

| 指标 | 目标 |
|------|------|
| 简单问答 P95 | < 6s |
| 单工具任务 P95 | < 15s |
| 多步任务 P95 | < 30s |
| 工具调用成功率 | ≥ 98% |

修改核心路径时运行 `make benchmark`，退化 > 10% 需分析。

---

## PR 检查项

- [ ] CI 全部通过
- [ ] 代码覆盖率 ≥ 80%
- [ ] 无安全漏洞 (HIGH/CRITICAL)
- [ ] 文档更新（如有 API/Proto 变更）
