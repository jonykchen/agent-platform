# Agent Platform — Claude Commands
# 自定义命令定义

## /agent-test
运行 Agent 相关测试并生成覆盖率报告
```bash
cd services/orchestrator-python && uv run pytest tests/ -v --cov=app --cov-report=html
```

## /agent-lint
检查 Python 服务代码质量
```bash
cd services/orchestrator-python && uv run ruff check . && uv run ruff format --check .
```

## /agent-start
启动本地开发环境（包含基础设施）
```bash
make dev && echo "Waiting for services..." && sleep 5 && docker compose -f infra/docker-compose.yml ps
```

## /agent-stop
停止开发环境
```bash
make dev-down
```

## /proto-gen
生成 Proto 代码
```bash
buf generate && echo "Proto code generated successfully"
```

## /db-reset
重置开发数据库（危险操作）
```bash
echo "This will reset the database. Are you sure?" && read confirm && [ "$confirm" = "yes" ] && psql -h localhost -U app_user -d agent_platform -f shared/sql/reset_dev.sql
```

## /security-scan
运行安全扫描
```bash
gitleaks detect --source . --verbose || true && trivy fs --severity HIGH,CRITICAL . || true
```

## /ci-local
本地运行完整 CI 流程
```bash
make ci
```

## /review-pr
审查当前分支的变更
```bash
git diff origin/master...HEAD --stat && git log origin/master..HEAD --oneline
```
