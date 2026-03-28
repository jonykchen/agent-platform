package com.platform.gateway.entity;

/**
 * API Key 类型枚举
 */
public enum ApiKeyType {
    /**
     * 服务间调用（内部服务）
     */
    SERVICE("svc_"),

    /**
     * 外部系统集成
     */
    EXTERNAL("ext_"),

    /**
     * 测试环境
     */
    TEST("test_");

    private final String prefix;

    ApiKeyType(String prefix) {
        this.prefix = prefix;
    }

    public String getPrefix() {
        return prefix;
    }

    /**
     * 根据前缀推断类型
     */
    public static ApiKeyType fromPrefix(String key) {
        if (key == null || key.isEmpty()) {
            return null;
        }
        if (key.startsWith("svc_")) {
            return SERVICE;
        }
        if (key.startsWith("ext_")) {
            return EXTERNAL;
        }
        if (key.startsWith("test_")) {
            return TEST;
        }
        return null;
    }
}
