package com.platform.gateway.dto.response;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.SuperBuilder;

import java.time.Instant;

/**
 * 用户详情响应（含更多信息）
 */
@Data
@SuperBuilder
@EqualsAndHashCode(callSuper = true)
public class UserDetailResponse extends UserResponse {

    /** 最后登录IP */
    private String lastLoginIp;

    /** 登录次数 */
    private Integer loginCount;

    /** 登录失败次数 */
    private Integer failedLoginCount;

    /** 更新时间 */
    private Instant updatedAt;
}
