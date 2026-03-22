package com.platform.gateway.repository;

import com.platform.gateway.entity.Tenant;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 租户 Repository
 */
@Repository
public interface TenantRepository extends JpaRepository<Tenant, String> {

    /**
     * 按ID和状态查询
     */
    Optional<Tenant> findByIdAndStatus(String id, String status);

    /**
     * 按状态查询（分页）
     */
    Page<Tenant> findByStatus(String status, Pageable pageable);

    /**
     * 按状态查询（列表）
     */
    List<Tenant> findByStatus(String status);

    /**
     * 检查租户是否存在
     */
    boolean existsById(String id);

    /**
     * 查询所有活跃租户
     */
    @Query("SELECT t FROM Tenant t WHERE t.status = 'active'")
    List<Tenant> findAllActive();

    /**
     * 按状态统计租户数
     */
    long countByStatus(String status);

    /**
     * 复杂查询：按条件筛选租户
     */
    @Query("SELECT t FROM Tenant t WHERE " +
           "(:status IS NULL OR t.status = :status)")
    Page<Tenant> findByConditions(
            @Param("status") String status,
            Pageable pageable);
}
