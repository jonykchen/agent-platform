package com.platform.gateway.repository;

import com.platform.gateway.entity.RolePermission;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 角色-权限映射仓库
 */
@Repository
public interface RolePermissionRepository extends JpaRepository<RolePermission, Long> {

    /** 查询某角色的全部权限 */
    List<RolePermission> findByRole(String role);
}
