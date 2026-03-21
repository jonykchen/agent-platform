# Agent Platform Web Frontend

企业级 Agent 平台前端应用，提供用户对话界面、管理后台和监控面板。

## 技术栈

- **框架**: React 18 + TypeScript 5
- **构建**: Vite 5
- **路由**: TanStack Router
- **状态**: Zustand + TanStack Query
- **UI**: Ant Design 5 + Tailwind CSS 3
- **图表**: ECharts 5

## 开发

```bash
# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev

# 构建生产版本
pnpm build

# 运行测试
pnpm test

# 代码检查
pnpm lint
```

## 目录结构

```
src/
├── routes/           # 路由定义
├── components/       # 共享组件
├── hooks/            # 自定义 Hooks
├── services/         # API 调用层
├── stores/           # Zustand 状态
├── types/            # TypeScript 类型
├── utils/            # 工具函数
├── constants/        # 常量
└── styles/           # 样式
```

## 环境变量

```bash
VITE_API_BASE_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/ws
```

## 功能模块

| 模块 | 路由 | 说明 |
|------|------|------|
| 对话界面 | /chat | SSE 流式对话、步骤可视化 |
| 审批中心 | /approval | 审批列表、详情、操作 |
| 工具管理 | /tools | 工具注册、启用/禁用 |
| 审计日志 | /audit | 查询、导出 |
| 监控面板 | /dashboard | 统计卡片、图表 |
| 用户管理 | /users | 用户 CRUD、角色管理 |
| 租户配置 | /tenant | 配额、功能开关 |
| 通知中心 | /notifications | WebSocket 实时推送 |