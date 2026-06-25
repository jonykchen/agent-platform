package com.platform.gateway.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.gateway.dto.request.ChatRequest;
import com.platform.gateway.dto.response.ChatResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.FastPathService;
import com.platform.gateway.service.OrchestratorClient;
import com.platform.gateway.service.TenantContextService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("ChatController 测试")
class ChatControllerTest {

    @Mock
    private FastPathService fastPathService;

    @Mock
    private OrchestratorClient orchestratorClient;

    @Mock
    private TenantContextService tenantContextService;

    @Mock
    private ObjectMapper objectMapper;

    @InjectMocks
    private ChatController chatController;

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(chatController).build();
    }

    @Test
    @DisplayName("应该返回 400 当请求体无效")
    void should_return_400_when_request_body_is_invalid() throws Exception {
        mockMvc.perform(post("/api/v1/chat/completions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("应该返回 400 当 message 为空")
    void should_return_400_when_message_is_empty() throws Exception {
        ChatRequest request = new ChatRequest();
        request.setMessage("");

        mockMvc.perform(post("/api/v1/chat/completions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("应该返回 400 当 message 超过最大长度")
    void should_return_400_when_message_exceeds_max_length() throws Exception {
        ChatRequest request = new ChatRequest();
        // 创建超过 8000 字符的消息
        StringBuilder longMessage = new StringBuilder();
        for (int i = 0; i < 10000; i++) {
            longMessage.append("a");
        }
        request.setMessage(longMessage.toString());

        mockMvc.perform(post("/api/v1/chat/completions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }
}
