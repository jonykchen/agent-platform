# 贡献指南

感谢你对 Agent Platform 的关注！我们欢迎所有形式的贡献。

## 快速开始

1. **Fork** 本仓库
2. 创建功能分支：`git checkout -b feat/your-feature`
3. 提交变更：遵循[提交规范](#提交规范)
4. 推送分支：`git push origin feat/your-feature`
5. 创建 **Pull Request**

## 开发环境搭建

详细步骤请参阅 [快速启动文档](docs/quick-start.md)。

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/agent-platform.git
cd agent-platform

# 2. 配置环境变量
cp .env.example .env.local
# 编辑 .env.local 填入必要配置

# 3. 启动基础设施
make dev

# 4. 安装依赖并运行测试
make ci
```

## 代码规范

### Python

- 使用 [Ruff](https://docs.astral.sh/ruff/) 进行 lint 和格式化
- 类型注解：使用 Python 3.12+ 语法
- 配置文件：`pyproject.toml` 中的 ruff 规则

```bash
# Lint 检查
make lint-python

# 格式化
make fmt-python
```

### Java

- 使用 [Checkstyle](shared/java-config/checkstyle.xml) 进行代码风格检查
- Spring Boot 3.2 最佳实践
- 使用虚拟线程（Java 21+）

```bash
# Lint 检查
make lint-java
```

### 前端

- 使用 ESLint + Prettier
- React + TypeScript

```bash
make lint-frontend
```

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <description>
```

**类型**：
- `feat`: 新功能
- `fix`: 修复 Bug
- `refactor`: 重构（不改变功能）
- `docs`: 文档变更
- `test`: 测试相关
- `chore`: 构建/工具变更

**示例**：
```
feat(orchestrator): 添加对话摘要生成功能
fix(gateway): 修复 JWT 过期时间未生效的问题
docs(readme): 更新安装步骤
```

## PR 检查清单

提交 PR 前，请确认：

- [ ] 代码通过 lint 检查（`make lint`）
- [ ] 所有测试通过（`make test`）
- [ ] 新功能有对应测试覆盖
- [ ] 提交信息符合规范
- [ ] 不包含敏感信息（密钥、密码等）
- [ ] 文档已更新（如需要）

## 代码审查

所有 PR 需要至少一位维护者审查后才能合并。我们会尽量在 3 个工作日内完成审查。

## 报告问题

- **Bug 报告**：使用 [GitHub Issues](https://github.com/your-username/agent-platform/issues)，选择 Bug Report 模板
- **功能建议**：使用 GitHub Issues，选择 Feature Request 模板
- **安全问题**：请勿公开报告，参见 [SECURITY.md](SECURITY.md)

## 许可证

提交代码即表示你同意在 [AGPL-3.0](LICENSE) 协议下贡献你的代码。
