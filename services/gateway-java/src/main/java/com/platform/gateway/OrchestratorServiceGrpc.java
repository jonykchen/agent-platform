package com.platform.gateway;

import static io.grpc.MethodDescriptor.generateFullMethodName;

/**
 * <pre>
 * OrchestratorService - Agent 编排服务
 * </pre>
 */
@io.grpc.stub.annotations.GrpcGenerated
public final class OrchestratorServiceGrpc {

  private OrchestratorServiceGrpc() {}

  public static final java.lang.String SERVICE_NAME = "gateway.OrchestratorService";

  // Static method descriptors that strictly reflect the proto.
  private static volatile io.grpc.MethodDescriptor<com.platform.gateway.ChatRequest,
      com.platform.gateway.ChatResponse> getChatCompletionMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ChatCompletion",
      requestType = com.platform.gateway.ChatRequest.class,
      responseType = com.platform.gateway.ChatResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.gateway.ChatRequest,
      com.platform.gateway.ChatResponse> getChatCompletionMethod() {
    io.grpc.MethodDescriptor<com.platform.gateway.ChatRequest, com.platform.gateway.ChatResponse> getChatCompletionMethod;
    if ((getChatCompletionMethod = OrchestratorServiceGrpc.getChatCompletionMethod) == null) {
      synchronized (OrchestratorServiceGrpc.class) {
        if ((getChatCompletionMethod = OrchestratorServiceGrpc.getChatCompletionMethod) == null) {
          OrchestratorServiceGrpc.getChatCompletionMethod = getChatCompletionMethod =
              io.grpc.MethodDescriptor.<com.platform.gateway.ChatRequest, com.platform.gateway.ChatResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ChatCompletion"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.ChatRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.ChatResponse.getDefaultInstance()))
              .setSchemaDescriptor(new OrchestratorServiceMethodDescriptorSupplier("ChatCompletion"))
              .build();
        }
      }
    }
    return getChatCompletionMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.gateway.ChatRequest,
      com.platform.gateway.ChatStreamChunk> getStreamChatCompletionMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "StreamChatCompletion",
      requestType = com.platform.gateway.ChatRequest.class,
      responseType = com.platform.gateway.ChatStreamChunk.class,
      methodType = io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
  public static io.grpc.MethodDescriptor<com.platform.gateway.ChatRequest,
      com.platform.gateway.ChatStreamChunk> getStreamChatCompletionMethod() {
    io.grpc.MethodDescriptor<com.platform.gateway.ChatRequest, com.platform.gateway.ChatStreamChunk> getStreamChatCompletionMethod;
    if ((getStreamChatCompletionMethod = OrchestratorServiceGrpc.getStreamChatCompletionMethod) == null) {
      synchronized (OrchestratorServiceGrpc.class) {
        if ((getStreamChatCompletionMethod = OrchestratorServiceGrpc.getStreamChatCompletionMethod) == null) {
          OrchestratorServiceGrpc.getStreamChatCompletionMethod = getStreamChatCompletionMethod =
              io.grpc.MethodDescriptor.<com.platform.gateway.ChatRequest, com.platform.gateway.ChatStreamChunk>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "StreamChatCompletion"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.ChatRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.ChatStreamChunk.getDefaultInstance()))
              .setSchemaDescriptor(new OrchestratorServiceMethodDescriptorSupplier("StreamChatCompletion"))
              .build();
        }
      }
    }
    return getStreamChatCompletionMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.gateway.AgentRunRequest,
      com.platform.gateway.AgentRunResponse> getExecuteAgentMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ExecuteAgent",
      requestType = com.platform.gateway.AgentRunRequest.class,
      responseType = com.platform.gateway.AgentRunResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.gateway.AgentRunRequest,
      com.platform.gateway.AgentRunResponse> getExecuteAgentMethod() {
    io.grpc.MethodDescriptor<com.platform.gateway.AgentRunRequest, com.platform.gateway.AgentRunResponse> getExecuteAgentMethod;
    if ((getExecuteAgentMethod = OrchestratorServiceGrpc.getExecuteAgentMethod) == null) {
      synchronized (OrchestratorServiceGrpc.class) {
        if ((getExecuteAgentMethod = OrchestratorServiceGrpc.getExecuteAgentMethod) == null) {
          OrchestratorServiceGrpc.getExecuteAgentMethod = getExecuteAgentMethod =
              io.grpc.MethodDescriptor.<com.platform.gateway.AgentRunRequest, com.platform.gateway.AgentRunResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ExecuteAgent"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.AgentRunRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.AgentRunResponse.getDefaultInstance()))
              .setSchemaDescriptor(new OrchestratorServiceMethodDescriptorSupplier("ExecuteAgent"))
              .build();
        }
      }
    }
    return getExecuteAgentMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.gateway.GetSessionRequest,
      com.platform.gateway.GetSessionResponse> getGetSessionMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "GetSession",
      requestType = com.platform.gateway.GetSessionRequest.class,
      responseType = com.platform.gateway.GetSessionResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.gateway.GetSessionRequest,
      com.platform.gateway.GetSessionResponse> getGetSessionMethod() {
    io.grpc.MethodDescriptor<com.platform.gateway.GetSessionRequest, com.platform.gateway.GetSessionResponse> getGetSessionMethod;
    if ((getGetSessionMethod = OrchestratorServiceGrpc.getGetSessionMethod) == null) {
      synchronized (OrchestratorServiceGrpc.class) {
        if ((getGetSessionMethod = OrchestratorServiceGrpc.getGetSessionMethod) == null) {
          OrchestratorServiceGrpc.getGetSessionMethod = getGetSessionMethod =
              io.grpc.MethodDescriptor.<com.platform.gateway.GetSessionRequest, com.platform.gateway.GetSessionResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "GetSession"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.GetSessionRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.GetSessionResponse.getDefaultInstance()))
              .setSchemaDescriptor(new OrchestratorServiceMethodDescriptorSupplier("GetSession"))
              .build();
        }
      }
    }
    return getGetSessionMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.gateway.GetRunStatusRequest,
      com.platform.gateway.GetRunStatusResponse> getGetRunStatusMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "GetRunStatus",
      requestType = com.platform.gateway.GetRunStatusRequest.class,
      responseType = com.platform.gateway.GetRunStatusResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.gateway.GetRunStatusRequest,
      com.platform.gateway.GetRunStatusResponse> getGetRunStatusMethod() {
    io.grpc.MethodDescriptor<com.platform.gateway.GetRunStatusRequest, com.platform.gateway.GetRunStatusResponse> getGetRunStatusMethod;
    if ((getGetRunStatusMethod = OrchestratorServiceGrpc.getGetRunStatusMethod) == null) {
      synchronized (OrchestratorServiceGrpc.class) {
        if ((getGetRunStatusMethod = OrchestratorServiceGrpc.getGetRunStatusMethod) == null) {
          OrchestratorServiceGrpc.getGetRunStatusMethod = getGetRunStatusMethod =
              io.grpc.MethodDescriptor.<com.platform.gateway.GetRunStatusRequest, com.platform.gateway.GetRunStatusResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "GetRunStatus"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.GetRunStatusRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.GetRunStatusResponse.getDefaultInstance()))
              .setSchemaDescriptor(new OrchestratorServiceMethodDescriptorSupplier("GetRunStatus"))
              .build();
        }
      }
    }
    return getGetRunStatusMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.gateway.CancelRunRequest,
      com.platform.gateway.CancelRunResponse> getCancelRunMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "CancelRun",
      requestType = com.platform.gateway.CancelRunRequest.class,
      responseType = com.platform.gateway.CancelRunResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.gateway.CancelRunRequest,
      com.platform.gateway.CancelRunResponse> getCancelRunMethod() {
    io.grpc.MethodDescriptor<com.platform.gateway.CancelRunRequest, com.platform.gateway.CancelRunResponse> getCancelRunMethod;
    if ((getCancelRunMethod = OrchestratorServiceGrpc.getCancelRunMethod) == null) {
      synchronized (OrchestratorServiceGrpc.class) {
        if ((getCancelRunMethod = OrchestratorServiceGrpc.getCancelRunMethod) == null) {
          OrchestratorServiceGrpc.getCancelRunMethod = getCancelRunMethod =
              io.grpc.MethodDescriptor.<com.platform.gateway.CancelRunRequest, com.platform.gateway.CancelRunResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "CancelRun"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.CancelRunRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.gateway.CancelRunResponse.getDefaultInstance()))
              .setSchemaDescriptor(new OrchestratorServiceMethodDescriptorSupplier("CancelRun"))
              .build();
        }
      }
    }
    return getCancelRunMethod;
  }

  /**
   * Creates a new async stub that supports all call types for the service
   */
  public static OrchestratorServiceStub newStub(io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<OrchestratorServiceStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<OrchestratorServiceStub>() {
        @java.lang.Override
        public OrchestratorServiceStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new OrchestratorServiceStub(channel, callOptions);
        }
      };
    return OrchestratorServiceStub.newStub(factory, channel);
  }

  /**
   * Creates a new blocking-style stub that supports all types of calls on the service
   */
  public static OrchestratorServiceBlockingV2Stub newBlockingV2Stub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<OrchestratorServiceBlockingV2Stub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<OrchestratorServiceBlockingV2Stub>() {
        @java.lang.Override
        public OrchestratorServiceBlockingV2Stub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new OrchestratorServiceBlockingV2Stub(channel, callOptions);
        }
      };
    return OrchestratorServiceBlockingV2Stub.newStub(factory, channel);
  }

  /**
   * Creates a new blocking-style stub that supports unary and streaming output calls on the service
   */
  public static OrchestratorServiceBlockingStub newBlockingStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<OrchestratorServiceBlockingStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<OrchestratorServiceBlockingStub>() {
        @java.lang.Override
        public OrchestratorServiceBlockingStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new OrchestratorServiceBlockingStub(channel, callOptions);
        }
      };
    return OrchestratorServiceBlockingStub.newStub(factory, channel);
  }

  /**
   * Creates a new ListenableFuture-style stub that supports unary calls on the service
   */
  public static OrchestratorServiceFutureStub newFutureStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<OrchestratorServiceFutureStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<OrchestratorServiceFutureStub>() {
        @java.lang.Override
        public OrchestratorServiceFutureStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new OrchestratorServiceFutureStub(channel, callOptions);
        }
      };
    return OrchestratorServiceFutureStub.newStub(factory, channel);
  }

  /**
   * <pre>
   * OrchestratorService - Agent 编排服务
   * </pre>
   */
  public interface AsyncService {

    /**
     * <pre>
     * 对话补全 - 支持流式和非流式
     * </pre>
     */
    default void chatCompletion(com.platform.gateway.ChatRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.ChatResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getChatCompletionMethod(), responseObserver);
    }

    /**
     * <pre>
     * 流式对话补全 - SSE 格式
     * </pre>
     */
    default void streamChatCompletion(com.platform.gateway.ChatRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.ChatStreamChunk> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getStreamChatCompletionMethod(), responseObserver);
    }

    /**
     * <pre>
     * Agent 任务执行
     * </pre>
     */
    default void executeAgent(com.platform.gateway.AgentRunRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.AgentRunResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getExecuteAgentMethod(), responseObserver);
    }

    /**
     * <pre>
     * 查询会话信息
     * </pre>
     */
    default void getSession(com.platform.gateway.GetSessionRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.GetSessionResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getGetSessionMethod(), responseObserver);
    }

    /**
     * <pre>
     * 查询运行状态
     * </pre>
     */
    default void getRunStatus(com.platform.gateway.GetRunStatusRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.GetRunStatusResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getGetRunStatusMethod(), responseObserver);
    }

    /**
     * <pre>
     * 取消运行
     * </pre>
     */
    default void cancelRun(com.platform.gateway.CancelRunRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.CancelRunResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getCancelRunMethod(), responseObserver);
    }
  }

  /**
   * Base class for the server implementation of the service OrchestratorService.
   * <pre>
   * OrchestratorService - Agent 编排服务
   * </pre>
   */
  public static abstract class OrchestratorServiceImplBase
      implements io.grpc.BindableService, AsyncService {

    @java.lang.Override public final io.grpc.ServerServiceDefinition bindService() {
      return OrchestratorServiceGrpc.bindService(this);
    }
  }

  /**
   * A stub to allow clients to do asynchronous rpc calls to service OrchestratorService.
   * <pre>
   * OrchestratorService - Agent 编排服务
   * </pre>
   */
  public static final class OrchestratorServiceStub
      extends io.grpc.stub.AbstractAsyncStub<OrchestratorServiceStub> {
    private OrchestratorServiceStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected OrchestratorServiceStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new OrchestratorServiceStub(channel, callOptions);
    }

    /**
     * <pre>
     * 对话补全 - 支持流式和非流式
     * </pre>
     */
    public void chatCompletion(com.platform.gateway.ChatRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.ChatResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getChatCompletionMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 流式对话补全 - SSE 格式
     * </pre>
     */
    public void streamChatCompletion(com.platform.gateway.ChatRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.ChatStreamChunk> responseObserver) {
      io.grpc.stub.ClientCalls.asyncServerStreamingCall(
          getChannel().newCall(getStreamChatCompletionMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * Agent 任务执行
     * </pre>
     */
    public void executeAgent(com.platform.gateway.AgentRunRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.AgentRunResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getExecuteAgentMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 查询会话信息
     * </pre>
     */
    public void getSession(com.platform.gateway.GetSessionRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.GetSessionResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getGetSessionMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 查询运行状态
     * </pre>
     */
    public void getRunStatus(com.platform.gateway.GetRunStatusRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.GetRunStatusResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getGetRunStatusMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 取消运行
     * </pre>
     */
    public void cancelRun(com.platform.gateway.CancelRunRequest request,
        io.grpc.stub.StreamObserver<com.platform.gateway.CancelRunResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getCancelRunMethod(), getCallOptions()), request, responseObserver);
    }
  }

  /**
   * A stub to allow clients to do synchronous rpc calls to service OrchestratorService.
   * <pre>
   * OrchestratorService - Agent 编排服务
   * </pre>
   */
  public static final class OrchestratorServiceBlockingV2Stub
      extends io.grpc.stub.AbstractBlockingStub<OrchestratorServiceBlockingV2Stub> {
    private OrchestratorServiceBlockingV2Stub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected OrchestratorServiceBlockingV2Stub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new OrchestratorServiceBlockingV2Stub(channel, callOptions);
    }

    /**
     * <pre>
     * 对话补全 - 支持流式和非流式
     * </pre>
     */
    public com.platform.gateway.ChatResponse chatCompletion(com.platform.gateway.ChatRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getChatCompletionMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 流式对话补全 - SSE 格式
     * </pre>
     */
    @io.grpc.ExperimentalApi("https://github.com/grpc/grpc-java/issues/10918")
    public io.grpc.stub.BlockingClientCall<?, com.platform.gateway.ChatStreamChunk>
        streamChatCompletion(com.platform.gateway.ChatRequest request) {
      return io.grpc.stub.ClientCalls.blockingV2ServerStreamingCall(
          getChannel(), getStreamChatCompletionMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * Agent 任务执行
     * </pre>
     */
    public com.platform.gateway.AgentRunResponse executeAgent(com.platform.gateway.AgentRunRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getExecuteAgentMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 查询会话信息
     * </pre>
     */
    public com.platform.gateway.GetSessionResponse getSession(com.platform.gateway.GetSessionRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getGetSessionMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 查询运行状态
     * </pre>
     */
    public com.platform.gateway.GetRunStatusResponse getRunStatus(com.platform.gateway.GetRunStatusRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getGetRunStatusMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 取消运行
     * </pre>
     */
    public com.platform.gateway.CancelRunResponse cancelRun(com.platform.gateway.CancelRunRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getCancelRunMethod(), getCallOptions(), request);
    }
  }

  /**
   * A stub to allow clients to do limited synchronous rpc calls to service OrchestratorService.
   * <pre>
   * OrchestratorService - Agent 编排服务
   * </pre>
   */
  public static final class OrchestratorServiceBlockingStub
      extends io.grpc.stub.AbstractBlockingStub<OrchestratorServiceBlockingStub> {
    private OrchestratorServiceBlockingStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected OrchestratorServiceBlockingStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new OrchestratorServiceBlockingStub(channel, callOptions);
    }

    /**
     * <pre>
     * 对话补全 - 支持流式和非流式
     * </pre>
     */
    public com.platform.gateway.ChatResponse chatCompletion(com.platform.gateway.ChatRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getChatCompletionMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 流式对话补全 - SSE 格式
     * </pre>
     */
    public java.util.Iterator<com.platform.gateway.ChatStreamChunk> streamChatCompletion(
        com.platform.gateway.ChatRequest request) {
      return io.grpc.stub.ClientCalls.blockingServerStreamingCall(
          getChannel(), getStreamChatCompletionMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * Agent 任务执行
     * </pre>
     */
    public com.platform.gateway.AgentRunResponse executeAgent(com.platform.gateway.AgentRunRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getExecuteAgentMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 查询会话信息
     * </pre>
     */
    public com.platform.gateway.GetSessionResponse getSession(com.platform.gateway.GetSessionRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getGetSessionMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 查询运行状态
     * </pre>
     */
    public com.platform.gateway.GetRunStatusResponse getRunStatus(com.platform.gateway.GetRunStatusRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getGetRunStatusMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 取消运行
     * </pre>
     */
    public com.platform.gateway.CancelRunResponse cancelRun(com.platform.gateway.CancelRunRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getCancelRunMethod(), getCallOptions(), request);
    }
  }

  /**
   * A stub to allow clients to do ListenableFuture-style rpc calls to service OrchestratorService.
   * <pre>
   * OrchestratorService - Agent 编排服务
   * </pre>
   */
  public static final class OrchestratorServiceFutureStub
      extends io.grpc.stub.AbstractFutureStub<OrchestratorServiceFutureStub> {
    private OrchestratorServiceFutureStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected OrchestratorServiceFutureStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new OrchestratorServiceFutureStub(channel, callOptions);
    }

    /**
     * <pre>
     * 对话补全 - 支持流式和非流式
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.gateway.ChatResponse> chatCompletion(
        com.platform.gateway.ChatRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getChatCompletionMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * Agent 任务执行
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.gateway.AgentRunResponse> executeAgent(
        com.platform.gateway.AgentRunRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getExecuteAgentMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 查询会话信息
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.gateway.GetSessionResponse> getSession(
        com.platform.gateway.GetSessionRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getGetSessionMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 查询运行状态
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.gateway.GetRunStatusResponse> getRunStatus(
        com.platform.gateway.GetRunStatusRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getGetRunStatusMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 取消运行
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.gateway.CancelRunResponse> cancelRun(
        com.platform.gateway.CancelRunRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getCancelRunMethod(), getCallOptions()), request);
    }
  }

  private static final int METHODID_CHAT_COMPLETION = 0;
  private static final int METHODID_STREAM_CHAT_COMPLETION = 1;
  private static final int METHODID_EXECUTE_AGENT = 2;
  private static final int METHODID_GET_SESSION = 3;
  private static final int METHODID_GET_RUN_STATUS = 4;
  private static final int METHODID_CANCEL_RUN = 5;

  private static final class MethodHandlers<Req, Resp> implements
      io.grpc.stub.ServerCalls.UnaryMethod<Req, Resp>,
      io.grpc.stub.ServerCalls.ServerStreamingMethod<Req, Resp>,
      io.grpc.stub.ServerCalls.ClientStreamingMethod<Req, Resp>,
      io.grpc.stub.ServerCalls.BidiStreamingMethod<Req, Resp> {
    private final AsyncService serviceImpl;
    private final int methodId;

    MethodHandlers(AsyncService serviceImpl, int methodId) {
      this.serviceImpl = serviceImpl;
      this.methodId = methodId;
    }

    @java.lang.Override
    @java.lang.SuppressWarnings("unchecked")
    public void invoke(Req request, io.grpc.stub.StreamObserver<Resp> responseObserver) {
      switch (methodId) {
        case METHODID_CHAT_COMPLETION:
          serviceImpl.chatCompletion((com.platform.gateway.ChatRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.gateway.ChatResponse>) responseObserver);
          break;
        case METHODID_STREAM_CHAT_COMPLETION:
          serviceImpl.streamChatCompletion((com.platform.gateway.ChatRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.gateway.ChatStreamChunk>) responseObserver);
          break;
        case METHODID_EXECUTE_AGENT:
          serviceImpl.executeAgent((com.platform.gateway.AgentRunRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.gateway.AgentRunResponse>) responseObserver);
          break;
        case METHODID_GET_SESSION:
          serviceImpl.getSession((com.platform.gateway.GetSessionRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.gateway.GetSessionResponse>) responseObserver);
          break;
        case METHODID_GET_RUN_STATUS:
          serviceImpl.getRunStatus((com.platform.gateway.GetRunStatusRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.gateway.GetRunStatusResponse>) responseObserver);
          break;
        case METHODID_CANCEL_RUN:
          serviceImpl.cancelRun((com.platform.gateway.CancelRunRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.gateway.CancelRunResponse>) responseObserver);
          break;
        default:
          throw new AssertionError();
      }
    }

    @java.lang.Override
    @java.lang.SuppressWarnings("unchecked")
    public io.grpc.stub.StreamObserver<Req> invoke(
        io.grpc.stub.StreamObserver<Resp> responseObserver) {
      switch (methodId) {
        default:
          throw new AssertionError();
      }
    }
  }

  public static final io.grpc.ServerServiceDefinition bindService(AsyncService service) {
    return io.grpc.ServerServiceDefinition.builder(getServiceDescriptor())
        .addMethod(
          getChatCompletionMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.gateway.ChatRequest,
              com.platform.gateway.ChatResponse>(
                service, METHODID_CHAT_COMPLETION)))
        .addMethod(
          getStreamChatCompletionMethod(),
          io.grpc.stub.ServerCalls.asyncServerStreamingCall(
            new MethodHandlers<
              com.platform.gateway.ChatRequest,
              com.platform.gateway.ChatStreamChunk>(
                service, METHODID_STREAM_CHAT_COMPLETION)))
        .addMethod(
          getExecuteAgentMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.gateway.AgentRunRequest,
              com.platform.gateway.AgentRunResponse>(
                service, METHODID_EXECUTE_AGENT)))
        .addMethod(
          getGetSessionMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.gateway.GetSessionRequest,
              com.platform.gateway.GetSessionResponse>(
                service, METHODID_GET_SESSION)))
        .addMethod(
          getGetRunStatusMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.gateway.GetRunStatusRequest,
              com.platform.gateway.GetRunStatusResponse>(
                service, METHODID_GET_RUN_STATUS)))
        .addMethod(
          getCancelRunMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.gateway.CancelRunRequest,
              com.platform.gateway.CancelRunResponse>(
                service, METHODID_CANCEL_RUN)))
        .build();
  }

  private static abstract class OrchestratorServiceBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoFileDescriptorSupplier, io.grpc.protobuf.ProtoServiceDescriptorSupplier {
    OrchestratorServiceBaseDescriptorSupplier() {}

    @java.lang.Override
    public com.google.protobuf.Descriptors.FileDescriptor getFileDescriptor() {
      return com.platform.gateway.Orchestrator.getDescriptor();
    }

    @java.lang.Override
    public com.google.protobuf.Descriptors.ServiceDescriptor getServiceDescriptor() {
      return getFileDescriptor().findServiceByName("OrchestratorService");
    }
  }

  private static final class OrchestratorServiceFileDescriptorSupplier
      extends OrchestratorServiceBaseDescriptorSupplier {
    OrchestratorServiceFileDescriptorSupplier() {}
  }

  private static final class OrchestratorServiceMethodDescriptorSupplier
      extends OrchestratorServiceBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoMethodDescriptorSupplier {
    private final java.lang.String methodName;

    OrchestratorServiceMethodDescriptorSupplier(java.lang.String methodName) {
      this.methodName = methodName;
    }

    @java.lang.Override
    public com.google.protobuf.Descriptors.MethodDescriptor getMethodDescriptor() {
      return getServiceDescriptor().findMethodByName(methodName);
    }
  }

  private static volatile io.grpc.ServiceDescriptor serviceDescriptor;

  public static io.grpc.ServiceDescriptor getServiceDescriptor() {
    io.grpc.ServiceDescriptor result = serviceDescriptor;
    if (result == null) {
      synchronized (OrchestratorServiceGrpc.class) {
        result = serviceDescriptor;
        if (result == null) {
          serviceDescriptor = result = io.grpc.ServiceDescriptor.newBuilder(SERVICE_NAME)
              .setSchemaDescriptor(new OrchestratorServiceFileDescriptorSupplier())
              .addMethod(getChatCompletionMethod())
              .addMethod(getStreamChatCompletionMethod())
              .addMethod(getExecuteAgentMethod())
              .addMethod(getGetSessionMethod())
              .addMethod(getGetRunStatusMethod())
              .addMethod(getCancelRunMethod())
              .build();
        }
      }
    }
    return result;
  }
}
