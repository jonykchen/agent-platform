package com.platform.gateway.dto.request;

import lombok.Data;

/**
 * 审批操作请求
 */
@Data
public class ApprovalActionRequest {

    /**
     * 审批意见/备注
     */
    private String comment;
}
