# ============================================================
#  Orchestrator Service - Production Dockerfile
#  多阶段构建：builder 阶段安装依赖 → runtime 阶段仅包含运行时文件
#  安全加固：非 root 用户、健康检查、最小化镜像
# ============================================================

# ---- Stage 1: Builder ----
FROM python:3.12-slim AS builder

WORKDIR /build

# 安装构建工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv 并下载 Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && \
    uv pip install --system --prefix=/install -e .

# ---- Stage 2: Runtime ----
FROM python:3.12-slim

# 安装运行时最小依赖（curl 用于健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

# 从 builder 阶段复制已安装的 Python 包
COPY --from=builder /install /usr/local

# 复制应用代码
COPY app/ app/

# 设置所有权
RUN chown -R app:app /app

# 切换到非 root 用户
USER app

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
