-- ============================================================
--  多租户 RLS 策略（Phase 4）
--  实现行级安全隔离
-- ============================================================

-- 启用 RLS
ALTER TABLE agent_session ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_step ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_task ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_document ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_chunk ENABLE ROW LEVEL SECURITY;

-- 创建租户上下文函数
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_id_param VARCHAR(64))
RETURNS VOID AS $$
BEGIN
    EXECUTE format('SET app.current_tenant = %L', tenant_id_param);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 获取当前租户 ID
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS VARCHAR(64) AS $$
BEGIN
    RETURN current_setting('app.current_tenant', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- agent_session RLS 策略
CREATE POLICY tenant_isolation_session ON agent_session
    FOR ALL TO app_user
    USING (tenant_id = current_tenant_id());

-- agent_run RLS 策略
CREATE POLICY tenant_isolation_run ON agent_run
    FOR ALL TO app_user
    USING (tenant_id = current_tenant_id());

-- agent_step RLS 策略
CREATE POLICY tenant_isolation_step ON agent_step
    FOR ALL TO app_user
    USING (tenant_id = current_tenant_id());

-- approval_task RLS 策略
CREATE POLICY tenant_isolation_approval ON approval_task
    FOR ALL TO app_user
    USING (tenant_id = current_tenant_id());

-- knowledge_document RLS 策略
CREATE POLICY tenant_isolation_kd_doc ON knowledge_document
    FOR ALL TO app_user
    USING (tenant_id = current_tenant_id());

-- knowledge_chunk RLS 策略
CREATE POLICY tenant_isolation_kd_chunk ON knowledge_chunk
    FOR ALL TO app_user
    USING (tenant_id = current_tenant_id());

-- 创建应用角色
CREATE ROLE app_user NOLOGIN;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_user;

-- 注释
COMMENT ON FUNCTION set_tenant_context IS '设置当前会话的租户上下文';
COMMENT ON FUNCTION current_tenant_id IS '获取当前租户 ID';
