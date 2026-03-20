package com.platform.gateway.util;

import org.slf4j.MDC;

import java.security.SecureRandom;
import java.time.Instant;

/**
 * Request ID 生成器 - UUID v7
 * 全链路唯一 ID，贯穿所有服务
 */
public class RequestIdGenerator {

    private static final String REQUEST_ID_KEY = "request_id";
    private static final SecureRandom RANDOM = new SecureRandom();

    /**
     * 生成 UUID v7 格式的 request_id
     * 格式: 时间戳(48位) + 随机数(74位) + 变体(2位) + 版本(4位)
     */
    public static String generate() {
        long timestamp = Instant.now().toEpochMilli();

        // 生成随机部分
        long randomA = RANDOM.nextLong() & 0xFFFFFFFFFFFFL;  // 48 bits
        long randomB = RANDOM.nextLong() & 0x3FFFFFFFFFFFFFFFL;  // 62 bits

        // UUID v7 结构
        long timeHigh = (timestamp >> 16) & 0xFFFFFFFFL;
        long timeMid = timestamp & 0xFFFFL;
        long timeLowAndVersion = ((timestamp & 0xFFF0L) << 4) | 0x7;  // version 7
        long clockSeqHiAndRes = (randomA >> 8) & 0x3FL | 0x80L;  // variant
        long clockSeqLow = randomA & 0xFFL;

        // 格式化为 UUID 字串
        return String.format("%08x-%04x-%04x-%02x%02x-%012x",
                timeHigh,
                timeMid,
                timeLowAndVersion,
                clockSeqHiAndRes,
                clockSeqLow,
                randomB);
    }

    /**
     * 设置当前请求的 request_id 到 MDC
     */
    public static void setCurrent(String requestId) {
        MDC.put(REQUEST_ID_KEY, requestId);
    }

    /**
     * 获取当前请求的 request_id
     */
    public static String getCurrent() {
        return MDC.get(REQUEST_ID_KEY);
    }

    /**
     * 清除当前请求的 request_id
     */
    public static void clear() {
        MDC.remove(REQUEST_ID_KEY);
    }
}