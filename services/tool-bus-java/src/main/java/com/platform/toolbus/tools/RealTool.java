// 真实工具接口

package com.platform.toolbus.tools;

import java.util.Map;

/**
 * 真实工具接口
 */
public interface RealTool {

    String getName();

    String getCategory();

    String getRiskLevel();

    default boolean requiresApproval() {
        return "high".equals(getRiskLevel()) || "critical".equals(getRiskLevel());
    }

    String execute(Map<String, Object> arguments);
}
