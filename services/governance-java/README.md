# Governance Service

治理服务，整合风控规则引擎、审批流程和通知推送。

## 技术栈

- Java 21 + Spring Boot 3.2
- Drools (规则引擎)
- Kafka (异步通知)
- PostgreSQL (审批记录)

## 开发

```bash
# 编译
./mvnw package -DskipTests

# 运行
./mvnw spring-boot:run

# 测试
./mvnw test
```

## 功能模块

- **风控引擎**: 基于 Drools 的规则匹配
- **审批服务**: 多级审批流程管理
- **通知服务**: WebSocket/Kafka 消息推送
