package com.platform.toolbus.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 用户信息 DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UserInfo {
    private String id;
    private String name;
    private String email;
    private String phone;
    private String level;
    private String registerDate;
    private Integer totalOrders;
}
