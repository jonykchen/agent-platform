package com.platform.gateway.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.gateway.dto.request.CreateSessionRequest;
import com.platform.gateway.dto.request.SessionListRequest;
import com.platform.gateway.dto.request.UpdateTitleRequest;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.dto.response.SessionResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.SessionService;
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

import java.util.Arrays;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("SessionController 测试")
class SessionControllerTest {

    @Mock
    private SessionService sessionService;

    @InjectMocks
    private SessionController sessionController;

    private MockMvc mockMvc;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(sessionController).build();
        objectMapper = new ObjectMapper();
    }

    @Test
    @DisplayName("应该返回会话列表")
    void should_return_session_list() throws Exception {
        // Given
        SessionResponse session1 = new SessionResponse();
        session1.setSessionId("session-1");
        session1.setTitle("Test Session 1");

        SessionResponse session2 = new SessionResponse();
        session2.setSessionId("session-2");
        session2.setTitle("Test Session 2");

        PageResponse<SessionResponse> pageResponse = new PageResponse<>();
        pageResponse.setContent(Arrays.asList(session1, session2));
        pageResponse.setTotalElements(2);

        when(sessionService.listSessions(any(SessionListRequest.class))).thenReturn(pageResponse);

        // When & Then
        mockMvc.perform(get("/api/v1/sessions")
                        .param("pageNumber", "0")
                        .param("pageSize", "10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content").isArray())
                .andExpect(jsonPath("$.content.length()").value(2));
    }

    @Test
    @DisplayName("应该创建会话")
    void should_create_session() throws Exception {
        // Given
        CreateSessionRequest request = new CreateSessionRequest();
        request.setSessionType("chat");

        SessionResponse response = new SessionResponse();
        response.setSessionId("session-123");
        response.setTitle("New Session");

        when(sessionService.createSession(any(CreateSessionRequest.class))).thenReturn(response);

        // When & Then
        mockMvc.perform(post("/api/v1/sessions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sessionId").value("session-123"));
    }

    @Test
    @DisplayName("应该创建会话当请求体为空")
    void should_create_session_when_request_body_is_null() throws Exception {
        // Given
        SessionResponse response = new SessionResponse();
        response.setSessionId("session-123");
        response.setTitle("New Session");

        when(sessionService.createSession(any(CreateSessionRequest.class))).thenReturn(response);

        // When & Then
        mockMvc.perform(post("/api/v1/sessions")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sessionId").value("session-123"));
    }

    @Test
    @DisplayName("应该返回会话详情")
    void should_return_session_detail() throws Exception {
        // Given
        SessionResponse response = new SessionResponse();
        response.setSessionId("session-123");
        response.setTitle("Test Session");

        when(sessionService.getSession("session-123")).thenReturn(response);

        // When & Then
        mockMvc.perform(get("/api/v1/sessions/session-123"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sessionId").value("session-123"));
    }

    @Test
    @DisplayName("应该返回 404 当会话不存在")
    void should_return_404_when_session_not_found() throws Exception {
        // Given
        when(sessionService.getSession("non-existent"))
                .thenThrow(new BusinessException(ErrorCode.NOT_FOUND, "Session not found"));

        // When & Then
        mockMvc.perform(get("/api/v1/sessions/non-existent"))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("应该更新会话标题")
    void should_update_session_title() throws Exception {
        // Given
        UpdateTitleRequest request = new UpdateTitleRequest();
        request.setTitle("Updated Title");

        SessionResponse response = new SessionResponse();
        response.setSessionId("session-123");
        response.setTitle("Updated Title");

        when(sessionService.updateTitle("session-123", "Updated Title")).thenReturn(response);

        // When & Then
        mockMvc.perform(put("/api/v1/sessions/session-123/title")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.title").value("Updated Title"));
    }

    @Test
    @DisplayName("应该删除会话")
    void should_delete_session() throws Exception {
        // When & Then
        mockMvc.perform(delete("/api/v1/sessions/session-123"))
                .andExpect(status().isNoContent());
    }
}
