# Gateway Service

API 网关服务，统一入口，处理鉴权、限流、租户隔离和请求追踪。

## 技术栈

- Java 21 + Spring Boot 3.2
- Spring Security + JWT
- Redis (限流、会话)

## 开发

```bash
# 编译
./mvnw package -DskipTests

# 运行
./mvnw spring-boot:run

# 测试
./mvnw test
```

## 配置

```yaml
# application.yml 关键配置
server:
  port: 8080

jwt:
  secret: ${JWT_SECRET}
  
rate-limit:
  requests-per-minute: 100
```
