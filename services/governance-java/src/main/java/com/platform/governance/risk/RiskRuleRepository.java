package com.platform.governance.risk;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 风险规则 Repository
 */
@Repository
public interface RiskRuleRepository extends JpaRepository<RiskRule, Long> {

    /**
     * 查询启用的规则
     */
    List<RiskRule> findByEnabledTrueOrderByPriorityDesc();

    /**
     * 查询指定类型的规则
     */
    List<RiskRule> findByRuleTypeAndEnabledTrue(String ruleType);

    /**
     * 查询指定名称的规则
     */
    Optional<RiskRule> findByName(String name);

    /**
     * 查询匹配租户的规则
     */
    List<RiskRule> findByTenantIdAndEnabledTrueOrderByPriorityDesc(String tenantId);
}