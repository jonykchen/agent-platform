-- ============================================================
-- V1.0.4__create_notifications_table.sql
-- 通知表（匹配 Notification 实体定义）
-- ============================================================

-- 创建通知表
CREATE TABLE IF NOT EXISTS notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(64) NOT NULL,
    user_id         VARCHAR(128) NOT NULL,
    type            VARCHAR(32) NOT NULL,
    title           TEXT NOT NULL,
    message         TEXT,
    read            BOOLEAN NOT NULL DEFAULT FALSE,
    priority        VARCHAR(16) DEFAULT 'normal',
    action_url      VARCHAR(512),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_notification_tenant_user ON notifications(tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_notification_user_read ON notifications(user_id, read);
CREATE INDEX IF NOT EXISTS idx_notification_created ON notifications(created_at DESC);

-- 注释
COMMENT ON TABLE notifications IS '用户通知表';
COMMENT ON COLUMN notifications.id IS '通知 ID（UUID）';
COMMENT ON COLUMN notifications.tenant_id IS '租户 ID';
COMMENT ON COLUMN notifications.user_id IS '用户 ID';
COMMENT ON COLUMN notifications.type IS '通知类型：approval/system/alert/info/error/success';
COMMENT ON COLUMN notifications.title IS '通知标题';
COMMENT ON COLUMN notifications.message IS '通知内容';
COMMENT ON COLUMN notifications.read IS '已读标记';
COMMENT ON COLUMN notifications.priority IS '优先级：low/normal/high/urgent';
COMMENT ON COLUMN notifications.action_url IS '关联跳转链接';
COMMENT ON COLUMN notifications.created_at IS '创建时间';