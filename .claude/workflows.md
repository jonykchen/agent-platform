# Agent Platform — 高效开发流程

> 基于 Claude Code 的智能化开发工作流

---

## 1. 智能任务启动

### 1.1 自动上下文加载
```
任务开始时 Claude 自动：
1. 读取 project_phase.md → 确认当前阶段优先级
2. 读取 tech_decisions.md → 遵循已有架构决策
3. 搜索相关代码 → 理解现有实现模式
4. 读取 user_preferences.md → 调整输出风格
```

### 1.2 任务分类与流程
| 任务类型 | 推荐流程 |
|---------|---------|
| 新功能 | 搜索 → Plan → 确认 → Task拆分 → 实现 → 测试 → 提交 |
| Bug修复 | 复现 → 定位 → 分析 → 修复 → 回归测试 → 提交 |
| 重构 | 分析 → Plan → 确认 → 小步重构 → 测试 → 提交 |
| 文档 | 搜索 → 理解 → 编写 → 校验 → 提交 |

---

## 2. Agent 开发特化流程

### 2.1 新增 LangGraph 节点
```
流程:
1. 在 app/graph/nodes/ 创建节点文件
2. 定义节点的 State → TypedDict
3. 实现节点函数: async def xxx_node(state: AgentState) -> dict
4. 在 graph/builder.py 中注册节点
5. 在 graph/router.py 中定义路由条件
6. 添加单元测试
7. 运行集成测试验证
```

### 2.2 新增工具
```
流程:
1. 在 app/tools/ 创建工具文件
2. 定义 Tool Schema (Pydantic)
3. 实现工具逻辑
4. 在 app/tools/__init__.py 注册
5. 更新 contracts/tool-schema/ 的 JSON Schema
6. 添加单元测试
7. 在 Gold Set 中添加测试用例
```

### 2.3 新增 LLM Provider
```
流程:
1. 在 model-gateway/app/providers/ 创建 Provider 类
2. 继承 BaseLLMProvider
3. 实现 chat_completion / stream 方法
4. 添加认证和重试逻辑
5. 在 config 中注册 provider
6. 添加 Provider 测试
7. 更新路由策略配置
```

---

## 3. 测试驱动开发 (TDD)

### 3.1 测试优先流程
```
用户: "添加订单查询工具"

Claude:
1. [创建测试] tests/tools/test_query_order.py
   - 正常查询
   - 订单不存在
   - 权限不足
   - 参数校验
   
2. [实现工具] app/tools/query_order.py
   - 满足所有测试用例
   
3. [运行测试] make test
   - 确保全部通过
   
4. [提交] git commit
```

### 3.2 测试命名规范
```python
# 单元测试
test_<function>_<scenario>_<expected>()
test_query_order_with_valid_id_returns_order()
test_query_order_with_invalid_id_raises_error()

# 集成测试
test_<flow>_<scenario>()
test_chat_flow_with_tool_calling()
test_agent_run_with_approval_required()
```

---

## 4. 智能代码生成

### 4.1 Python 代码模板
```python
# 新节点模板
async def xxx_node(state: AgentState) -> dict:
    """
    XXX 节点说明
    
    输入状态: state["xxx"]
    输出状态: {"key": value}
    """
    logger.info("xxx_node started", run_id=state["run_id"])
    
    try:
        # 业务逻辑
        result = await _process(state)
        
        logger.info("xxx_node completed", run_id=state["run_id"])
        return {"next_key": result}
    except Exception as e:
        logger.error("xxx_node failed", error=str(e), run_id=state["run_id"])
        raise
```

### 4.2 Java 代码模板
```java
// 新 Service 模板
@Service
@Slf4j
@RequiredArgsConstructor
public class XxxService {
    
    private final XxxRepository repository;
    
    public XxxResponse execute(XxxRequest request) {
        log.info("[{}] XxxService.execute started, param={}", 
            RequestIdGenerator.getCurrent(), request);
        
        // 参数校验
        validateRequest(request);
        
        try {
            // 业务逻辑
            var result = doExecute(request);
            
            log.info("[{}] XxxService.execute completed", 
                RequestIdGenerator.getCurrent());
            return result;
        } catch (BusinessException e) {
            log.warn("[{}] XxxService.execute failed: {}", 
                RequestIdGenerator.getCurrent(), e.getMessage());
            throw e;
        }
    }
}
```

---

## 5. 自动化质量检查

### 5.1 提交前检查清单
```
每次提交自动执行:
□ Python 语法检查 (py_compile)
□ Python Lint (ruff)
□ Java 编译检查
□ Proto Lint (buf)
□ 单元测试 (pytest)
□ 敏感信息扫描 (gitleaks)
```

### 5.2 PR 检查清单
```
PR 创建时自动检查:
□ CI 全部通过
□ 代码覆盖率 ≥ 80%
□ 无安全漏洞 (HIGH/CRITICAL)
□ 文档更新
□ CHANGELOG 更新 (如有破坏性变更)
```

---

## 6. 性能基准自动化

### 6.1 性能回归检测
```
当修改核心路径时自动:
1. 运行基准测试: make benchmark
2. 对比基线性能
3. 如果退化 > 10%，发出警告
4. 提示性能瓶颈分析
```

### 6.2 Agent 性能指标
```
关键指标监控:
- 简单问答 P95: < 6s
- 单工具任务 P95: < 15s
- 多步任务 P95: < 30s
- Token 使用效率: 输出/输入 ≥ 0.5
- 工具调用成功率: ≥ 98%
```

---

## 7. 安全自动化

### 7.1 敏感信息检测
```
写入文件时自动扫描:
- API Key: sk-[a-zA-Z0-9]{20,}
- JWT: eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*
- 密码字段: password, secret, token
- 手机号: 1[3-9]\d{9}
- 身份证: \d{17}[\dXx]
```

### 7.2 Prompt 注入检测
```
创建 Prompt 文件时自动:
- 检测已知注入模式
- 提示添加防护措施
- 推荐使用结构化包装
```

---

## 8. 文档自动化

### 8.1 API 文档同步
```
修改 OpenAPI/Proto 时:
1. 重新生成文档
2. 检查破坏性变更
3. 更新 README 链接
```

### 8.2 CHANGELOG 自动生成
```
根据提交消息自动生成:
- feat: → 新功能
- fix: → Bug 修复
- breaking: → 破坏性变更
- perf: → 性能优化
```

---

## 9. 智能提交流程

### 9.1 提交消息生成
```
根据变更自动生成:
- 文件路径 → scope
- 变更类型 → feat/fix/refactor
- 变更内容 → 简短描述

示例:
services/orchestrator-python/app/graph/nodes/thinker.py
→ feat(orchestrator): add thinker node with retry logic
```

### 9.2 PR 描述生成
```
自动分析变更:
1. 扫描修改文件
2. 提取关键变更
3. 生成 Summary
4. 推断 Test plan
5. 生成 Checklist
```

---

## 10. 快捷命令

| 命令 | 说明 |
|------|------|
| `/agent-test` | 运行 Agent 测试并生成覆盖率 |
| `/agent-lint` | 检查所有服务代码质量 |
| `/agent-start` | 启动完整开发环境 |
| `/security-scan` | 运行安全扫描 |
| `/ci-local` | 本地运行完整 CI |
| `/benchmark` | 运行性能基准测试 |
| `/review-pr` | 审查当前分支变更 |

---

## 11. 最佳实践提示

### 11.1 请求功能时
```
✅ 好: "添加订单查询工具，支持按订单号和用户ID查询"
❌ 差: "加个工具"
```

### 11.2 报告 Bug 时
```
✅ 好: "JWT 验证失败，错误信息 'Token expired'，复现步骤..."
❌ 差: "认证报错了"
```

### 11.3 重构请求时
```
✅ 好: "重构 thinker 节点，提取重试逻辑为独立函数"
❌ 差: "优化一下代码"
```

---

## 12. 效率统计

```
每周自动生成:
- 任务完成数
- 代码提交数
- 测试覆盖率变化
- 性能指标趋势
- 安全漏洞修复数
```
