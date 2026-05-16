package com.platform.toolbus;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Tool Bus 服务启动类
 *
 * <p>Tool Bus 是 Agent 平台的工具执行总线，负责统一管理工具的注册、发现与执行。
 *
 * <h2>核心职责</h2>
 * <ul>
 *   <li>工具动态注册与管理（通过 {@link com.platform.toolbus.registry.ToolRegistry}）</li>
 *   <li>工具执行与结果返回（支持本地 Mock 和远程调用）</li>
 *   <li>与 Orchestrator 通过 gRPC 通信（端口 40051）</li>
 *   <li>高风险工具审批流程对接（与 Governance 服务交互）</li>
 * </ul>
 *
 * <h2>架构位置</h2>
 * <pre>
 * Gateway (Java) → Orchestrator (Python) → Tool Bus (Java) ← Governance (Java)
 *                                            ↓
 *                                     外部业务系统
 * </pre>
 *
 * <h2>技术选型</h2>
 * <table border="1">
 *   <tr><th>组件</th><th>版本</th><th>说明</th></tr>
 *   <tr><td>Java</td><td>21</td><td>使用虚拟线程优化批量工具执行</td></tr>
 *   <tr><td>Spring Boot</td><td>3.2.5</td><td>主流稳定版本</td></tr>
 *   <tr><td>gRPC Spring Boot Starter</td><td>3.1.0.RELEASE</td><td>gRPC 服务集成</td></tr>
 *   <tr><td>Spring Data JPA</td><td>-</td><td>工具定义持久化</td></tr>
 *   <tr><td>Spring Data Redis</td><td>-</td><td>工具执行结果缓存</td></tr>
 * </table>
 *
 * <h2>启动流程</h2>
 * <ol>
 *   <li>加载 application.yml 配置</li>
 *   <li>初始化数据库连接池（PostgreSQL）</li>
 *   <li>初始化 Redis 连接池</li>
 *   <li>启动 gRPC 服务器（端口 40051）</li>
 *   <li>启动 HTTP 服务器（端口 8083）</li>
 *   <li>从数据库加载所有已启用的工具到内存注册表</li>
 * </ol>
 *
 * <h2>配置文件</h2>
 * <p>主要配置项：
 * <ul>
 *   <li>{@code server.port}: HTTP 端口，默认 8083</li>
 *   <li>{@code grpc.server.port}: gRPC 端口，默认 40051</li>
 *   <li>{@code spring.datasource.*}: 数据库连接配置</li>
 *   <li>{@code spring.data.redis.*}: Redis 连接配置</li>
 * </ul>
 *
 * @see com.platform.toolbus.registry.ToolRegistry
 * @see com.platform.toolbus.controller.ToolAdminController
 * @see com.platform.toolbus.grpc.ToolExecutionService
 */
@SpringBootApplication
public class ToolBusApplication {

    public static void main(String[] args) {
        SpringApplication.run(ToolBusApplication.class, args);
    }
}
