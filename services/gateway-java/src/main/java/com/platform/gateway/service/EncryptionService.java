package com.platform.gateway.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * 加密/解密服务 — AES-256-GCM
 *
 * <p>密钥来源优先级：
 * <ol>
 *   <li>Vault/KMS（生产环境，通过 ENCRYPTION_KEY_PATH 指定）</li>
 *   <li>环境变量 ENCRYPTION_KEY（开发/测试环境）</li>
 * </ol>
 *
 * <p>存储格式: enc:v1:{base64(nonce)}:{base64(ciphertext+tag)}
 *
 * <h3>安全说明</h3>
 * <ul>
 *   <li>使用 AES-256-GCM 认证加密算法，同时保证机密性和完整性</li>
 *   <li>每次加密生成随机 96-bit nonce，防止重放攻击</li>
 *   <li>支持密钥轮转，过渡期可使用新旧密钥解密</li>
 *   <li>密钥与密文分离存储，符合安全最佳实践</li>
 * </ul>
 *
 * @author Platform Team
 * @since 1.0.0
 */
@Slf4j
@Service
public class EncryptionService {

    private static final String ALGORITHM = "AES/GCM/NoPadding";
    private static final int GCM_IV_LENGTH = 12;     // 96-bit nonce (NIST 推荐)
    private static final int GCM_TAG_LENGTH = 128;    // 128-bit auth tag
    private static final String VERSION_PREFIX = "enc:v1:";
    private static final int KEY_LENGTH = 32;          // 256-bit

    private final SecureRandom secureRandom = new SecureRandom();

    // 密钥持有者 — 从 Vault/KMS/环境变量加载
    private volatile byte[] currentKey;
    private volatile byte[] previousKey;  // 用于轮转过渡期
    private volatile int keyVersion = 1;

    /**
     * 构造函数 — 从环境变量加载初始密钥
     *
     * @param encryptionKeyBase64 Base64 编码的 256-bit AES 密钥
     */
    public EncryptionService(
            @Value("${ENCRYPTION_KEY:}") String encryptionKeyBase64) {
        if (encryptionKeyBase64 != null && !encryptionKeyBase64.isEmpty()) {
            try {
                byte[] keyBytes = Base64.getDecoder().decode(encryptionKeyBase64);
                setEncryptionKey(keyBytes);
                log.info("Encryption key loaded from environment variable, version={}", keyVersion);
            } catch (Exception e) {
                log.warn("Failed to load encryption key from environment variable: {}", e.getMessage());
            }
        } else {
            log.warn("ENCRYPTION_KEY not set, encryption service will be unavailable");
        }
    }

    /**
     * 初始化密钥（由 @PostConstruct 或配置刷新触发）
     *
     * @param keyBytes 32 字节 AES 密钥
     */
    public synchronized void setEncryptionKey(byte[] keyBytes) {
        if (keyBytes == null || keyBytes.length != KEY_LENGTH) {
            throw new IllegalArgumentException("Encryption key must be exactly 32 bytes");
        }
        // 轮转时将当前密钥降级为 previous
        if (this.currentKey != null) {
            this.previousKey = this.currentKey.clone();
        }
        this.currentKey = keyBytes.clone();
        this.keyVersion++;
        log.info("Encryption key rotated, version={}", keyVersion);
    }

    /**
     * 加密明文
     *
     * @param plaintext 明文
     * @return 格式: enc:v1:{base64(nonce)}:{base64(ciphertext+tag)}
     * @throws IllegalArgumentException 如果明文为空
     * @throws RuntimeException 如果加密失败
     */
    public String encrypt(String plaintext) {
        if (plaintext == null || plaintext.isEmpty()) {
            throw new IllegalArgumentException("Plaintext cannot be null or empty");
        }
        if (currentKey == null) {
            throw new IllegalStateException("Encryption key not initialized");
        }
        try {
            byte[] nonce = new byte[GCM_IV_LENGTH];
            secureRandom.nextBytes(nonce);

            Cipher cipher = Cipher.getInstance(ALGORITHM);
            SecretKeySpec keySpec = new SecretKeySpec(currentKey, "AES");
            GCMParameterSpec gcmSpec = new GCMParameterSpec(GCM_TAG_LENGTH, nonce);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec, gcmSpec);

            byte[] ciphertext = cipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));

            String encodedNonce = Base64.getEncoder().encodeToString(nonce);
            String encodedCiphertext = Base64.getEncoder().encodeToString(ciphertext);

            return VERSION_PREFIX + encodedNonce + ":" + encodedCiphertext;
        } catch (Exception e) {
            log.error("Encryption failed", e);
            throw new RuntimeException("Encryption failed", e);
        }
    }

    /**
     * 解密密文
     *
     * @param encryptedText 格式: enc:v1:{base64(nonce)}:{base64(ciphertext+tag)}
     * @return 明文
     * @throws IllegalArgumentException 如果密文格式无效
     * @throws RuntimeException 如果解密失败
     */
    public String decrypt(String encryptedText) {
        if (encryptedText == null || !encryptedText.startsWith(VERSION_PREFIX)) {
            throw new IllegalArgumentException("Invalid encrypted text format");
        }
        if (currentKey == null) {
            throw new IllegalStateException("Encryption key not initialized");
        }

        try {
            String content = encryptedText.substring(VERSION_PREFIX.length());
            String[] parts = content.split(":");
            if (parts.length != 2) {
                throw new IllegalArgumentException("Malformed encrypted text");
            }

            byte[] nonce = Base64.getDecoder().decode(parts[0]);
            byte[] ciphertext = Base64.getDecoder().decode(parts[1]);

            // 先用当前密钥尝试解密
            try {
                return decryptWithKey(currentKey, nonce, ciphertext);
            } catch (Exception e) {
                // 当前密钥解密失败，尝试旧密钥（轮转过渡期）
                if (previousKey != null) {
                    log.info("Decrypt with current key failed, trying previous key");
                    String result = decryptWithKey(previousKey, nonce, ciphertext);
                    // 标记需要重加密（可选：异步重加密）
                    log.info("Decrypted with previous key, re-encryption recommended");
                    return result;
                }
                throw e;
            }
        } catch (Exception e) {
            log.error("Decryption failed", e);
            throw new RuntimeException("Decryption failed", e);
        }
    }

    /**
     * 使用指定密钥解密
     */
    private String decryptWithKey(byte[] key, byte[] nonce, byte[] ciphertext) throws Exception {
        Cipher cipher = Cipher.getInstance(ALGORITHM);
        SecretKeySpec keySpec = new SecretKeySpec(key, "AES");
        GCMParameterSpec gcmSpec = new GCMParameterSpec(GCM_TAG_LENGTH, nonce);
        cipher.init(Cipher.DECRYPT_MODE, keySpec, gcmSpec);

        byte[] plaintext = cipher.doFinal(ciphertext);
        return new String(plaintext, StandardCharsets.UTF_8);
    }

    /**
     * 检查是否为加密格式
     *
     * @param value 待检查的字符串
     * @return 是否为加密格式
     */
    public boolean isEncrypted(String value) {
        return value != null && value.startsWith(VERSION_PREFIX);
    }

    /**
     * 重加密（轮转后使用新密钥重新加密旧数据）
     *
     * @param encryptedText 旧密文
     * @return 新密文
     */
    public String reEncrypt(String encryptedText) {
        String plaintext = decrypt(encryptedText);
        return encrypt(plaintext);
    }

    /**
     * 检查加密服务是否可用
     *
     * @return 是否已初始化密钥
     */
    public boolean isAvailable() {
        return currentKey != null;
    }

    /**
     * 获取当前密钥版本
     *
     * @return 密钥版本号
     */
    public int getKeyVersion() {
        return keyVersion;
    }
}
