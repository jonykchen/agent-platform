---
name: dev_workflow
description: 日常开发工作流和自动化流程
type: project
---

# 开发工作流

## 分支策略

```
master (生产)
    │
    ├── feature/xxx (功能分支)
    ├── fix/xxx (修复分支)
    └── refactor/xxx (重构分支)
```

**规则**: 
- 所有变更通过 PR 合并
- PR 必须通过 CI 检查
- 至少一人 Review 才能合并

---

## 开发流程

### 1. 开始任务
```bash
# 从 master 创建功能分支
git checkout master && git pull
git checkout -b feature/agent-memory
```

### 2. 开发中
```bash
# 运行本地检查
make lint

# 运行测试
make test

# 格式化代码
make fmt
```

### 3. 提交代码
```bash
# 查看变更
git status && git diff

# 提交（遵循 Conventional Commits）
git add <files>
git commit -m "feat(orchestrator): add conversation memory module"
```

### 4. 创建 PR
```bash
# 推送分支
git push -u origin feature/agent-memory

# 创建 PR
gh pr create --title "feat: add conversation memory" --body "$(cat <<'EOF'
## Summary
- 实现对话记忆滑动窗口
- 支持摘要压缩长对话

## Test plan
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 手动验证 E2E

🤖 Generated with [Claude Code](https://claude.ai/code)
EOF
)"
```

---

## 提交规范 (Conventional Commits)

| 类型 | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(orchestrator): add RAG retrieval node` |
| `fix` | Bug 修复 | `fix(gateway): correct JWT validation logic` |
| `refactor` | 重构 | `refactor(model-gateway): simplify provider routing` |
| `docs` | 文档 | `docs: update API documentation` |
| `test` | 测试 | `test(orchestrator): add unit tests for thinker node` |
| `chore` | 杂项 | `chore: update dependencies` |

---

## CI 检查项

每次 PR 必须通过:
1. Lint (ruff + checkstyle)
2. 格式化检查
3. 单元测试
4. 安全扫描 (trivy + gitleaks)
5. Proto 契约检查 (buf breaking)

---
**How to apply**: 所有代码变更遵循此流程，CI 不通过不得合并。
