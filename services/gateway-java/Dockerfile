# ============================================================
#  Gateway Service - Production Dockerfile
#  安全加固：非 root 用户、多阶段构建、健康检查
# ============================================================

# Stage 1: Build (多阶段构建减小镜像体积)
FROM maven:3.9-eclipse-temurin-21-alpine AS builder

WORKDIR /build

# 复制 pom.xml（利用 Docker 缓存）
COPY pom.xml .

# 下载依赖
RUN mvn dependency:go-offline -B

# 复制源码
COPY src src
RUN mvn package -DskipTests -Dcheckstyle.skip=true -Dspotbugs.skip=true -B

# Stage 2: Runtime
FROM eclipse-temurin:21-jre-alpine

# 安装 wget 用于健康检查
RUN apk add --no-cache wget

# 创建非 root 用户
RUN addgroup -S app && adduser -S app -G app

WORKDIR /app

# 从构建阶段复制 JAR
COPY --from=builder /build/target/*.jar app.jar

# 设置所有权
RUN chown -R app:app /app

# 切换到非 root 用户
USER app

EXPOSE 8080

# JVM 参数（生产优化）
ENV JAVA_OPTS="-Xms256m -Xmx512m -XX:+UseG1GC -XX:MaxGCPauseMillis=200 -XX:+UseStringDeduplication"

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -q --spider http://localhost:8080/actuator/health || exit 1

# 启动命令
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
