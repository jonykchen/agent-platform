#!/usr/bin/env bash
# ============================================================
#  Agent Platform - Unix/macOS 开发助手
#  用法: ./scripts/unix/dev.sh [操作]
#  支持: macOS, Linux, Git Bash (Windows)
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

# Python 服务列表（脚本级常量，便于统一维护）
PYTHON_SERVICES=(
    "orchestrator-python"
    "model-gateway-python"
    "knowledge-python"
)

# Docker Compose 文件路径
DOCKER_COMPOSE_FILE="infra/docker-compose.yml"

# 打印函数
print_status() { printf "${GREEN}[OK]${NC} %s\n" "$1"; }
print_warn()   { printf "${YELLOW}[*]${NC} %s\n" "$1"; }
print_error()  { printf "${RED}[X]${NC} %s\n" "$1"; }
print_info()   { printf "${CYAN}[i]${NC} %s\n" "$1"; }

# 检测操作系统
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macOS" ;;
        Linux*)     echo "Linux" ;;
        MINGW*|MSYS*|CYGWIN*)  echo "Windows (Git Bash)" ;;
        *)          echo "Unknown" ;;
    esac
}

OS=$(detect_os)

# ============================================================
#  Docker Compose 兼容性辅助函数
#  统一处理 "docker compose" (V2) 和 "docker-compose" (V1) 的差异
# ============================================================
DOCKER_COMPOSE_CMD=""

get_docker_compose_cmd() {
    if [ -n "$DOCKER_COMPOSE_CMD" ]; then
        return 0
    fi
    if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        print_error "未找到 docker compose 或 docker-compose"
        return 1
    fi
}

# 安全地执行 docker compose 命令
# 用法: run_docker_compose <子命令> [额外参数...]
run_docker_compose() {
    get_docker_compose_cmd || return 1
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" "$@"
}

# ============================================================
#  健康检查辅助函数
#  轮询等待服务就绪，替代固定 sleep
# ============================================================
wait_for_service() {
    local host="${1:-localhost}"
    local port="${2:-}"
    local max_attempts="${3:-30}"
    local attempt=1

    if [ -z "$port" ]; then
        print_warn "wait_for_service: 未指定端口，跳过健康检查"
        return 0
    fi

    print_info "等待 ${host}:${port} 就绪 (最多 ${max_attempts} 秒)..."
    while [ $attempt -le $max_attempts ]; do
        if command -v nc &>/dev/null; then
            if nc -z "$host" "$port" 2>/dev/null; then
                print_status "${host}:${port} 已就绪 (${attempt}s)"
                return 0
            fi
        elif command -v bash &>/dev/null; then
            # 使用 bash 内置 /dev/tcp 作为 fallback
            if (echo > /dev/tcp/"$host"/"$port") 2>/dev/null; then
                print_status "${host}:${port} 已就绪 (${attempt}s)"
                return 0
            fi
        fi
        sleep 1
        attempt=$((attempt + 1))
    done

    print_warn "${host}:${port} 在 ${max_attempts} 秒内未就绪，继续执行..."
    return 1
}

# 清屏并显示菜单
show_menu() {
    clear
    printf "\n"
    printf "${BLUE}============================================================${NC}\n"
    printf "${BLUE} Agent Platform - Unix/macOS 开发助手${NC}\n"
    printf "${BLUE} 操作系统: ${OS}${NC}\n"
    printf "${BLUE}============================================================${NC}\n"
    printf "\n"
    printf " === 可用功能 ===\n\n"
    printf "   [1]  环境检查        - 检查 Git/Python/Java/Docker/Make/uv/ruff/buf\n"
    printf "   [2]  UV 安装        - 安装 uv、Python 3.12，创建虚拟环境\n"
    printf "   [3]  启动开发环境    - 启动 PostgreSQL/Redis/MinIO/Grafana\n"
    printf "   [4]  停止开发环境    - 停止 Docker 服务，清理容器\n"
    printf "   [5]  代码检查        - ruff lint 检查代码质量\n"
    printf "   [6]  格式化代码      - ruff format 格式化 Python 代码\n"
    printf "   [7]  运行测试        - pytest 运行单元测试\n"
    printf "   [8]  运行 E2E 测试   - 端到端集成测试\n"
    printf "   [9]  完整 CI 流水线  - lint + test + security\n"
    printf "   [10] 安全扫描        - Trivy 漏洞 + Gitleaks 密钥泄露\n"
    printf "   [0]  退出\n\n"
}

# ============================================================
#  [1] 环境检查
# ============================================================
do_setup() {
    printf "\n${BLUE}=== 环境检查 ===${NC}\n\n"

    # Git
    if command -v git &>/dev/null; then
        GIT_VERSION=$(git --version | head -1)
        print_status "Git: ${GIT_VERSION}"
    else
        print_error "Git 未安装"
        return 1
    fi

    # Python
    if command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1)
        print_status "${PYTHON_VERSION}"
    elif command -v python &>/dev/null; then
        PYTHON_VERSION=$(python --version 2>&1)
        print_status "${PYTHON_VERSION}"
    else
        print_error "Python 未安装"
    fi

    # Java
    if command -v java &>/dev/null; then
        JAVA_VERSION=$(java -version 2>&1 | head -1)
        print_status "Java: ${JAVA_VERSION}"
    else
        print_warn "Java 未安装 (Agent 编排可选)"
    fi

    # Docker
    if command -v docker &>/dev/null; then
        if docker info &>/dev/null; then
            DOCKER_VERSION=$(docker --version)
            print_status "${DOCKER_VERSION} (运行中)"
        else
            print_warn "Docker 已安装但未运行"
        fi
    else
        print_warn "Docker 未安装"
    fi

    # Make
    if command -v make &>/dev/null; then
        print_status "Make: 已安装"
    else
        print_warn "Make 未安装"
        if [ "$OS" = "macOS" ]; then
            printf "  安装: xcode-select --install\n"
        elif [ "$OS" = "Linux" ]; then
            printf "  安装: sudo apt-get install build-essential\n"
        fi
    fi

    # uv
    if command -v uv &>/dev/null; then
        UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
        print_status "uv: ${UV_VERSION}"
    else
        print_warn "uv 未安装 (推荐用于 Python 管理)"
        printf "  执行 [2] 安装\n"
    fi

    # ruff
    if command -v ruff &>/dev/null; then
        RUFF_VERSION=$(ruff --version 2>/dev/null || echo "unknown")
        print_status "ruff: ${RUFF_VERSION}"
    else
        print_warn "ruff 未安装"
        printf "  安装: pip install ruff 或 uv tool install ruff\n"
    fi

    # buf (proto)
    if command -v buf &>/dev/null; then
        BUF_VERSION=$(buf --version 2>&1 || echo "unknown")
        print_status "buf: ${BUF_VERSION}"
    else
        print_warn "buf 未安装 (Proto 可选)"
        if [ "$OS" = "macOS" ]; then
            printf "  安装: brew install bufbuild/buf/buf\n"
        elif [ "$OS" = "Linux" ]; then
            printf "  安装: \" BUF_URL=\"https://github.com/bufbuild/buf/releases/latest/download/buf-\$(uname -s)-\$(uname -m)\" && sudo curl -sSL \"\$BUF_URL\" -o /usr/local/bin/buf && sudo chmod +x /usr/local/bin/buf\n"
        fi
    fi

    printf "\n"
    print_status "环境检查完成"
}

# ============================================================
#  [2] UV 安装
# ============================================================
do_uv_setup() {
    printf "\n${BLUE}=== UV 安装 ===${NC}\n\n"

    # Step 1: UV 安装
    printf "${CYAN}Step 1: UV 安装${NC}\n"

    if command -v uv &>/dev/null; then
        UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
        print_status "uv: $UV_VERSION"
    else
        print_warn "uv 未安装"
        print_info "正在安装 uv..."

        # 安全安装：先下载到临时文件，校验后再执行
        local uv_install_tmp
        uv_install_tmp="$(mktemp "${TMPDIR:-/tmp}/uv-install.XXXXXX.sh")"
        if curl -fsSL https://astral.sh/uv/install.sh -o "$uv_install_tmp"; then
            if [ -s "$uv_install_tmp" ]; then
                sh "$uv_install_tmp"
            else
                print_error "uv 安装脚本下载失败 (空文件)"
                rm -f "$uv_install_tmp"
                return 1
            fi
            rm -f "$uv_install_tmp"
        else
            print_error "uv 安装脚本下载失败"
            rm -f "$uv_install_tmp"
            return 1
        fi

        # 刷新 PATH
        export PATH="$HOME/.local/bin:$PATH"

        if command -v uv &>/dev/null; then
            print_status "uv 安装成功"
        else
            print_error "uv 安装失败"
            printf "  手动安装: curl -fsSL https://astral.sh/uv/install.sh -o /tmp/uv-install.sh && sh /tmp/uv-install.sh\n"
            return 1
        fi
    fi

    # Step 2: Python 3.12
    printf "\n${CYAN}Step 2: Python 3.12${NC}\n"

    if uv python list 2>/dev/null | grep -q "3\.12"; then
        print_status "Python 3.12 已安装"
    else
        print_info "正在安装 Python 3.12..."
        if uv python install 3.12; then
            print_status "Python 3.12 安装成功"
        else
            print_error "Python 3.12 安装失败"
            return 1
        fi
    fi

    # Step 3: 配置 Python 服务
    printf "\n${CYAN}Step 3: 配置 Python 服务${NC}\n"

    for service in "${PYTHON_SERVICES[@]}"; do
        local service_path="$PROJECT_ROOT/services/$service"

        if [ ! -d "$service_path" ]; then
            print_warn "$service 不存在，跳过"
            continue
        fi

        printf "\n"
        print_info "正在配置 $service..."

        # 使用子shell，避免 cd 失败影响主进程工作目录
        (
            cd "$service_path" || exit 1

            if [ ! -f "pyproject.toml" ]; then
                echo "$(print_warn "$service: 无 pyproject.toml，跳过")"
                exit 0
            fi

            if [ ! -d ".venv" ]; then
                print_info "创建虚拟环境..."
                uv venv --python 3.12
            else
                print_status ".venv 已存在"
            fi

            print_info "安装依赖..."
            if uv sync --all-extras; then
                print_status "$service 配置完成"
            else
                print_error "$service 依赖安装失败"
                exit 1
            fi
        )
    done

    # Step 4: 验证安装
    printf "\n${CYAN}Step 4: 验证安装${NC}\n"

    local all_ok=true

    for service in "${PYTHON_SERVICES[@]}"; do
        local service_path="$PROJECT_ROOT/services/$service"
        local venv_path="$service_path/.venv"

        if [ ! -d "$venv_path" ]; then
            print_warn "$service: .venv 不存在"
            all_ok=false
            continue
        fi

        (
            cd "$service_path" || exit 1

            if uv run python -c "import fastapi; import pydantic" 2>/dev/null; then
                print_status "$service: 依赖验证通过"
            else
                print_warn "$service: 依赖验证失败"
                exit 1
            fi
        ) || all_ok=false
    done

    printf "\n"

    if [ "$all_ok" = true ]; then
        print_status "所有服务配置成功!"
    else
        print_warn "部分服务需要检查"
    fi

    printf "\n${GREEN}下一步:${NC}\n"
    printf "  1. 激活环境:  cd services/orchestrator-python && source .venv/bin/activate\n"
    printf "  2. 运行测试:  make test\n"
    printf "  3. 启动服务:  make dev\n\n"
}

# ============================================================
#  [3] 启动开发环境
# ============================================================
do_dev_up() {
    printf "\n${BLUE}=== 启动开发环境 ===${NC}\n\n"

    if ! command -v docker &>/dev/null; then
        print_error "Docker 未安装"
        return 1
    fi

    if ! docker info &>/dev/null; then
        print_error "Docker 未运行 - 请先启动 Docker"
        return 1
    fi

    if [ -f "Makefile" ]; then
        make dev
    else
        if ! run_docker_compose up -d; then
            print_error "Docker 服务启动失败"
            return 1
        fi
    fi

    # 健康检查：等待核心服务就绪
    printf "\n"
    print_info "检查服务健康状态..."
    wait_for_service localhost 5432 30 || true   # PostgreSQL
    wait_for_service localhost 6379 30 || true    # Redis

    printf "\n"
    print_status "服务已启动"
    printf "\n${BLUE}=== 服务状态 ===${NC}\n"
    run_docker_compose ps || true
    printf "\n${BLUE}=== 可用服务 ===${NC}\n"
    printf "  PostgreSQL:  localhost:5432\n"
    printf "  Redis:       localhost:6379\n"
    printf "  MinIO:       http://localhost:9000\n"
    printf "  Grafana:     http://localhost:3000\n\n"
}

# ============================================================
#  [4] 停止开发环境
# ============================================================
do_dev_down() {
    printf "\n${BLUE}=== 停止开发环境 ===${NC}\n\n"

    if [ -f "Makefile" ]; then
        make dev-down
    else
        run_docker_compose down || true
    fi

    printf "\n"
    print_status "服务已停止"
}

# ============================================================
#  [5] 代码检查
# ============================================================
do_lint() {
    printf "\n${BLUE}=== 代码检查 ===${NC}\n\n"

    if [ -f "Makefile" ]; then
        make lint
    else
        local has_tool=false
        for service in "${PYTHON_SERVICES[@]}"; do
            local service_path="$PROJECT_ROOT/services/$service"
            [ -d "$service_path" ] || continue

            (
                cd "$service_path" || exit 1
                if command -v uv &>/dev/null; then
                    uv run ruff check .
                elif command -v ruff &>/dev/null; then
                    ruff check .
                else
                    exit 2  # 标记无可用工具
                fi
            )
            local rc=$?
            if [ $rc -eq 2 ]; then
                : # 无工具，在外层统一提示
            elif [ $rc -ne 0 ]; then
                print_warn "$service: 代码检查发现问题"
            else
                print_status "$service: 代码检查通过"
            fi
            has_tool=true
        done

        if [ "$has_tool" = false ]; then
            print_warn "ruff 不可用，请安装: pip install ruff 或 uv tool install ruff"
        fi
    fi

    printf "\n"
    print_status "代码检查完成"
}

# ============================================================
#  [6] 格式化代码
# ============================================================
do_format() {
    printf "\n${BLUE}=== 格式化代码 ===${NC}\n\n"

    if [ -f "Makefile" ]; then
        make fmt
    else
        local has_tool=false
        for service in "${PYTHON_SERVICES[@]}"; do
            local service_path="$PROJECT_ROOT/services/$service"
            [ -d "$service_path" ] || continue

            (
                cd "$service_path" || exit 1
                if command -v uv &>/dev/null; then
                    uv run ruff format .
                elif command -v ruff &>/dev/null; then
                    ruff format .
                else
                    exit 2  # 标记无可用工具
                fi
            )
            local rc=$?
            if [ $rc -eq 2 ]; then
                : # 无工具，在外层统一提示
            elif [ $rc -ne 0 ]; then
                print_warn "$service: 格式化出现错误"
            else
                print_status "$service: 格式化完成"
            fi
            has_tool=true
        done

        if [ "$has_tool" = false ]; then
            print_warn "ruff 不可用，请安装: pip install ruff 或 uv tool install ruff"
        fi
    fi

    printf "\n"
    print_status "格式化完成"
}

# ============================================================
#  [7] 运行测试
# ============================================================
do_test() {
    printf "\n${BLUE}=== 运行单元测试 ===${NC}\n\n"

    if [ -f "Makefile" ]; then
        make test
    else
        local has_tool=false
        for service in "${PYTHON_SERVICES[@]}"; do
            local service_path="$PROJECT_ROOT/services/$service"
            [ -d "$service_path" ] || continue

            (
                cd "$service_path" || exit 1
                if command -v uv &>/dev/null; then
                    uv run pytest tests/ -v --tb=short
                elif command -v pytest &>/dev/null; then
                    pytest tests/ -v --tb=short
                else
                    exit 2  # 标记无可用工具
                fi
            )
            local rc=$?
            if [ $rc -eq 2 ]; then
                : # 无工具
            elif [ $rc -ne 0 ]; then
                print_warn "$service: 测试失败"
            else
                print_status "$service: 测试通过"
            fi
            has_tool=true
        done

        if [ "$has_tool" = false ]; then
            print_warn "pytest 不可用，请安装: pip install pytest 或 uv sync"
        fi
    fi

    printf "\n"
    print_status "测试完成"
}

# ============================================================
#  [8] 运行 E2E 测试
# ============================================================
do_e2e_test() {
    printf "\n${BLUE}=== 运行 E2E 测试 ===${NC}\n\n"

    printf "检查服务是否运行...\n"
    local services_running=false
    if run_docker_compose ps 2>/dev/null | grep -q "running\|Up"; then
        services_running=true
    fi

    if [ "$services_running" = false ]; then
        print_warn "服务未运行 - 正在启动..."
        if ! run_docker_compose up -d; then
            print_error "服务启动失败"
            return 1
        fi
        # 健康检查轮询，替代固定 sleep
        wait_for_service localhost 5432 30 || true
        wait_for_service localhost 6379 30 || true
        print_info "等待额外 5 秒确保服务完全就绪..."
        sleep 5
    fi

    if [ -d "tests/e2e" ]; then
        local e2e_failed=false
        if command -v python3 &>/dev/null; then
            python3 -m pytest tests/e2e/ -v --tb=short -m "not slow" || e2e_failed=true
        elif command -v python &>/dev/null; then
            python -m pytest tests/e2e/ -v --tb=short -m "not slow" || e2e_failed=true
        else
            print_warn "Python 不可用，无法运行 E2E 测试"
            return 1
        fi

        if [ "$e2e_failed" = true ]; then
            print_warn "E2E 测试存在失败用例"
        fi
    else
        print_warn "未找到 E2E 测试"
    fi

    printf "\n"
    print_status "E2E 测试完成"
}

# ============================================================
#  [9] 完整 CI 流水线
# ============================================================
do_ci() {
    printf "\n${BLUE}=== 完整 CI 流水线 ===${NC}\n\n"

    local ci_failed=false

    if [ -f "Makefile" ]; then
        make ci || ci_failed=true
    else
        printf "[1/3] 代码检查...\n"
        do_lint || ci_failed=true

        printf "\n[2/3] 运行测试...\n"
        do_test || ci_failed=true

        printf "\n[3/3] 安全扫描...\n"
        do_security || ci_failed=true
    fi

    printf "\n"

    if [ "$ci_failed" = true ]; then
        print_warn "CI 流水线完成（存在失败项）"
        return 1
    else
        print_status "CI 流水线完成"
    fi
}

# ============================================================
#  [10] 安全扫描
# ============================================================
do_security() {
    printf "\n${BLUE}=== 安全扫描 ===${NC}\n\n"

    local security_failed=false

    if command -v trivy &>/dev/null; then
        printf "运行 Trivy 扫描...\n"
        trivy fs --severity HIGH,CRITICAL . || security_failed=true
    else
        print_warn "trivy 未安装"
        if [ "$OS" = "macOS" ]; then
            printf "  安装: brew install trivy\n"
        elif [ "$OS" = "Linux" ]; then
            printf "  安装: sudo apt-get install trivy 或参考 https://aquasecurity.github.io/trivy/latest/getting-started/installation/\n"
        fi
    fi

    if command -v gitleaks &>/dev/null; then
        printf "运行 Gitleaks 扫描...\n"
        gitleaks detect --source . --verbose || security_failed=true
    else
        print_warn "gitleaks 未安装"
        if [ "$OS" = "macOS" ]; then
            printf "  安装: brew install gitleaks\n"
        fi
    fi

    printf "\n"

    if [ "$security_failed" = true ]; then
        print_warn "安全扫描完成（发现风险）"
        return 1
    else
        print_status "安全扫描完成"
    fi
}

# ============================================================
#  主逻辑
# ============================================================

# 如果带参数运行，直接执行对应功能
if [ $# -gt 0 ]; then
    case "$1" in
        1|setup)     do_setup ;;
        2|uv)        do_uv_setup ;;
        3|up)        do_dev_up ;;
        4|down)      do_dev_down ;;
        5|lint)      do_lint ;;
        6|fmt|format) do_format ;;
        7|test)      do_test ;;
        8|e2e)       do_e2e_test ;;
        9|ci)        do_ci ;;
        10|security) do_security ;;
        -h|--help)
            printf "用法: %s [操作]\n" "$0"
            printf "操作: setup|uv|up|down|lint|fmt|test|e2e|ci|security\n"
            printf "无参数时进入交互模式\n"
            exit 0
            ;;
        *)
            print_error "未知操作: $1"
            printf "可用操作: setup, uv, up, down, lint, fmt, test, e2e, ci, security\n"
            exit 1
            ;;
    esac
    exit $?
fi

# 交互模式
while true; do
    show_menu
    read -r -p "请选择操作 (0-10): " CHOICE

    case "$CHOICE" in
        0) printf "再见!\n"; exit 0 ;;
        1) do_setup ;;
        2) do_uv_setup ;;
        3) do_dev_up ;;
        4) do_dev_down ;;
        5) do_lint ;;
        6) do_format ;;
        7) do_test ;;
        8) do_e2e_test ;;
        9) do_ci ;;
        10) do_security ;;
        h|H) printf "用法: ./scripts/unix/dev.sh [setup|uv|up|down|lint|fmt|test|e2e|ci|security]\n" ;;
        *) print_error "无效选择" ;;
    esac

    printf "\n"
    read -r -p "按回车继续..."
done
