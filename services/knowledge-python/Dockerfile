# ============================================================
#  Knowledge Service - Production Dockerfile
#  安全加固：非 root 用户、健康检查、最小化镜像
# ============================================================

FROM python:3.12-slim

# 创建非 root 用户
RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

# 安装系统依赖（最小化）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && \
    uv pip install --system -e .

# 复制应用代码
COPY app/ app/

# 设置所有权
RUN chown -R app:app /app

# 切换到非 root 用户
USER app

EXPOSE 8081

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/api/v1/documents/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
