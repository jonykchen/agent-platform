---
name: dev_workflow
description: 项目开发工作流和 CI 检查项
type: reference
---

# 开发工作流

## CI 检查项
- Python 语法检查 (py_compile)
- Python Lint (ruff)
- Java 编译检查
- Proto Lint (buf)
- 单元测试 (pytest)
- 敏感信息扫描 (gitleaks)

## 测试命名规范
```python
# 单元测试
test_<function>_<scenario>_<expected>()
test_query_order_with_valid_id_returns_order()

# 集成测试
test_<flow>_<scenario>()
test_chat_flow_with_tool_calling()
```
