package com.platform.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 通用分页响应 DTO
 *
 * <p>标准的分页响应结构，包含数据列表和分页信息。
 * 用于各种列表查询接口的响应。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/users - 用户列表</li>
 *   <li>GET /api/v1/sessions - 会话列表</li>
 *   <li>其他需要分页的列表查询接口</li>
 * </ul>
 *
 * <p>【使用示例】
 * <pre>{@code
 * PageResponse<UserDetailResponse> response = PageResponse.<UserDetailResponse>builder()
 *     .items(userList)
 *     .totalCount(100L)
 *     .pageNumber(1)
 *     .totalPages(10)
 *     .hasNext(true)
 *     .build();
 * }</pre>
 *
 * @param <T> 数据项类型
 * @see com.platform.gateway.controller.UserController
 * @see com.platform.gateway.controller.SessionController
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PageResponse<T> {

    /**
     * 数据项列表
     *
     * <p>当前页的数据列表。
     */
    private List<T> items;

    /**
     * 总记录数
     *
     * <p>符合查询条件的总记录数。
     */
    private Long totalCount;

    /**
     * 当前页码
     *
     * <p>当前页码，从 1 开始。
     */
    private Integer pageNumber;

    /**
     * 总页数
     *
     * <p>总页数，根据 totalCount 和 pageSize 计算得出。
     */
    private Integer totalPages;

    /**
     * 是否有下一页
     *
     * <p>指示是否存在下一页数据。
     */
    private Boolean hasNext;
}