# Tool Bus Service

工具总线服务，管理工具注册、权限校验和执行代理。

## 技术栈

- Java 21 + Spring Boot 3.2
- gRPC (与 Orchestrator 通信)
- PostgreSQL (工具元数据)

## 开发

```bash
# 编译
./mvnw package -DskipTests

# 运行
./mvnw spring-boot:run

# 测试
./mvnw test
```

## 工具注册

工具通过数据库表 `tool_registry` 注册，支持动态加载。
