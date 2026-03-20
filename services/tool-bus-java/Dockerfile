# ToolBus Service Dockerfile
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

COPY target/tool-bus-java-*.jar app.jar

EXPOSE 50051

ENV JAVA_OPTS="-Xms128m -Xmx256m -XX:+UseG1GC"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
