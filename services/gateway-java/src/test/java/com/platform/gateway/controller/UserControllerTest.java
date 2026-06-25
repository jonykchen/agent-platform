package com.platform.gateway.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.gateway.dto.request.CreateUserRequest;
import com.platform.gateway.dto.request.UpdateUserRequest;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.dto.response.UserDetailResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.UserService;
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

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("UserController 测试")
class UserControllerTest {

    @Mock
    private UserService userService;

    @InjectMocks
    private UserController userController;

    private MockMvc mockMvc;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(userController).build();
        objectMapper = new ObjectMapper();
    }

    @Test
    @DisplayName("应该返回用户列表")
    void should_return_user_list() throws Exception {
        // Given
        UserDetailResponse user1 = new UserDetailResponse();
        user1.setId("user-1");
        user1.setUsername("user1");

        UserDetailResponse user2 = new UserDetailResponse();
        user2.setId("user-2");
        user2.setUsername("user2");

        PageResponse<UserDetailResponse> pageResponse = new PageResponse<>();
        pageResponse.setContent(Arrays.asList(user1, user2));
        pageResponse.setTotalElements(2);

        when(userService.listUsers(any())).thenReturn(pageResponse);

        // When & Then
        mockMvc.perform(get("/api/v1/users")
                        .param("pageNumber", "0")
                        .param("pageSize", "10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content").isArray())
                .andExpect(jsonPath("$.content.length()").value(2));
    }

    @Test
    @DisplayName("应该创建用户")
    void should_create_user() throws Exception {
        // Given
        CreateUserRequest request = new CreateUserRequest();
        request.setUsername("newuser");
        request.setEmail("newuser@example.com");
        request.setPassword("password123");

        UserDetailResponse response = new UserDetailResponse();
        response.setId("user-123");
        response.setUsername("newuser");

        when(userService.createUser(any(CreateUserRequest.class))).thenReturn(response);

        // When & Then
        mockMvc.perform(post("/api/v1/users")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value("user-123"));
    }

    @Test
    @DisplayName("应该返回用户详情")
    void should_return_user_detail() throws Exception {
        // Given
        UserDetailResponse response = new UserDetailResponse();
        response.setId("user-123");
        response.setUsername("admin");

        when(userService.getUser("user-123")).thenReturn(response);

        // When & Then
        mockMvc.perform(get("/api/v1/users/user-123"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value("user-123"));
    }

    @Test
    @DisplayName("应该返回 404 当用户不存在")
    void should_return_404_when_user_not_found() throws Exception {
        // Given
        when(userService.getUser("non-existent"))
                .thenThrow(new BusinessException(ErrorCode.NOT_FOUND, "User not found"));

        // When & Then
        mockMvc.perform(get("/api/v1/users/non-existent"))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("应该更新用户信息")
    void should_update_user() throws Exception {
        // Given
        UpdateUserRequest request = new UpdateUserRequest();
        request.setEmail("updated@example.com");

        UserDetailResponse response = new UserDetailResponse();
        response.setId("user-123");
        response.setEmail("updated@example.com");

        when(userService.updateUser("user-123", any(UpdateUserRequest.class))).thenReturn(response);

        // When & Then
        mockMvc.perform(patch("/api/v1/users/user-123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value("updated@example.com"));
    }

    @Test
    @DisplayName("应该禁用用户")
    void should_disable_user() throws Exception {
        // When & Then
        mockMvc.perform(post("/api/v1/users/user-123/disable"))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("应该启用用户")
    void should_enable_user() throws Exception {
        // When & Then
        mockMvc.perform(post("/api/v1/users/user-123/enable"))
                .andExpect(status().isOk());
    }
}
