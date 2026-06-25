#!/bin/bash
# ============================================================
#  Agent Platform - 2GB 内存精简部署脚本
#  只部署核心服务：Gateway + Orchestrator + Model Gateway + Web
# ============================================================

set -e

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ========== 第一步：检查环境 ==========
log_info "第一步：检查环境..."

# 检查内存
TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
if [ $TOTAL_MEM -lt 1800 ]; then
    log_error "内存不足：需要至少 2GB，当前 ${TOTAL_MEM}MB"
    exit 1
fi
log_info "内存检查通过：${TOTAL_MEM}MB"

# 检查磁盘
TOTAL_DISK=$(df -m / | awk 'NR==2{print $2}')
if [ $TOTAL_DISK -lt 30000 ]; then
    log_warn "磁盘空间较小：${TOTAL_DISK}MB，建议至少 30GB"
fi

# ========== 第二步：安装依赖 ==========
log_info "第二步：安装依赖..."

# 更新系统
apt-get update -qq
apt-get install -y -qq curl git

# 安装 Docker
if ! command -v docker &> /dev/null; then
    log_info "安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 安装 Docker Compose
if ! command -v docker compose &> /dev/null; then
    log_info "安装 Docker Compose..."
    apt-get install -y -qq docker-compose-plugin
fi

log_info "依赖安装完成"

# ========== 第三步：拉取代码 ==========
log_info "第三步：拉取代码..."

cd /opt
if [ -d "agent-platform" ]; then
    cd agent-platform
    git pull
else
    git clone https://github.com/jonykchen/agent-platform.git
    cd agent-platform
fi

# ========== 第四步：配置环境变量 ==========
log_info "第四步：配置环境变量..."

if [ ! -f .env ]; then
    # 生成随机密码
    POSTGRES_PASSWORD=$(openssl rand -base64 24)
    REDIS_PASSWORD=$(openssl rand -base64 24)
    JWT_SECRET=$(openssl rand -base64 48)
    ENCRYPTION_KEY=$(openssl rand -base64 24)

    cat > .env << EOF
# ========== 数据库 ==========
POSTGRES_USER=app_user
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=agent_platform

# ========== Redis ==========
REDIS_PASSWORD=${REDIS_PASSWORD}

# ========== JWT ==========
JWT_SECRET=${JWT_SECRET}

# ========== 加密 ==========
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# ========== LLM 配置 ==========
# 请手动填入你的 API 密钥
LLM_API_KEY=你的LLM_API密钥
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_DEFAULT_MODEL=qwen-max

# ========== 环境 ==========
ENVIRONMENT=production
EOF

    log_warn "已生成 .env 文件，请编辑填入 LLM API 密钥："
    log_warn "  vim /opt/agent-platform/.env"
    log_warn "  找到 LLM_API_KEY= 填入你的密钥"
    echo ""
    read -p "按回车继续（已填入密钥）..."
fi

# ========== 第五步：创建精简版 docker-compose ==========
log_info "第五步：创建精简版配置..."

cat > /opt/agent-platform/docker-compose-2g.yml << 'COMPOSE'
# 2GB 内存精简版 - 只部署核心服务
services:
  # PostgreSQL
  postgres:
    image: pgvector/pgvector:pg16
    container_name: agent-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-app_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-agent_platform}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./shared/sql:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app_user"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 256M
    restart: unless-stopped
    networks:
      - agent-net

  # Redis
  redis:
    image: redis:7-alpine
    container_name: agent-redis
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD} --maxmemory 100mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 128M
    restart: unless-stopped
    networks:
      - agent-net

  # Gateway
  gateway:
    build:
      context: ./services/gateway-java
      dockerfile: Dockerfile
    container_name: agent-gateway
    ports:
      - "8080:8080"
    environment:
      SPRING_PROFILES_ACTIVE: prod
      SERVER_PORT: 8080
      DATABASE_URL: jdbc:postgresql://postgres:5432/${POSTGRES_DB:-agent_platform}
      DATABASE_USER: ${POSTGRES_USER:-app_user}
      DATABASE_PASSWORD: ${POSTGRES_PASSWORD}
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_PASSWORD: ${REDIS_PASSWORD}
      JWT_SECRET: ${JWT_SECRET}
      ORCHESTRATOR_GRPC_HOST: orchestrator
      ORCHESTRATOR_GRPC_PORT: 50100
      JAVA_OPTS: "-Xms64m -Xmx256m -XX:+UseSerialGC"
      LOG_LEVEL: INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8080/actuator/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 90s
    deploy:
      resources:
        limits:
          memory: 384M
    restart: unless-stopped
    networks:
      - agent-net

  # Orchestrator
  orchestrator:
    build:
      context: ./services/orchestrator-python
      dockerfile: Dockerfile
    container_name: agent-orchestrator
    ports:
      - "8001:8000"
    environment:
      ENVIRONMENT: production
      APP_PORT: 8000
      DATABASE_URL: postgresql://${POSTGRES_USER:-app_user}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-agent_platform}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      MODEL_GATEWAY_URL: http://model-gateway:8002
      JWT_SECRET: ${JWT_SECRET}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      USE_REDIS_STREAM: "true"
      USE_LOCAL_STORAGE: "true"
      LOG_LEVEL: INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    deploy:
      resources:
        limits:
          memory: 256M
    restart: unless-stopped
    networks:
      - agent-net

  # Model Gateway
  model-gateway:
    build:
      context: ./services/model-gateway-python
      dockerfile: Dockerfile
    container_name: agent-model-gateway
    ports:
      - "8002:8002"
    environment:
      ENVIRONMENT: production
      APP_PORT: 8002
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/1
      LLM_API_KEY: ${LLM_API_KEY}
      LLM_BASE_URL: ${LLM_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}
      LLM_DEFAULT_MODEL: ${LLM_DEFAULT_MODEL:-qwen-max}
      LOG_LEVEL: INFO
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    deploy:
      resources:
        limits:
          memory: 128M
    restart: unless-stopped
    networks:
      - agent-net

  # Web Frontend
  web:
    build:
      context: ./services/web-frontend
      dockerfile: Dockerfile
    container_name: agent-web
    ports:
      - "80:80"
    depends_on:
      gateway:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 32M
    restart: unless-stopped
    networks:
      - agent-net

volumes:
  postgres_data:
  redis_data:

networks:
  agent-net:
    driver: bridge
COMPOSE

# ========== 第六步：构建并启动 ==========
log_info "第六步：构建并启动服务（约 10-15 分钟）..."

cd /opt/agent-platform
docker compose -f docker-compose-2g.yml up -d --build

# ========== 第七步：等待服务就绪 ==========
log_info "第七步：等待服务就绪..."

echo -n "等待服务启动"
for i in {1..60}; do
    if curl -s http://localhost:8080/actuator/health > /dev/null 2>&1; then
        echo ""
        log_info "服务启动成功！"
        break
    fi
    echo -n "."
    sleep 5
done

# ========== 第八步：显示状态 ==========
log_info "第八步：部署状态"
echo ""
echo "=========================================="
echo "  Agent Platform 部署完成！"
echo "=========================================="
echo ""
echo "访问地址："
echo "  前端：http://$(curl -s ifconfig.me)"
echo "  API：http://$(curl -s ifconfig.me):8080"
echo ""
echo "服务列表："
docker compose -f docker-compose-2g.yml ps
echo ""
echo "内存使用："
free -h
echo ""
echo "常用命令："
echo "  查看日志：docker compose -f /opt/agent-platform/docker-compose-2g.yml logs -f"
echo "  重启服务：docker compose -f /opt/agent-platform/docker-compose-2g.yml restart"
echo "  停止服务：docker compose -f /opt/agent-platform/docker-compose-2g.yml down"
echo "=========================================="
