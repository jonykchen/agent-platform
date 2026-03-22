package com.platform.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 通用分页响应
 *
 * @param <T> 数据项类型
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PageResponse<T> {

    /**
     * 数据项列表
     */
    private List<T> items;

    /**
     * 总记录数
     */
    private Long totalCount;

    /**
     * 当前页码（从1开始）
     */
    private Integer pageNumber;

    /**
     * 总页数
     */
    private Integer totalPages;

    /**
     * 是否有下一页
     */
    private Boolean hasNext;
}