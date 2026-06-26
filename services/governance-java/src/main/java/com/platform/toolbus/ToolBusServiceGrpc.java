package com.platform.toolbus;

import static io.grpc.MethodDescriptor.generateFullMethodName;

/**
 * <pre>
 * ToolBusService - 工具总线服务
 * </pre>
 */
@io.grpc.stub.annotations.GrpcGenerated
public final class ToolBusServiceGrpc {

  private ToolBusServiceGrpc() {}

  public static final java.lang.String SERVICE_NAME = "toolbus.ToolBusService";

  // Static method descriptors that strictly reflect the proto.
  private static volatile io.grpc.MethodDescriptor<com.platform.toolbus.ToolExecuteRequest,
      com.platform.toolbus.ToolExecuteResponse> getExecuteToolMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ExecuteTool",
      requestType = com.platform.toolbus.ToolExecuteRequest.class,
      responseType = com.platform.toolbus.ToolExecuteResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.toolbus.ToolExecuteRequest,
      com.platform.toolbus.ToolExecuteResponse> getExecuteToolMethod() {
    io.grpc.MethodDescriptor<com.platform.toolbus.ToolExecuteRequest, com.platform.toolbus.ToolExecuteResponse> getExecuteToolMethod;
    if ((getExecuteToolMethod = ToolBusServiceGrpc.getExecuteToolMethod) == null) {
      synchronized (ToolBusServiceGrpc.class) {
        if ((getExecuteToolMethod = ToolBusServiceGrpc.getExecuteToolMethod) == null) {
          ToolBusServiceGrpc.getExecuteToolMethod = getExecuteToolMethod =
              io.grpc.MethodDescriptor.<com.platform.toolbus.ToolExecuteRequest, com.platform.toolbus.ToolExecuteResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ExecuteTool"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.toolbus.ToolExecuteRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.toolbus.ToolExecuteResponse.getDefaultInstance()))
              .setSchemaDescriptor(new ToolBusServiceMethodDescriptorSupplier("ExecuteTool"))
              .build();
        }
      }
    }
    return getExecuteToolMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.toolbus.ToolsBatchRequest,
      com.platform.toolbus.ToolsBatchResponse> getExecuteToolsBatchMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ExecuteToolsBatch",
      requestType = com.platform.toolbus.ToolsBatchRequest.class,
      responseType = com.platform.toolbus.ToolsBatchResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.toolbus.ToolsBatchRequest,
      com.platform.toolbus.ToolsBatchResponse> getExecuteToolsBatchMethod() {
    io.grpc.MethodDescriptor<com.platform.toolbus.ToolsBatchRequest, com.platform.toolbus.ToolsBatchResponse> getExecuteToolsBatchMethod;
    if ((getExecuteToolsBatchMethod = ToolBusServiceGrpc.getExecuteToolsBatchMethod) == null) {
      synchronized (ToolBusServiceGrpc.class) {
        if ((getExecuteToolsBatchMethod = ToolBusServiceGrpc.getExecuteToolsBatchMethod) == null) {
          ToolBusServiceGrpc.getExecuteToolsBatchMethod = getExecuteToolsBatchMethod =
              io.grpc.MethodDescriptor.<com.platform.toolbus.ToolsBatchRequest, com.platform.toolbus.ToolsBatchResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ExecuteToolsBatch"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.toolbus.ToolsBatchRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.toolbus.ToolsBatchResponse.getDefaultInstance()))
              .setSchemaDescriptor(new ToolBusServiceMethodDescriptorSupplier("ExecuteToolsBatch"))
              .build();
        }
      }
    }
    return getExecuteToolsBatchMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.toolbus.ListToolsRequest,
      com.platform.toolbus.ListToolsResponse> getListToolsMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ListTools",
      requestType = com.platform.toolbus.ListToolsRequest.class,
      responseType = com.platform.toolbus.ListToolsResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.toolbus.ListToolsRequest,
      com.platform.toolbus.ListToolsResponse> getListToolsMethod() {
    io.grpc.MethodDescriptor<com.platform.toolbus.ListToolsRequest, com.platform.toolbus.ListToolsResponse> getListToolsMethod;
    if ((getListToolsMethod = ToolBusServiceGrpc.getListToolsMethod) == null) {
      synchronized (ToolBusServiceGrpc.class) {
        if ((getListToolsMethod = ToolBusServiceGrpc.getListToolsMethod) == null) {
          ToolBusServiceGrpc.getListToolsMethod = getListToolsMethod =
              io.grpc.MethodDescriptor.<com.platform.toolbus.ListToolsRequest, com.platform.toolbus.ListToolsResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ListTools"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.toolbus.ListToolsRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.toolbus.ListToolsResponse.getDefaultInstance()))
              .setSchemaDescriptor(new ToolBusServiceMethodDescriptorSupplier("ListTools"))
              .build();
        }
      }
    }
    return getListToolsMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.toolbus.GetToolInfoRequest,
      com.platform.toolbus.GetToolInfoResponse> getGetToolInfoMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "GetToolInfo",
      requestType = com.platform.toolbus.GetToolInfoRequest.class,
      responseType = com.platform.toolbus.GetToolInfoResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.toolbus.GetToolInfoRequest,
      com.platform.toolbus.GetToolInfoResponse> getGetToolInfoMethod() {
    io.grpc.MethodDescriptor<com.platform.toolbus.GetToolInfoRequest, com.platform.toolbus.GetToolInfoResponse> getGetToolInfoMethod;
    if ((getGetToolInfoMethod = ToolBusServiceGrpc.getGetToolInfoMethod) == null) {
      synchronized (ToolBusServiceGrpc.class) {
        if ((getGetToolInfoMethod = ToolBusServiceGrpc.getGetToolInfoMethod) == null) {
          ToolBusServiceGrpc.getGetToolInfoMethod = getGetToolInfoMethod =
              io.grpc.MethodDescriptor.<com.platform.toolbus.GetToolInfoRequest, com.platform.toolbus.GetToolInfoResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "GetToolInfo"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.toolbus.GetToolInfoRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.toolbus.GetToolInfoResponse.getDefaultInstance()))
              .setSchemaDescriptor(new ToolBusServiceMethodDescriptorSupplier("GetToolInfo"))
              .build();
        }
      }
    }
    return getGetToolInfoMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.toolbus.ValidateToolInputRequest,
      com.platform.toolbus.ValidateToolInputResponse> getValidateToolInputMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ValidateToolInput",
      requestType = com.platform.toolbus.ValidateToolInputRequest.class,
      responseType = com.platform.toolbus.ValidateToolInputResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.toolbus.ValidateToolInputRequest,
      com.platform.toolbus.ValidateToolInputResponse> getValidateToolInputMethod() {
    io.grpc.MethodDescriptor<com.platform.toolbus.ValidateToolInputRequest, com.platform.toolbus.ValidateToolInputResponse> getValidateToolInputMethod;
    if ((getValidateToolInputMethod = ToolBusServiceGrpc.getValidateToolInputMethod) == null) {
      synchronized (ToolBusServiceGrpc.class) {
        if ((getValidateToolInputMethod = ToolBusServiceGrpc.getValidateToolInputMethod) == null) {
          ToolBusServiceGrpc.getValidateToolInputMethod = getValidateToolInputMethod =
              io.grpc.MethodDescriptor.<com.platform.toolbus.ValidateToolInputRequest, com.platform.toolbus.ValidateToolInputResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ValidateToolInput"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.toolbus.ValidateToolInputRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.toolbus.ValidateToolInputResponse.getDefaultInstance()))
              .setSchemaDescriptor(new ToolBusServiceMethodDescriptorSupplier("ValidateToolInput"))
              .build();
        }
      }
    }
    return getValidateToolInputMethod;
  }

  /**
   * Creates a new async stub that supports all call types for the service
   */
  public static ToolBusServiceStub newStub(io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<ToolBusServiceStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<ToolBusServiceStub>() {
        @java.lang.Override
        public ToolBusServiceStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new ToolBusServiceStub(channel, callOptions);
        }
      };
    return ToolBusServiceStub.newStub(factory, channel);
  }

  /**
   * Creates a new blocking-style stub that supports all types of calls on the service
   */
  public static ToolBusServiceBlockingV2Stub newBlockingV2Stub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<ToolBusServiceBlockingV2Stub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<ToolBusServiceBlockingV2Stub>() {
        @java.lang.Override
        public ToolBusServiceBlockingV2Stub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new ToolBusServiceBlockingV2Stub(channel, callOptions);
        }
      };
    return ToolBusServiceBlockingV2Stub.newStub(factory, channel);
  }

  /**
   * Creates a new blocking-style stub that supports unary and streaming output calls on the service
   */
  public static ToolBusServiceBlockingStub newBlockingStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<ToolBusServiceBlockingStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<ToolBusServiceBlockingStub>() {
        @java.lang.Override
        public ToolBusServiceBlockingStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new ToolBusServiceBlockingStub(channel, callOptions);
        }
      };
    return ToolBusServiceBlockingStub.newStub(factory, channel);
  }

  /**
   * Creates a new ListenableFuture-style stub that supports unary calls on the service
   */
  public static ToolBusServiceFutureStub newFutureStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<ToolBusServiceFutureStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<ToolBusServiceFutureStub>() {
        @java.lang.Override
        public ToolBusServiceFutureStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new ToolBusServiceFutureStub(channel, callOptions);
        }
      };
    return ToolBusServiceFutureStub.newStub(factory, channel);
  }

  /**
   * <pre>
   * ToolBusService - 工具总线服务
   * </pre>
   */
  public interface AsyncService {

    /**
     * <pre>
     * 调用工具
     * </pre>
     */
    default void executeTool(com.platform.toolbus.ToolExecuteRequest request,
        io.grpc.stub.StreamObserver<com.platform.toolbus.ToolExecuteResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getExecuteToolMethod(), responseObserver);
    }

    /**
     * <pre>
     * 批量调用工具（并行）
     * </pre>
     */
    default void executeToolsBatch(com.platform.toolbus.ToolsBatchRequest request,
        io.grpc.stub.StreamObserver<com.platform.toolbus.ToolsBatchResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getExecuteToolsBatchMethod(), responseObserver);
    }

    /**
     * <pre>
     * 查询工具列表
     * </pre>
     */
    default void listTools(com.platform.toolbus.ListToolsRequest request,
        io.grpc.stub.StreamObserver<com.platform.toolbus.ListToolsResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getListToolsMethod(), responseObserver);
    }

    /**
     * <pre>
     * 查询工具详情
     * </pre>
     */
    default void getToolInfo(com.platform.toolbus.GetToolInfoRequest request,
        io.grpc.stub.StreamObserver<com.platform.toolbus.GetToolInfoResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getGetToolInfoMethod(), responseObserver);
    }

    /**
     * <pre>
     * 验证工具参数
     * </pre>
     */
    default void validateToolInput(com.platform.toolbus.ValidateToolInputRequest request,
        io.grpc.stub.StreamObserver<com.platform.toolbus.ValidateToolInputResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getValidateToolInputMethod(), responseObserver);
    }
  }

  /**
   * Base class for the server implementation of the service ToolBusService.
   * <pre>
   * ToolBusService - 工具总线服务
   * </pre>
   */
  public static abstract class ToolBusServiceImplBase
      implements io.grpc.BindableService, AsyncService {

    @java.lang.Override public final io.grpc.ServerServiceDefinition bindService() {
      return ToolBusServiceGrpc.bindService(this);
    }
  }

  /**
   * A stub to allow clients to do asynchronous rpc calls to service ToolBusService.
   * <pre>
   * ToolBusService - 工具总线服务
   * </pre>
   */
  public static final class ToolBusServiceStub
      extends io.grpc.stub.AbstractAsyncStub<ToolBusServiceStub> {
    private ToolBusServiceStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected ToolBusServiceStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new ToolBusServiceStub(channel, callOptions);
    }

    /**
     * <pre>
     * 调用工具
     * </pre>
     */
    public void executeTool(com.platform.toolbus.ToolExecuteRequest request,
        io.grpc.stub.StreamObserver<com.platform.toolbus.ToolExecuteResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getExecuteToolMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 批量调用工具（并行）
     * </pre>
     */
    public void executeToolsBatch(com.platform.toolbus.ToolsBatchRequest request,
        io.grpc.stub.StreamObserver<com.platform.toolbus.ToolsBatchResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getExecuteToolsBatchMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 查询工具列表
     * </pre>
     */
    public void listTools(com.platform.toolbus.ListToolsRequest request,
        io.grpc.stub.StreamObserver<com.platform.toolbus.ListToolsResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getListToolsMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 查询工具详情
     * </pre>
     */
    public void getToolInfo(com.platform.toolbus.GetToolInfoRequest request,
        io.grpc.stub.StreamObserver<com.platform.toolbus.GetToolInfoResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getGetToolInfoMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 验证工具参数
     * </pre>
     */
    public void validateToolInput(com.platform.toolbus.ValidateToolInputRequest request,
        io.grpc.stub.StreamObserver<com.platform.toolbus.ValidateToolInputResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getValidateToolInputMethod(), getCallOptions()), request, responseObserver);
    }
  }

  /**
   * A stub to allow clients to do synchronous rpc calls to service ToolBusService.
   * <pre>
   * ToolBusService - 工具总线服务
   * </pre>
   */
  public static final class ToolBusServiceBlockingV2Stub
      extends io.grpc.stub.AbstractBlockingStub<ToolBusServiceBlockingV2Stub> {
    private ToolBusServiceBlockingV2Stub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected ToolBusServiceBlockingV2Stub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new ToolBusServiceBlockingV2Stub(channel, callOptions);
    }

    /**
     * <pre>
     * 调用工具
     * </pre>
     */
    public com.platform.toolbus.ToolExecuteResponse executeTool(com.platform.toolbus.ToolExecuteRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getExecuteToolMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 批量调用工具（并行）
     * </pre>
     */
    public com.platform.toolbus.ToolsBatchResponse executeToolsBatch(com.platform.toolbus.ToolsBatchRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getExecuteToolsBatchMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 查询工具列表
     * </pre>
     */
    public com.platform.toolbus.ListToolsResponse listTools(com.platform.toolbus.ListToolsRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getListToolsMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 查询工具详情
     * </pre>
     */
    public com.platform.toolbus.GetToolInfoResponse getToolInfo(com.platform.toolbus.GetToolInfoRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getGetToolInfoMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 验证工具参数
     * </pre>
     */
    public com.platform.toolbus.ValidateToolInputResponse validateToolInput(com.platform.toolbus.ValidateToolInputRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getValidateToolInputMethod(), getCallOptions(), request);
    }
  }

  /**
   * A stub to allow clients to do limited synchronous rpc calls to service ToolBusService.
   * <pre>
   * ToolBusService - 工具总线服务
   * </pre>
   */
  public static final class ToolBusServiceBlockingStub
      extends io.grpc.stub.AbstractBlockingStub<ToolBusServiceBlockingStub> {
    private ToolBusServiceBlockingStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected ToolBusServiceBlockingStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new ToolBusServiceBlockingStub(channel, callOptions);
    }

    /**
     * <pre>
     * 调用工具
     * </pre>
     */
    public com.platform.toolbus.ToolExecuteResponse executeTool(com.platform.toolbus.ToolExecuteRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getExecuteToolMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 批量调用工具（并行）
     * </pre>
     */
    public com.platform.toolbus.ToolsBatchResponse executeToolsBatch(com.platform.toolbus.ToolsBatchRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getExecuteToolsBatchMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 查询工具列表
     * </pre>
     */
    public com.platform.toolbus.ListToolsResponse listTools(com.platform.toolbus.ListToolsRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getListToolsMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 查询工具详情
     * </pre>
     */
    public com.platform.toolbus.GetToolInfoResponse getToolInfo(com.platform.toolbus.GetToolInfoRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getGetToolInfoMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 验证工具参数
     * </pre>
     */
    public com.platform.toolbus.ValidateToolInputResponse validateToolInput(com.platform.toolbus.ValidateToolInputRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getValidateToolInputMethod(), getCallOptions(), request);
    }
  }

  /**
   * A stub to allow clients to do ListenableFuture-style rpc calls to service ToolBusService.
   * <pre>
   * ToolBusService - 工具总线服务
   * </pre>
   */
  public static final class ToolBusServiceFutureStub
      extends io.grpc.stub.AbstractFutureStub<ToolBusServiceFutureStub> {
    private ToolBusServiceFutureStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected ToolBusServiceFutureStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new ToolBusServiceFutureStub(channel, callOptions);
    }

    /**
     * <pre>
     * 调用工具
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.toolbus.ToolExecuteResponse> executeTool(
        com.platform.toolbus.ToolExecuteRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getExecuteToolMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 批量调用工具（并行）
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.toolbus.ToolsBatchResponse> executeToolsBatch(
        com.platform.toolbus.ToolsBatchRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getExecuteToolsBatchMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 查询工具列表
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.toolbus.ListToolsResponse> listTools(
        com.platform.toolbus.ListToolsRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getListToolsMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 查询工具详情
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.toolbus.GetToolInfoResponse> getToolInfo(
        com.platform.toolbus.GetToolInfoRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getGetToolInfoMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 验证工具参数
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.toolbus.ValidateToolInputResponse> validateToolInput(
        com.platform.toolbus.ValidateToolInputRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getValidateToolInputMethod(), getCallOptions()), request);
    }
  }

  private static final int METHODID_EXECUTE_TOOL = 0;
  private static final int METHODID_EXECUTE_TOOLS_BATCH = 1;
  private static final int METHODID_LIST_TOOLS = 2;
  private static final int METHODID_GET_TOOL_INFO = 3;
  private static final int METHODID_VALIDATE_TOOL_INPUT = 4;

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
        case METHODID_EXECUTE_TOOL:
          serviceImpl.executeTool((com.platform.toolbus.ToolExecuteRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.toolbus.ToolExecuteResponse>) responseObserver);
          break;
        case METHODID_EXECUTE_TOOLS_BATCH:
          serviceImpl.executeToolsBatch((com.platform.toolbus.ToolsBatchRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.toolbus.ToolsBatchResponse>) responseObserver);
          break;
        case METHODID_LIST_TOOLS:
          serviceImpl.listTools((com.platform.toolbus.ListToolsRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.toolbus.ListToolsResponse>) responseObserver);
          break;
        case METHODID_GET_TOOL_INFO:
          serviceImpl.getToolInfo((com.platform.toolbus.GetToolInfoRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.toolbus.GetToolInfoResponse>) responseObserver);
          break;
        case METHODID_VALIDATE_TOOL_INPUT:
          serviceImpl.validateToolInput((com.platform.toolbus.ValidateToolInputRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.toolbus.ValidateToolInputResponse>) responseObserver);
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
          getExecuteToolMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.toolbus.ToolExecuteRequest,
              com.platform.toolbus.ToolExecuteResponse>(
                service, METHODID_EXECUTE_TOOL)))
        .addMethod(
          getExecuteToolsBatchMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.toolbus.ToolsBatchRequest,
              com.platform.toolbus.ToolsBatchResponse>(
                service, METHODID_EXECUTE_TOOLS_BATCH)))
        .addMethod(
          getListToolsMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.toolbus.ListToolsRequest,
              com.platform.toolbus.ListToolsResponse>(
                service, METHODID_LIST_TOOLS)))
        .addMethod(
          getGetToolInfoMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.toolbus.GetToolInfoRequest,
              com.platform.toolbus.GetToolInfoResponse>(
                service, METHODID_GET_TOOL_INFO)))
        .addMethod(
          getValidateToolInputMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.toolbus.ValidateToolInputRequest,
              com.platform.toolbus.ValidateToolInputResponse>(
                service, METHODID_VALIDATE_TOOL_INPUT)))
        .build();
  }

  private static abstract class ToolBusServiceBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoFileDescriptorSupplier, io.grpc.protobuf.ProtoServiceDescriptorSupplier {
    ToolBusServiceBaseDescriptorSupplier() {}

    @java.lang.Override
    public com.google.protobuf.Descriptors.FileDescriptor getFileDescriptor() {
      return com.platform.toolbus.ToolBus.getDescriptor();
    }

    @java.lang.Override
    public com.google.protobuf.Descriptors.ServiceDescriptor getServiceDescriptor() {
      return getFileDescriptor().findServiceByName("ToolBusService");
    }
  }

  private static final class ToolBusServiceFileDescriptorSupplier
      extends ToolBusServiceBaseDescriptorSupplier {
    ToolBusServiceFileDescriptorSupplier() {}
  }

  private static final class ToolBusServiceMethodDescriptorSupplier
      extends ToolBusServiceBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoMethodDescriptorSupplier {
    private final java.lang.String methodName;

    ToolBusServiceMethodDescriptorSupplier(java.lang.String methodName) {
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
      synchronized (ToolBusServiceGrpc.class) {
        result = serviceDescriptor;
        if (result == null) {
          serviceDescriptor = result = io.grpc.ServiceDescriptor.newBuilder(SERVICE_NAME)
              .setSchemaDescriptor(new ToolBusServiceFileDescriptorSupplier())
              .addMethod(getExecuteToolMethod())
              .addMethod(getExecuteToolsBatchMethod())
              .addMethod(getListToolsMethod())
              .addMethod(getGetToolInfoMethod())
              .addMethod(getValidateToolInputMethod())
              .build();
        }
      }
    }
    return result;
  }
}
