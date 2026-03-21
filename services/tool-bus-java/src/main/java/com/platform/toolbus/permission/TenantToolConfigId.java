package com.platform.toolbus.permission;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

/**
 * TenantToolConfig 复合主键
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class TenantToolConfigId implements Serializable {
    private String tenantId;
    private String toolName;
}
