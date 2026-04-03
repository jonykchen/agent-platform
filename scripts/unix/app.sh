#!/usr/bin/env bash
# ============================================================
#  Agent Platform - Python 应用服务管理
#  用法: ./scripts/unix/app.sh [操作]
# ============================================================

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Python 服务配置
declare -A SERVICES=(
    ["orchestrator"]="8001:services/orchestrator-python"
    ["model-gateway"]="8002:services/model-gateway-python"
    ["knowledge"]="8003:services/knowledge-python"
)

SERVICE_ORDER=("orchestrator" "model-gateway" "knowledge")

# 目录配置
LOG_DIR="$PROJECT_ROOT/logs"
PID_DIR="$PROJECT_ROOT/logs"

# 确保目录存在
mkdir -p "$LOG_DIR" "$PID_DIR"

# 打印函数
print_status() { printf "${GREEN}[OK]${NC} %s\n" "$1"; }
print_warn()   { printf "${YELLOW}[*]${NC} %s\n" "$1"; }
print_error()  { printf "${RED}[X]${NC} %s\n" "$1"; }
print_info()   { printf "${CYAN}[i]${NC} %s\n" "$1"; }

# 显示菜单
show_menu() {
    clear
    printf "\n"
    printf "${BLUE}============================================================${NC}\n"
    printf "${BLUE} Agent Platform - Python 应用服务管理${NC}\n"
    printf "${BLUE}============================================================${NC}\n"
    printf "\n"
    printf " === 可用操作 ===\n\n"
    printf "   [1]  启动所有服务    - 启动 orchestrator/model-gateway/knowledge\n"
    printf "   [2]  停止所有服务    - 停止所有 Python 服务\n"
    printf "   [3]  查看服务状态    - 检查服务运行状态和端口\n"
    printf "   [4]  查看日志        - 实时查看服务日志\n"
    printf "   [5]  重启所有服务    - 停止后重新启动\n"
    printf "   [0]  退出\n\n"
}

# 检查基础设施是否就绪
check_infrastructure() {
    print_info "检查基础设施..."

    local pg_ready=false
    local redis_ready=false

    # 检查 PostgreSQL
    if command -v nc &>/dev/null; then
        if nc -z localhost 5432 2>/dev/null; then
            pg_ready=true
        fi
    elif command -v bash &>/dev/null; then
        if (echo > /dev/tcp/localhost/5432) 2>/dev/null; then
            pg_ready=true
        fi
    fi

    # 检查 Redis
    if command -v nc &>/dev/null; then
        if nc -z localhost 6379 2>/dev/null; then
            redis_ready=true
        fi
    elif command -v bash &>/dev/null; then
        if (echo > /dev/tcp/localhost/6379) 2>/dev/null; then
            redis_ready=true
        fi
    fi

    if [ "$pg_ready" = false ]; then
        print_error "PostgreSQL 未运行 (端口 5432)"
        echo "  请先运行: ./scripts/unix/dev.sh up"
        return 1
    fi

    if [ "$redis_ready" = false ]; then
        print_error "Redis 未运行 (端口 6379)"
        echo "  请先运行: ./scripts/unix/dev.sh up"
        return 1
    fi

    print_status "基础设施就绪"
    return 0
}

# 启动单个服务
start_service() {
    local name="$1"
    local config="${SERVICES[$name]}"
    local port="${config%%:*}"
    local path="${config#*:}"

    local service_path="$PROJECT_ROOT/$path"
    local pid_file="$PID_DIR/$name.pid"
    local log_file="$LOG_DIR/$name.log"
    local err_file="$LOG_DIR/$name.err.log"

    # 检查是否已运行
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            print_warn "$name 已在运行 (PID: $pid)"
            return 0
        fi
        rm -f "$pid_file"
    fi

    # 检查端口是否被占用
    if command -v nc &>/dev/null && nc -z localhost "$port" 2>/dev/null; then
        print_error "$name 端口 $port 已被占用"
        return 1
    fi

    print_info "启动 $name (端口 $port)..."

    cd "$service_path"

    # 启动服务
    nohup uv run uvicorn app.main:app --host 0.0.0.0 --port "$port" \
        > "$log_file" 2> "$err_file" &

    local pid=$!
    echo "$pid" > "$pid_file"

    cd "$PROJECT_ROOT"

    # 等待启动
    sleep 0.5

    if kill -0 "$pid" 2>/dev/null; then
        print_status "$name 启动成功 (PID: $pid)"
        return 0
    else
        print_error "$name 启动失败，查看日志: $log_file"
        return 1
    fi
}

# 停止单个服务
stop_service() {
    local name="$1"
    local pid_file="$PID_DIR/$name.pid"

    if [ ! -f "$pid_file" ]; then
        print_warn "$name 未运行"
        return 0
    fi

    local pid=$(cat "$pid_file" 2>/dev/null || echo "")
    if [ -z "$pid" ]; then
        rm -f "$pid_file"
        print_warn "$name 未运行"
        return 0
    fi

    if kill -0 "$pid" 2>/dev/null; then
        print_info "停止 $name (PID: $pid)..."
        kill "$pid" 2>/dev/null || true

        # 等待进程结束
        local count=0
        while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
            sleep 0.5
            count=$((count + 1))
        done

        # 强制杀死
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi

        print_status "$name 已停止"
    else
        print_warn "$name 进程已不存在"
    fi

    rm -f "$pid_file"
}

# 查看服务状态
get_status() {
    printf "\n${BLUE}=== 服务状态 ===${NC}\n\n"

    local all_stopped=true

    for name in "${SERVICE_ORDER[@]}"; do
        local config="${SERVICES[$name]}"
        local port="${config%%:*}"
        local pid_file="$PID_DIR/$name.pid"

        local status="未运行"
        local pid="-"

        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                status="运行中"
                all_stopped=false
            else
                pid="-"
            fi
        fi

        # 检查端口
        local port_status="空闲"
        if command -v nc &>/dev/null && nc -z localhost "$port" 2>/dev/null; then
            port_status="监听"
        fi

        local status_color=$GREEN
        [ "$status" = "未运行" ] && status_color=$YELLOW

        printf "  %s [PID: %s] 端口: %s (%s) - " "$name" "$pid" "$port" "$port_status"
        printf "${status_color}%s${NC}\n" "$status"
    done

    printf "\n"

    if [ "$all_stopped" = true ]; then
        print_info "日志目录: $LOG_DIR"
    fi
}

# 启动所有服务
start_all() {
    printf "\n${BLUE}=== 启动所有 Python 服务 ===${NC}\n\n"

    if ! check_infrastructure; then
        return 1
    fi

    local failed=()

    for name in "${SERVICE_ORDER[@]}"; do
        if ! start_service "$name"; then
            failed+=("$name")
        fi
    done

    printf "\n"

    if [ ${#failed[@]} -eq 0 ]; then
        print_status "所有服务启动成功"
        printf "\n"
        echo -e "${GREEN}服务地址:${NC}"
        for name in "${SERVICE_ORDER[@]}"; do
            local config="${SERVICES[$name]}"
            local port="${config%%:*}"
            printf "  http://localhost:%s (%s)\n" "$port" "$name"
        done
        printf "\n"
        echo -e "${GREEN}API 文档:${NC}"
        echo "  http://localhost:8001/docs (orchestrator)"
        echo "  http://localhost:8002/docs (model-gateway)"
        echo "  http://localhost:8003/docs (knowledge)"
    else
        print_error "以下服务启动失败: ${failed[*]}"
        echo "  查看日志: tail -f $LOG_DIR/*.log"
    fi
}

# 停止所有服务
stop_all() {
    printf "\n${BLUE}=== 停止所有 Python 服务 ===${NC}\n\n"

    for name in "${SERVICE_ORDER[@]}"; do
        stop_service "$name"
    done

    printf "\n"
    print_status "所有服务已停止"
}

# 查看日志
watch_logs() {
    printf "\n${BLUE}=== 查看日志 ===${NC}\n\n"

    echo -e "${CYAN}日志文件:${NC}"
    for name in "${SERVICE_ORDER[@]}"; do
        printf "  %s/%s.log\n" "$LOG_DIR" "$name"
    done
    printf "\n"
    echo -e "${CYAN}实时查看日志 (Ctrl+C 退出):${NC}"
    echo "  tail -f $LOG_DIR/orchestrator.log"
    printf "\n"

    read -r -p "是否实时查看所有日志? [y/N]: " choice
    if [ "$choice" = 'y' ] || [ "$choice" = 'Y' ]; then
        tail -f "$LOG_DIR"/*.log
    fi
}

# 重启所有服务
restart_all() {
    stop_all
    sleep 2
    start_all
}

# 主逻辑
if [ $# -gt 0 ]; then
    case "$1" in
        1|start)    start_all ;;
        2|stop)     stop_all ;;
        3|status)   get_status ;;
        4|logs)     watch_logs ;;
        5|restart)  restart_all ;;
        *)
            print_error "未知操作: $1"
            echo "可用操作: start, stop, status, logs, restart"
            exit 1
            ;;
    esac
    exit 0
fi

# 交互模式
while true; do
    show_menu
    read -r -p "请选择操作 (0-5): " choice

    case "$choice" in
        0) echo "再见!"; exit 0 ;;
        1) start_all ;;
        2) stop_all ;;
        3) get_status ;;
        4) watch_logs ;;
        5) restart_all ;;
        *) print_error "无效选择" ;;
    esac

    printf "\n"
    read -r -p "按回车继续..."
done
