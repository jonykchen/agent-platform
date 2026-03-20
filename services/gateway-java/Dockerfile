# Gateway Service Dockerfile
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# 复制 JAR 文件
COPY target/gateway-java-*.jar app.jar

# 暴露端口
EXPOSE 8080

# JVM 参数
ENV JAVA_OPTS="-Xms256m -Xmx512m -XX:+UseG1GC"

# 启动命令
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
