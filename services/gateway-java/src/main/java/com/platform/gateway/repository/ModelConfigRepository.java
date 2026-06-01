package com.platform.gateway.repository;

import com.platform.gateway.entity.ModelConfig;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 模型配置 Repository
 */
@Repository
public interface ModelConfigRepository extends JpaRepository<ModelConfig, String> {

    /**
     * 查询所有启用的模型，按 display_order 排序
     */
    List<ModelConfig> findByEnabledTrueOrderByDisplayOrderAsc();

    /**
     * 查询指定 ID 的启用模型
     */
    Optional<ModelConfig> findByIdAndEnabledTrue(String id);

    /**
     * 按提供商查询启用模型
     */
    List<ModelConfig> findByProviderAndEnabledTrueOrderByDisplayOrderAsc(String provider);
}
