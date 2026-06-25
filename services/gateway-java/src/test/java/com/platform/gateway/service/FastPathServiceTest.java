package com.platform.gateway.service;

import com.platform.gateway.dto.request.ChatRequest;
import com.platform.gateway.dto.response.ChatResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("FastPathService 测试")
class FastPathServiceTest {

    @InjectMocks
    private FastPathService fastPathService;

    private ChatRequest request;

    @BeforeEach
    void setUp() {
        request = new ChatRequest();
        request.setMessage("你好");
    }

    @Test
    @DisplayName("应该识别快速路径当消息是简单问候")
    void should_identify_fast_path_when_message_is_simple_greeting() {
        // Given
        request.setMessage("你好");

        // When
        boolean result = fastPathService.isFastPath(request);

        // Then
        assertTrue(result);
    }

    @Test
    @DisplayName("应该识别快速路径当消息是简单问候英文")
    void should_identify_fast_path_when_message_is_simple_greeting_english() {
        // Given
        request.setMessage("hello");

        // When
        boolean result = fastPathService.isFastPath(request);

        // Then
        assertTrue(result);
    }

    @Test
    @DisplayName("不应该识别快速路径当消息是复杂问题")
    void should_not_identify_fast_path_when_message_is_complex() {
        // Given
        request.setMessage("请帮我查询今天的订单状态，并生成一份报告");

        // When
        boolean result = fastPathService.isFastPath(request);

        // Then
        assertFalse(result);
    }

    @Test
    @DisplayName("不应该识别快速路径当消息包含工具调用意图")
    void should_not_identify_fast_path_when_message_contains_tool_intent() {
        // Given
        request.setMessage("帮我查询订单");

        // When
        boolean result = fastPathService.isFastPath(request);

        // Then
        assertFalse(result);
    }

    @Test
    @DisplayName("应该返回快速路径响应当消息是简单问候")
    void should_return_fast_path_response_when_message_is_simple_greeting() {
        // Given
        request.setMessage("你好");

        // When
        ChatResponse response = fastPathService.handleFastPath(request);

        // Then
        assertNotNull(response);
        assertNotNull(response.getResponse());
        assertFalse(response.getResponse().isEmpty());
    }

    @Test
    @DisplayName("应该返回快速路径响应包含正确的元数据")
    void should_return_fast_path_response_with_correct_metadata() {
        // Given
        request.setMessage("你好");

        // When
        ChatResponse response = fastPathService.handleFastPath(request);

        // Then
        assertNotNull(response);
        assertEquals("fast-path", response.getModelUsed());
        assertNotNull(response.getRequestId());
    }
}
