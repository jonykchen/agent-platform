# Governance Service Dockerfile
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

COPY target/governance-java-*.jar app.jar

EXPOSE 8082

ENV JAVA_OPTS="-Xms128m -Xmx256m -XX:+UseG1GC"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
