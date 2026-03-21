package com.platform.toolbus.permission;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 工具权限 Repository
 */
@Repository
public interface ToolPermissionRepository extends JpaRepository<ToolPermission, UUID> {

    /**
     * 根据工具名和角色名查找权限
     */
    Optional<ToolPermission> findByToolNameAndRoleName(String toolName, String roleName);

    /**
     * 根据角色名查找所有权限
     */
    List<ToolPermission> findByRoleName(String roleName);

    /**
     * 根据工具名查找所有权限
     */
    List<ToolPermission> findByToolName(String toolName);
}
