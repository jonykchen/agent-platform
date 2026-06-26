package com.platform.model;

import static io.grpc.MethodDescriptor.generateFullMethodName;

/**
 * <pre>
 * ModelGatewayService - 模型网关服务
 * </pre>
 */
@io.grpc.stub.annotations.GrpcGenerated
public final class ModelGatewayServiceGrpc {

  private ModelGatewayServiceGrpc() {}

  public static final java.lang.String SERVICE_NAME = "model.ModelGatewayService";

  // Static method descriptors that strictly reflect the proto.
  private static volatile io.grpc.MethodDescriptor<com.platform.model.ChatRequest,
      com.platform.model.ChatResponse> getChatCompletionMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ChatCompletion",
      requestType = com.platform.model.ChatRequest.class,
      responseType = com.platform.model.ChatResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.model.ChatRequest,
      com.platform.model.ChatResponse> getChatCompletionMethod() {
    io.grpc.MethodDescriptor<com.platform.model.ChatRequest, com.platform.model.ChatResponse> getChatCompletionMethod;
    if ((getChatCompletionMethod = ModelGatewayServiceGrpc.getChatCompletionMethod) == null) {
      synchronized (ModelGatewayServiceGrpc.class) {
        if ((getChatCompletionMethod = ModelGatewayServiceGrpc.getChatCompletionMethod) == null) {
          ModelGatewayServiceGrpc.getChatCompletionMethod = getChatCompletionMethod =
              io.grpc.MethodDescriptor.<com.platform.model.ChatRequest, com.platform.model.ChatResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ChatCompletion"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.model.ChatRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.model.ChatResponse.getDefaultInstance()))
              .setSchemaDescriptor(new ModelGatewayServiceMethodDescriptorSupplier("ChatCompletion"))
              .build();
        }
      }
    }
    return getChatCompletionMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.model.ChatRequest,
      com.platform.model.ChatStreamChunk> getStreamChatCompletionMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "StreamChatCompletion",
      requestType = com.platform.model.ChatRequest.class,
      responseType = com.platform.model.ChatStreamChunk.class,
      methodType = io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
  public static io.grpc.MethodDescriptor<com.platform.model.ChatRequest,
      com.platform.model.ChatStreamChunk> getStreamChatCompletionMethod() {
    io.grpc.MethodDescriptor<com.platform.model.ChatRequest, com.platform.model.ChatStreamChunk> getStreamChatCompletionMethod;
    if ((getStreamChatCompletionMethod = ModelGatewayServiceGrpc.getStreamChatCompletionMethod) == null) {
      synchronized (ModelGatewayServiceGrpc.class) {
        if ((getStreamChatCompletionMethod = ModelGatewayServiceGrpc.getStreamChatCompletionMethod) == null) {
          ModelGatewayServiceGrpc.getStreamChatCompletionMethod = getStreamChatCompletionMethod =
              io.grpc.MethodDescriptor.<com.platform.model.ChatRequest, com.platform.model.ChatStreamChunk>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "StreamChatCompletion"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.model.ChatRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.model.ChatStreamChunk.getDefaultInstance()))
              .setSchemaDescriptor(new ModelGatewayServiceMethodDescriptorSupplier("StreamChatCompletion"))
              .build();
        }
      }
    }
    return getStreamChatCompletionMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.model.ListModelsRequest,
      com.platform.model.ListModelsResponse> getListModelsMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ListModels",
      requestType = com.platform.model.ListModelsRequest.class,
      responseType = com.platform.model.ListModelsResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.model.ListModelsRequest,
      com.platform.model.ListModelsResponse> getListModelsMethod() {
    io.grpc.MethodDescriptor<com.platform.model.ListModelsRequest, com.platform.model.ListModelsResponse> getListModelsMethod;
    if ((getListModelsMethod = ModelGatewayServiceGrpc.getListModelsMethod) == null) {
      synchronized (ModelGatewayServiceGrpc.class) {
        if ((getListModelsMethod = ModelGatewayServiceGrpc.getListModelsMethod) == null) {
          ModelGatewayServiceGrpc.getListModelsMethod = getListModelsMethod =
              io.grpc.MethodDescriptor.<com.platform.model.ListModelsRequest, com.platform.model.ListModelsResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ListModels"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.model.ListModelsRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.model.ListModelsResponse.getDefaultInstance()))
              .setSchemaDescriptor(new ModelGatewayServiceMethodDescriptorSupplier("ListModels"))
              .build();
        }
      }
    }
    return getListModelsMethod;
  }

  private static volatile io.grpc.MethodDescriptor<com.platform.model.GetTokenQuotaRequest,
      com.platform.model.GetTokenQuotaResponse> getGetTokenQuotaMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "GetTokenQuota",
      requestType = com.platform.model.GetTokenQuotaRequest.class,
      responseType = com.platform.model.GetTokenQuotaResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<com.platform.model.GetTokenQuotaRequest,
      com.platform.model.GetTokenQuotaResponse> getGetTokenQuotaMethod() {
    io.grpc.MethodDescriptor<com.platform.model.GetTokenQuotaRequest, com.platform.model.GetTokenQuotaResponse> getGetTokenQuotaMethod;
    if ((getGetTokenQuotaMethod = ModelGatewayServiceGrpc.getGetTokenQuotaMethod) == null) {
      synchronized (ModelGatewayServiceGrpc.class) {
        if ((getGetTokenQuotaMethod = ModelGatewayServiceGrpc.getGetTokenQuotaMethod) == null) {
          ModelGatewayServiceGrpc.getGetTokenQuotaMethod = getGetTokenQuotaMethod =
              io.grpc.MethodDescriptor.<com.platform.model.GetTokenQuotaRequest, com.platform.model.GetTokenQuotaResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "GetTokenQuota"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.model.GetTokenQuotaRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  com.platform.model.GetTokenQuotaResponse.getDefaultInstance()))
              .setSchemaDescriptor(new ModelGatewayServiceMethodDescriptorSupplier("GetTokenQuota"))
              .build();
        }
      }
    }
    return getGetTokenQuotaMethod;
  }

  /**
   * Creates a new async stub that supports all call types for the service
   */
  public static ModelGatewayServiceStub newStub(io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<ModelGatewayServiceStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<ModelGatewayServiceStub>() {
        @java.lang.Override
        public ModelGatewayServiceStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new ModelGatewayServiceStub(channel, callOptions);
        }
      };
    return ModelGatewayServiceStub.newStub(factory, channel);
  }

  /**
   * Creates a new blocking-style stub that supports all types of calls on the service
   */
  public static ModelGatewayServiceBlockingV2Stub newBlockingV2Stub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<ModelGatewayServiceBlockingV2Stub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<ModelGatewayServiceBlockingV2Stub>() {
        @java.lang.Override
        public ModelGatewayServiceBlockingV2Stub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new ModelGatewayServiceBlockingV2Stub(channel, callOptions);
        }
      };
    return ModelGatewayServiceBlockingV2Stub.newStub(factory, channel);
  }

  /**
   * Creates a new blocking-style stub that supports unary and streaming output calls on the service
   */
  public static ModelGatewayServiceBlockingStub newBlockingStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<ModelGatewayServiceBlockingStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<ModelGatewayServiceBlockingStub>() {
        @java.lang.Override
        public ModelGatewayServiceBlockingStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new ModelGatewayServiceBlockingStub(channel, callOptions);
        }
      };
    return ModelGatewayServiceBlockingStub.newStub(factory, channel);
  }

  /**
   * Creates a new ListenableFuture-style stub that supports unary calls on the service
   */
  public static ModelGatewayServiceFutureStub newFutureStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<ModelGatewayServiceFutureStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<ModelGatewayServiceFutureStub>() {
        @java.lang.Override
        public ModelGatewayServiceFutureStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new ModelGatewayServiceFutureStub(channel, callOptions);
        }
      };
    return ModelGatewayServiceFutureStub.newStub(factory, channel);
  }

  /**
   * <pre>
   * ModelGatewayService - 模型网关服务
   * </pre>
   */
  public interface AsyncService {

    /**
     * <pre>
     * 对话补全
     * </pre>
     */
    default void chatCompletion(com.platform.model.ChatRequest request,
        io.grpc.stub.StreamObserver<com.platform.model.ChatResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getChatCompletionMethod(), responseObserver);
    }

    /**
     * <pre>
     * 流式对话补全
     * </pre>
     */
    default void streamChatCompletion(com.platform.model.ChatRequest request,
        io.grpc.stub.StreamObserver<com.platform.model.ChatStreamChunk> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getStreamChatCompletionMethod(), responseObserver);
    }

    /**
     * <pre>
     * 模型列表查询
     * </pre>
     */
    default void listModels(com.platform.model.ListModelsRequest request,
        io.grpc.stub.StreamObserver<com.platform.model.ListModelsResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getListModelsMethod(), responseObserver);
    }

    /**
     * <pre>
     * Token 配额查询
     * </pre>
     */
    default void getTokenQuota(com.platform.model.GetTokenQuotaRequest request,
        io.grpc.stub.StreamObserver<com.platform.model.GetTokenQuotaResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getGetTokenQuotaMethod(), responseObserver);
    }
  }

  /**
   * Base class for the server implementation of the service ModelGatewayService.
   * <pre>
   * ModelGatewayService - 模型网关服务
   * </pre>
   */
  public static abstract class ModelGatewayServiceImplBase
      implements io.grpc.BindableService, AsyncService {

    @java.lang.Override public final io.grpc.ServerServiceDefinition bindService() {
      return ModelGatewayServiceGrpc.bindService(this);
    }
  }

  /**
   * A stub to allow clients to do asynchronous rpc calls to service ModelGatewayService.
   * <pre>
   * ModelGatewayService - 模型网关服务
   * </pre>
   */
  public static final class ModelGatewayServiceStub
      extends io.grpc.stub.AbstractAsyncStub<ModelGatewayServiceStub> {
    private ModelGatewayServiceStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected ModelGatewayServiceStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new ModelGatewayServiceStub(channel, callOptions);
    }

    /**
     * <pre>
     * 对话补全
     * </pre>
     */
    public void chatCompletion(com.platform.model.ChatRequest request,
        io.grpc.stub.StreamObserver<com.platform.model.ChatResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getChatCompletionMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 流式对话补全
     * </pre>
     */
    public void streamChatCompletion(com.platform.model.ChatRequest request,
        io.grpc.stub.StreamObserver<com.platform.model.ChatStreamChunk> responseObserver) {
      io.grpc.stub.ClientCalls.asyncServerStreamingCall(
          getChannel().newCall(getStreamChatCompletionMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 模型列表查询
     * </pre>
     */
    public void listModels(com.platform.model.ListModelsRequest request,
        io.grpc.stub.StreamObserver<com.platform.model.ListModelsResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getListModelsMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * Token 配额查询
     * </pre>
     */
    public void getTokenQuota(com.platform.model.GetTokenQuotaRequest request,
        io.grpc.stub.StreamObserver<com.platform.model.GetTokenQuotaResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getGetTokenQuotaMethod(), getCallOptions()), request, responseObserver);
    }
  }

  /**
   * A stub to allow clients to do synchronous rpc calls to service ModelGatewayService.
   * <pre>
   * ModelGatewayService - 模型网关服务
   * </pre>
   */
  public static final class ModelGatewayServiceBlockingV2Stub
      extends io.grpc.stub.AbstractBlockingStub<ModelGatewayServiceBlockingV2Stub> {
    private ModelGatewayServiceBlockingV2Stub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected ModelGatewayServiceBlockingV2Stub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new ModelGatewayServiceBlockingV2Stub(channel, callOptions);
    }

    /**
     * <pre>
     * 对话补全
     * </pre>
     */
    public com.platform.model.ChatResponse chatCompletion(com.platform.model.ChatRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getChatCompletionMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 流式对话补全
     * </pre>
     */
    @io.grpc.ExperimentalApi("https://github.com/grpc/grpc-java/issues/10918")
    public io.grpc.stub.BlockingClientCall<?, com.platform.model.ChatStreamChunk>
        streamChatCompletion(com.platform.model.ChatRequest request) {
      return io.grpc.stub.ClientCalls.blockingV2ServerStreamingCall(
          getChannel(), getStreamChatCompletionMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 模型列表查询
     * </pre>
     */
    public com.platform.model.ListModelsResponse listModels(com.platform.model.ListModelsRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getListModelsMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * Token 配额查询
     * </pre>
     */
    public com.platform.model.GetTokenQuotaResponse getTokenQuota(com.platform.model.GetTokenQuotaRequest request) throws io.grpc.StatusException {
      return io.grpc.stub.ClientCalls.blockingV2UnaryCall(
          getChannel(), getGetTokenQuotaMethod(), getCallOptions(), request);
    }
  }

  /**
   * A stub to allow clients to do limited synchronous rpc calls to service ModelGatewayService.
   * <pre>
   * ModelGatewayService - 模型网关服务
   * </pre>
   */
  public static final class ModelGatewayServiceBlockingStub
      extends io.grpc.stub.AbstractBlockingStub<ModelGatewayServiceBlockingStub> {
    private ModelGatewayServiceBlockingStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected ModelGatewayServiceBlockingStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new ModelGatewayServiceBlockingStub(channel, callOptions);
    }

    /**
     * <pre>
     * 对话补全
     * </pre>
     */
    public com.platform.model.ChatResponse chatCompletion(com.platform.model.ChatRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getChatCompletionMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 流式对话补全
     * </pre>
     */
    public java.util.Iterator<com.platform.model.ChatStreamChunk> streamChatCompletion(
        com.platform.model.ChatRequest request) {
      return io.grpc.stub.ClientCalls.blockingServerStreamingCall(
          getChannel(), getStreamChatCompletionMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 模型列表查询
     * </pre>
     */
    public com.platform.model.ListModelsResponse listModels(com.platform.model.ListModelsRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getListModelsMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * Token 配额查询
     * </pre>
     */
    public com.platform.model.GetTokenQuotaResponse getTokenQuota(com.platform.model.GetTokenQuotaRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getGetTokenQuotaMethod(), getCallOptions(), request);
    }
  }

  /**
   * A stub to allow clients to do ListenableFuture-style rpc calls to service ModelGatewayService.
   * <pre>
   * ModelGatewayService - 模型网关服务
   * </pre>
   */
  public static final class ModelGatewayServiceFutureStub
      extends io.grpc.stub.AbstractFutureStub<ModelGatewayServiceFutureStub> {
    private ModelGatewayServiceFutureStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected ModelGatewayServiceFutureStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new ModelGatewayServiceFutureStub(channel, callOptions);
    }

    /**
     * <pre>
     * 对话补全
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.model.ChatResponse> chatCompletion(
        com.platform.model.ChatRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getChatCompletionMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 模型列表查询
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.model.ListModelsResponse> listModels(
        com.platform.model.ListModelsRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getListModelsMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * Token 配额查询
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<com.platform.model.GetTokenQuotaResponse> getTokenQuota(
        com.platform.model.GetTokenQuotaRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getGetTokenQuotaMethod(), getCallOptions()), request);
    }
  }

  private static final int METHODID_CHAT_COMPLETION = 0;
  private static final int METHODID_STREAM_CHAT_COMPLETION = 1;
  private static final int METHODID_LIST_MODELS = 2;
  private static final int METHODID_GET_TOKEN_QUOTA = 3;

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
          serviceImpl.chatCompletion((com.platform.model.ChatRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.model.ChatResponse>) responseObserver);
          break;
        case METHODID_STREAM_CHAT_COMPLETION:
          serviceImpl.streamChatCompletion((com.platform.model.ChatRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.model.ChatStreamChunk>) responseObserver);
          break;
        case METHODID_LIST_MODELS:
          serviceImpl.listModels((com.platform.model.ListModelsRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.model.ListModelsResponse>) responseObserver);
          break;
        case METHODID_GET_TOKEN_QUOTA:
          serviceImpl.getTokenQuota((com.platform.model.GetTokenQuotaRequest) request,
              (io.grpc.stub.StreamObserver<com.platform.model.GetTokenQuotaResponse>) responseObserver);
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
              com.platform.model.ChatRequest,
              com.platform.model.ChatResponse>(
                service, METHODID_CHAT_COMPLETION)))
        .addMethod(
          getStreamChatCompletionMethod(),
          io.grpc.stub.ServerCalls.asyncServerStreamingCall(
            new MethodHandlers<
              com.platform.model.ChatRequest,
              com.platform.model.ChatStreamChunk>(
                service, METHODID_STREAM_CHAT_COMPLETION)))
        .addMethod(
          getListModelsMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.model.ListModelsRequest,
              com.platform.model.ListModelsResponse>(
                service, METHODID_LIST_MODELS)))
        .addMethod(
          getGetTokenQuotaMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              com.platform.model.GetTokenQuotaRequest,
              com.platform.model.GetTokenQuotaResponse>(
                service, METHODID_GET_TOKEN_QUOTA)))
        .build();
  }

  private static abstract class ModelGatewayServiceBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoFileDescriptorSupplier, io.grpc.protobuf.ProtoServiceDescriptorSupplier {
    ModelGatewayServiceBaseDescriptorSupplier() {}

    @java.lang.Override
    public com.google.protobuf.Descriptors.FileDescriptor getFileDescriptor() {
      return com.platform.model.ModelGateway.getDescriptor();
    }

    @java.lang.Override
    public com.google.protobuf.Descriptors.ServiceDescriptor getServiceDescriptor() {
      return getFileDescriptor().findServiceByName("ModelGatewayService");
    }
  }

  private static final class ModelGatewayServiceFileDescriptorSupplier
      extends ModelGatewayServiceBaseDescriptorSupplier {
    ModelGatewayServiceFileDescriptorSupplier() {}
  }

  private static final class ModelGatewayServiceMethodDescriptorSupplier
      extends ModelGatewayServiceBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoMethodDescriptorSupplier {
    private final java.lang.String methodName;

    ModelGatewayServiceMethodDescriptorSupplier(java.lang.String methodName) {
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
      synchronized (ModelGatewayServiceGrpc.class) {
        result = serviceDescriptor;
        if (result == null) {
          serviceDescriptor = result = io.grpc.ServiceDescriptor.newBuilder(SERVICE_NAME)
              .setSchemaDescriptor(new ModelGatewayServiceFileDescriptorSupplier())
              .addMethod(getChatCompletionMethod())
              .addMethod(getStreamChatCompletionMethod())
              .addMethod(getListModelsMethod())
              .addMethod(getGetTokenQuotaMethod())
              .build();
        }
      }
    }
    return result;
  }
}
