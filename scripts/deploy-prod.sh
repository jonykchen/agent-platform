#!/bin/bash
# ============================================================
#  Agent Platform - 生产环境部署脚本
#  用法: ./scripts/deploy-prod.sh
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 日志函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    command -v docker >/dev/null 2>&1 || { log_error "Docker 未安装"; exit 1; }
    command -v docker compose >/dev/null 2>&1 || { log_error "Docker Compose 未安装"; exit 1; }
    log_info "依赖检查通过"
}

# 检查环境变量
check_env() {
    log_info "检查环境变量..."
    if [ ! -f .env.prod ]; then
        log_error ".env.prod 文件不存在"
        log_info "请复制 .env.prod.example 为 .env.prod 并填入真实值"
        exit 1
    fi

    # 检查必需的环境变量
    required_vars=(
        "POSTGRES_PASSWORD"
        "REDIS_PASSWORD"
        "MINIO_ROOT_PASSWORD"
        "JWT_SECRET"
        "ENCRYPTION_KEY"
        "LLM_API_KEY"
        "GRAFANA_ADMIN_PASSWORD"
    )

    source .env.prod
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "环境变量 $var 未设置"
            exit 1
        fi
    done

    log_info "环境变量检查通过"
}

# 生成自签名证书（开发/测试用）
generate_self_signed_cert() {
    local domain=$1
    if [ ! -f "/etc/letsencrypt/live/$domain/fullchain.pem" ]; then
        log_warn "SSL 证书不存在，生成自签名证书..."
        mkdir -p /etc/letsencrypt/live/$domain
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout /etc/letsencrypt/live/$domain/privkey.pem \
            -out /etc/letsencrypt/live/$domain/fullchain.pem \
            -subj "/CN=$domain"
        log_warn "⚠️  自签名证书仅用于测试，生产环境请使用 Let's Encrypt"
    fi
}

# 申请 Let's Encrypt 证书
setup_ssl() {
    source .env.prod
    local domain=$DOMAIN

    if [ -z "$domain" ] || [ "$domain" = "your-domain.com" ]; then
        log_warn "域名未配置，跳过 SSL 设置"
        return
    fi

    log_info "设置 SSL 证书..."

    # 安装 certbot
    if ! command -v certbot >/dev/null 2>&1; then
        log_info "安装 certbot..."
        apt-get update && apt-get install -y certbot python3-certbot-nginx
    fi

    # 申请证书
    certbot certonly --standalone \
        -d $domain \
        --email $SSL_EMAIL \
        --agree-tos \
        --no-eff-email \
        --force-renewal

    log_info "SSL 证书申请成功"
}

# 部署服务
deploy_services() {
    log_info "部署服务..."

    # 拉取最新代码
    git pull origin master

    # 构建镜像
    log_info "构建 Docker 镜像..."
    docker compose -f infra/docker-compose.prod.yml build --no-cache

    # 停止旧服务
    log_info "停止旧服务..."
    docker compose -f infra/docker-compose.prod.yml down

    # 启动新服务
    log_info "启动新服务..."
    docker compose -f infra/docker-compose.prod.yml up -d

    # 等待服务就绪
    log_info "等待服务就绪..."
    sleep 30

    # 检查服务状态
    check_services
}

# 检查服务状态
check_services() {
    log_info "检查服务状态..."

    services=(
        "postgres"
        "redis"
        "kafka"
        "gateway"
        "orchestrator"
        "model-gateway"
        "knowledge"
        "tool-bus"
        "governance"
        "web-frontend"
    )

    all_healthy=true
    for service in "${services[@]}"; do
        status=$(docker compose -f infra/docker-compose.prod.yml ps --format json $service 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4)
        if [ "$status" = "running" ]; then
            log_info "✅ $service: 运行中"
        else
            log_error "❌ $service: $status"
            all_healthy=false
        fi
    done

    if [ "$all_healthy" = true ]; then
        log_info "所有服务运行正常！"
    else
        log_error "部分服务异常，请检查日志"
        docker compose -f infra/docker-compose.prod.yml logs --tail=50
        exit 1
    fi
}

# 显示部署信息
show_info() {
    source .env.prod
    echo ""
    echo "=========================================="
    echo "  Agent Platform 部署完成！"
    echo "=========================================="
    echo ""
    echo "访问地址:"
    echo "  前端: https://$DOMAIN"
    echo "  API:  https://$DOMAIN/api/"
    echo ""
    echo "监控面板:"
    echo "  Grafana:    http://$DOMAIN:3000"
    echo "  Prometheus: http://$DOMAIN:9090"
    echo "  Jaeger:     http://$DOMAIN:16686"
    echo ""
    echo "默认账号:"
    echo "  Grafana: admin / $GRAFANA_ADMIN_PASSWORD"
    echo ""
    echo "=========================================="
}

# 主函数
main() {
    log_info "开始部署 Agent Platform..."

    check_dependencies
    check_env
    setup_ssl
    deploy_services
    show_info

    log_info "部署完成！"
}

# 执行主函数
main "$@"
