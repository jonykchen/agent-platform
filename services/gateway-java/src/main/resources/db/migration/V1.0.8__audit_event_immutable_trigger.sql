-- ============================================================
--  V1.0.8: 审计事件防删改触发器（G-SEC-03 审计不可删改）
-- ============================================================
--
-- audit_event 表记录全平台审计事件，依据安全红线 G-SEC-03，审计数据
-- 一经写入不可被修改或删除。本迁移通过 BEFORE UPDATE / BEFORE DELETE
-- 触发器在数据库层强制阻断任何 UPDATE/DELETE，即使应用层或具备表写权限
-- 的账号也无法篡改历史审计记录。
--
-- 说明：
-- - 仅允许 INSERT 与 SELECT；UPDATE/DELETE 一律抛异常
-- - 触发器在数据库层生效，绕过应用层的攻击同样被拦截
-- - 归档清理应通过具备 BYPASSRLS/superuser 的离线流程，或先临时禁用触发器，
--   严禁在线 UPDATE/DELETE
-- ============================================================

-- 阻断函数：被触发即抛出异常
CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_event is append-only: % is not allowed (G-SEC-03)', TG_OP
        USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

-- 阻断 UPDATE
DROP TRIGGER IF EXISTS trg_audit_event_no_update ON audit_event;
CREATE TRIGGER trg_audit_event_no_update
    BEFORE UPDATE ON audit_event
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_event_mutation();

-- 阻断 DELETE
DROP TRIGGER IF EXISTS trg_audit_event_no_delete ON audit_event;
CREATE TRIGGER trg_audit_event_no_delete
    BEFORE DELETE ON audit_event
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_event_mutation();

-- 阻断 TRUNCATE（语句级触发器）
DROP TRIGGER IF EXISTS trg_audit_event_no_truncate ON audit_event;
CREATE TRIGGER trg_audit_event_no_truncate
    BEFORE TRUNCATE ON audit_event
    FOR EACH STATEMENT
    EXECUTE FUNCTION prevent_audit_event_mutation();
