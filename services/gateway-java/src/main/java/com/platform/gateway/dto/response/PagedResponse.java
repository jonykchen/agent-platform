package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * 分页响应包装
 *
 * @param <T> 数据项类型
 */
@Data
@Builder
public class PagedResponse<T> {

    /**
     * 数据列表
     */
    private List<T> items;

    /**
     * 总数量
     */
    private Long total;

    /**
     * 当前页码
     */
    private Integer page;

    /**
     * 每页大小
     */
    private Integer page_size;

    /**
     * 总页数
     */
    private Integer total_pages;
}
