package com.platform.gateway.dto.request;

import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 更新会话标题请求 DTO
 *
 * <p>用于修改会话的显示标题。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>PATCH /api/v1/sessions/{id}/title - 更新会话标题</li>
 * </ul>
 *
 * <p>【权限要求】只能更新自己创建的会话
 *
 * @see com.platform.gateway.controller.SessionController
 * @see com.platform.gateway.dto.response.SessionResponse
 */
@Data
public class UpdateTitleRequest {

    /**
     * 新标题
     *
     * <p>会话的新显示标题。
     *
     * <p>【验证规则】
     * <ul>
     *   <li>必填项</li>
     *   <li>最大长度 256 字符</li>
     * </ul>
     */
    @Size(max = 256, message = "标题最长256个字符")
    private String title;
}