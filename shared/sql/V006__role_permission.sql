-- ============================================================
--  Agent Platform - RBAC 角色权限表
--  版本: V006
--  说明: 将角色→权限映射从应用硬编码迁移到数据库，支持动态权限管理。
--        Gateway 通过 RolePermissionService 加载该表（带缓存与默认值兜底）。
-- ============================================================

CREATE TABLE IF NOT EXISTS role_permission (
    id              BIGSERIAL PRIMARY KEY,
    role            VARCHAR(32) NOT NULL,
    permission      VARCHAR(64) NOT NULL,
    description     VARCHAR(256),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_role_permission UNIQUE (role, permission)
);

CREATE INDEX IF NOT EXISTS idx_role_permission_role ON role_permission(role);

COMMENT ON TABLE role_permission IS 'RBAC 角色-权限映射表（动态权限管理）';

-- 种子数据：与历史硬编码 ROLE_PERMISSIONS 一致
-- admin: 通配全部权限
INSERT INTO role_permission (role, permission, description) VALUES
    ('admin',    '*',                 '全部权限')
ON CONFLICT (role, permission) DO NOTHING;

-- operator: 对话/审批/工具执行
INSERT INTO role_permission (role, permission, description) VALUES
    ('operator', 'chat:read',         '查看对话'),
    ('operator', 'chat:write',        '发送消息'),
    ('operator', 'approval:read',     '查看审批'),
    ('operator', 'approval:approve',  '审批操作'),
    ('operator', 'tools:execute',     '执行工具')
ON CONFLICT (role, permission) DO NOTHING;

-- viewer: 只读
INSERT INTO role_permission (role, permission, description) VALUES
    ('viewer',   'chat:read',         '查看对话'),
    ('viewer',   'approval:read',     '查看审批')
ON CONFLICT (role, permission) DO NOTHING;

-- member: 默认成员（与 viewer 同级只读 + 发消息）
INSERT INTO role_permission (role, permission, description) VALUES
    ('member',   'chat:read',         '查看对话'),
    ('member',   'chat:write',        '发送消息'),
    ('member',   'approval:read',     '查看审批')
ON CONFLICT (role, permission) DO NOTHING;
