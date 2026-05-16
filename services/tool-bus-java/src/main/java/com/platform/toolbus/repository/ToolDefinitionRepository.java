package com.platform.toolbus.repository;

import com.platform.toolbus.entity.ToolDefinitionEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 工具定义 Repository
 *
 * <p>提供工具定义的 CRUD 操作和常用查询方法。
 *
 * <h2>核心查询方法</h2>
 * <ul>
 *   <li>{@link #findAllEnabled()} - 获取所有启用的工具</li>
 *   <li>{@link #findByNameAndVersion(String, String)} - 按名称和版本查询</li>
 *   <li>{@link #findByName(String)} - 按名称查询（返回版本列表）</li>
 *   <li>{@link #findByCategory(String)} - 按类别查询</li>
 * </ul>
 *
 * <h2>使用示例</h2>
 * <pre>{@code
 * // 获取所有启用的工具
 * List<ToolDefinitionEntity> tools = repository.findAllEnabled();
 *
 * // 获取特定版本的工具
 * Optional<ToolDefinitionEntity> tool = repository.findByNameAndVersion("query_order", "2.0");
 *
 * // 获取工具的所有版本
 * List<ToolDefinitionEntity> versions = repository.findByName("query_order");
 * }</pre>
 *
 * @see com.platform.toolbus.entity.ToolDefinitionEntity
 */
@Repository
public interface ToolDefinitionRepository extends JpaRepository<ToolDefinitionEntity, java.util.UUID> {

    /**
     * 查找所有启用的工具定义
     *
     * <p>用于加载到 ToolRegistry
     *
     * @return 启用的工具定义列表
     */
    List<ToolDefinitionEntity> findByEnabledTrue();

    /**
     * 按名称和版本查找工具定义
     *
     * <p>版本号精确匹配
     *
     * @param name    工具名称
     * @param version 版本号
     * @return 工具定义（可选）
     */
    Optional<ToolDefinitionEntity> findByNameAndVersion(String name, String version);

    /**
     * 按名称查找所有版本的工具定义
     *
     * <p>用于版本管理，获取工具的所有历史版本
     *
     * @param name 工具名称
     * @return 该工具的所有版本列表
     */
    List<ToolDefinitionEntity> findByName(String name);

    /**
     * 按类别查找工具定义
     *
     * @param category 类别（query/write/external）
     * @return 该类别的所有工具定义
     */
    List<ToolDefinitionEntity> findByCategory(String category);

    /**
     * 按类别查找启用的工具定义
     *
     * @param category 类别
     * @return 该类别启用的工具定义
     */
    List<ToolDefinitionEntity> findByCategoryAndEnabledTrue(String category);

    /**
     * 检查工具名称是否存在
     *
     * @param name 工具名称
     * @return 是否存在
     */
    boolean existsByName(String name);

    /**
     * 检查工具名称和版本是否存在
     *
     * @param name    工具名称
     * @param version 版本号
     * @return 是否存在
     */
    boolean existsByNameAndVersion(String name, String version);
}
