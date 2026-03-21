package com.platform.toolbus.grpc;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.annotation.PreDestroy;
import java.io.IOException;

/**
 * gRPC 服务端配置
 */
@Slf4j
@Configuration
public class GrpcServerConfig {

    @Value("${grpc.server.port:50051}")
    private int grpcPort;

    private Server grpcServer;

    @Bean
    public Server grpcServer(ToolBusGrpcService toolBusService) throws IOException {
        this.grpcServer = ServerBuilder.forPort(grpcPort)
                .addService(toolBusService)
                .build()
                .start();

        log.info("gRPC server started on port {}", grpcPort);

        return this.grpcServer;
    }

    @PreDestroy
    public void shutdown() {
        if (grpcServer != null) {
            log.info("Shutting down gRPC server");
            grpcServer.shutdown();
        }
    }
}