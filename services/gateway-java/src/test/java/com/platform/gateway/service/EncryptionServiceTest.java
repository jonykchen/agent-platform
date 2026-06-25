package com.platform.gateway.service;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Base64;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("EncryptionService 测试")
class EncryptionServiceTest {

    private EncryptionService encryptionService;
    private String validKeyBase64;

    @BeforeEach
    void setUp() {
        // 生成一个有效的 256-bit AES 密钥
        byte[] keyBytes = new byte[32];
        for (int i = 0; i < 32; i++) {
            keyBytes[i] = (byte) i;
        }
        validKeyBase64 = Base64.getEncoder().encodeToString(keyBytes);
        encryptionService = new EncryptionService(validKeyBase64);
    }

    @Test
    @DisplayName("应该成功加密和解密明文")
    void should_encrypt_and_decrypt_plaintext_successfully() {
        // Given
        String plaintext = "Hello, World!";

        // When
        String encrypted = encryptionService.encrypt(plaintext);
        String decrypted = encryptionService.decrypt(encrypted);

        // Then
        assertNotNull(encrypted);
        assertTrue(encrypted.startsWith("enc:v1:"));
        assertEquals(plaintext, decrypted);
    }

    @Test
    @DisplayName("应该生成不同的密文当加密相同明文多次")
    void should_generate_different_ciphertext_when_encrypting_same_plaintext_multiple_times() {
        // Given
        String plaintext = "Hello, World!";

        // When
        String encrypted1 = encryptionService.encrypt(plaintext);
        String encrypted2 = encryptionService.encrypt(plaintext);

        // Then
        assertNotEquals(encrypted1, encrypted2);
        // 但两者都能正确解密
        assertEquals(plaintext, encryptionService.decrypt(encrypted1));
        assertEquals(plaintext, encryptionService.decrypt(encrypted2));
    }

    @Test
    @DisplayName("应该正确识别加密格式")
    void should_correctly_identify_encrypted_format() {
        // Given
        String plaintext = "Hello, World!";
        String encrypted = encryptionService.encrypt(plaintext);

        // When & Then
        assertTrue(encryptionService.isEncrypted(encrypted));
        assertFalse(encryptionService.isEncrypted(plaintext));
        assertFalse(encryptionService.isEncrypted(null));
        assertFalse(encryptionService.isEncrypted(""));
        assertFalse(encryptionService.isEncrypted("enc:v2:something"));
    }

    @Test
    @DisplayName("应该抛出异常当加密空字符串")
    void should_throw_exception_when_encrypting_empty_string() {
        // When & Then
        assertThrows(IllegalArgumentException.class, () -> encryptionService.encrypt(""));
        assertThrows(IllegalArgumentException.class, () -> encryptionService.encrypt(null));
    }

    @Test
    @DisplayName("应该抛出异常当解密无效格式")
    void should_throw_exception_when_decrypting_invalid_format() {
        // When & Then
        assertThrows(IllegalArgumentException.class, () -> encryptionService.decrypt("invalid"));
        assertThrows(IllegalArgumentException.class, () -> encryptionService.decrypt(null));
        assertThrows(IllegalArgumentException.class, () -> encryptionService.decrypt("enc:v1:invalid"));
    }

    @Test
    @DisplayName("应该抛出异常当密钥未初始化")
    void should_throw_exception_when_key_not_initialized() {
        // Given
        EncryptionService uninitializedService = new EncryptionService("");

        // When & Then
        assertThrows(IllegalStateException.class, () -> uninitializedService.encrypt("test"));
        assertThrows(IllegalStateException.class, () -> uninitializedService.decrypt("enc:v1:test:test"));
    }

    @Test
    @DisplayName("应该支持密钥轮转")
    void should_support_key_rotation() {
        // Given
        String plaintext = "Hello, World!";
        String encryptedWithOldKey = encryptionService.encrypt(plaintext);

        // 生成新密钥
        byte[] newKeyBytes = new byte[32];
        for (int i = 0; i < 32; i++) {
            newKeyBytes[i] = (byte) (i + 100);
        }
        String newKeyBase64 = Base64.getEncoder().encodeToString(newKeyBytes);
        EncryptionService newService = new EncryptionService(newKeyBase64);

        // When - 使用新密钥加密
        String encryptedWithNewKey = newService.encrypt(plaintext);

        // Then - 两种密文都能解密
        assertEquals(plaintext, encryptionService.decrypt(encryptedWithOldKey));
        assertEquals(plaintext, newService.decrypt(encryptedWithNewKey));
    }

    @Test
    @DisplayName("应该正确重加密数据")
    void should_correctly_re_encrypt_data() {
        // Given
        String plaintext = "Hello, World!";
        String encrypted = encryptionService.encrypt(plaintext);

        // When
        String reEncrypted = encryptionService.reEncrypt(encrypted);

        // Then
        assertNotEquals(encrypted, reEncrypted);
        assertEquals(plaintext, encryptionService.decrypt(reEncrypted));
    }

    @Test
    @DisplayName("应该报告服务可用性")
    void should_report_service_availability() {
        // Given
        EncryptionService initializedService = new EncryptionService(validKeyBase64);
        EncryptionService uninitializedService = new EncryptionService("");

        // When & Then
        assertTrue(initializedService.isAvailable());
        assertFalse(uninitializedService.isAvailable());
    }

    @Test
    @DisplayName("应该报告密钥版本")
    void should_report_key_version() {
        // Given
        EncryptionService service = new EncryptionService(validKeyBase64);

        // When & Then
        assertEquals(1, service.getKeyVersion());
    }

    @Test
    @DisplayName("应该支持 Unicode 字符")
    void should_support_unicode_characters() {
        // Given
        String plaintext = "你好，世界！🌍";

        // When
        String encrypted = encryptionService.encrypt(plaintext);
        String decrypted = encryptionService.decrypt(encrypted);

        // Then
        assertEquals(plaintext, decrypted);
    }

    @Test
    @DisplayName("应该支持长文本")
    void should_support_long_text() {
        // Given
        StringBuilder longText = new StringBuilder();
        for (int i = 0; i < 10000; i++) {
            longText.append("Hello, World! ");
        }
        String plaintext = longText.toString();

        // When
        String encrypted = encryptionService.encrypt(plaintext);
        String decrypted = encryptionService.decrypt(encrypted);

        // Then
        assertEquals(plaintext, decrypted);
    }
}
