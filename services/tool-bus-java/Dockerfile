# ============================================================
#  ToolBus Service - Production Dockerfile
#  安全加固：非 root 用户、多阶段构建、健康检查
# ============================================================

# Stage 1: Build
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /build

COPY mvnw .
COPY .mvn .mvn
COPY pom.xml .

RUN ./mvnw dependency:go-offline -B

COPY src src
RUN ./mvnw package -DskipTests -B

# Stage 2: Runtime
FROM eclipse-temurin:21-jre-alpine

# 安装 grpcurl 用于 gRPC 健康检查
RUN apk add --no-cache grpcurl

# 创建非 root 用户
RUN addgroup -S app && adduser -S app -G app

WORKDIR /app

COPY --from=builder /build/target/*.jar app.jar

RUN chown -R app:app /app

USER app

EXPOSE 50051

ENV JAVA_OPTS="-Xms128m -Xmx256m -XX:+UseG1GC"

# gRPC 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD grpcurl -plaintext localhost:50051 grpc.health.v1.Health/Check || exit 1

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
