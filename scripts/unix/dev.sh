#!/usr/bin/env bash
# ============================================================
#  Agent Platform - Unix/macOS 开发助手
#  用法: ./scripts/unix/dev.sh
#  支持: macOS, Linux, Git Bash (Windows)
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 打印函数
print_status() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warn()   { echo -e "${YELLOW}[*]${NC} $1"; }
print_error()  { echo -e "${RED}[X]${NC} $1"; }
print_info()   { echo -e "${CYAN}[i]${NC} $1"; }

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

# 清屏并显示菜单
show_menu() {
    clear
    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE} Agent Platform - Unix/macOS 开发助手${NC}"
    echo -e "${BLUE} 操作系统: ${OS}${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo ""
    echo " === 可用功能 ==="
    echo ""
    echo "   [1]  环境检查        - 检查 Git/Python/Java/Docker/Make/uv/ruff/buf"
    echo "   [2]  UV 安装        - 安装 uv、Python 3.12，创建虚拟环境"
    echo "   [3]  启动开发环境    - 启动 PostgreSQL/Redis/MinIO/Grafana"
    echo "   [4]  停止开发环境    - 停止 Docker 服务，清理容器"
    echo "   [5]  代码检查        - ruff lint 检查代码质量"
    echo "   [6]  格式化代码      - ruff format 格式化 Python 代码"
    echo "   [7]  运行测试        - pytest 运行单元测试"
    echo "   [8]  运行 E2E 测试   - 端到端集成测试"
    echo "   [9]  完整 CI 流水线  - lint + test + security"
    echo "   [10] 安全扫描        - Trivy 漏洞 + Gitleaks 密钥泄露"
    echo "   [0]  退出"
    echo ""
}

# ============================================================
#  [1] 环境检查
# ============================================================
do_setup() {
    echo ""
    echo -e "${BLUE}=== 环境检查 ===${NC}"
    echo ""

    # Git
    if command -v git &>/dev/null; then
        GIT_VERSION=$(git --version | head -1)
        print_status "Git: ${GIT_VERSION}"
    else
        print_error "Git 未安装"
        exit 1
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
            echo "  安装: xcode-select --install"
        elif [ "$OS" = "Linux" ]; then
            echo "  安装: sudo apt-get install build-essential"
        fi
    fi

    # uv
    if command -v uv &>/dev/null; then
        UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
        print_status "uv: ${UV_VERSION}"
    else
        print_warn "uv 未安装 (推荐用于 Python 管理)"
        echo "  执行 [2] 安装"
    fi

    # ruff
    if command -v ruff &>/dev/null; then
        RUFF_VERSION=$(ruff --version 2>/dev/null || echo "unknown")
        print_status "ruff: ${RUFF_VERSION}"
    else
        print_warn "ruff 未安装"
        echo "  安装: pip install ruff 或 uv tool install ruff"
    fi

    # buf (proto)
    if command -v buf &>/dev/null; then
        BUF_VERSION=$(buf --version 2>&1 || echo "unknown")
        print_status "buf: ${BUF_VERSION}"
    else
        print_warn "buf 未安装 (Proto 可选)"
        if [ "$OS" = "macOS" ]; then
            echo "  安装: brew install bufbuild/buf/buf"
        elif [ "$OS" = "Linux" ]; then
            echo "  安装: curl -sSL https://github.com/bufbuild/buf/releases/latest/download/buf-\$(uname -s)-\$(uname -m) -o /usr/local/bin/buf && chmod +x /usr/local/bin/buf"
        fi
    fi

    echo ""
    print_status "环境检查完成"
}

# ============================================================
#  [2] UV 安装
# ============================================================
do_uv_setup() {
    echo ""
    echo -e "${BLUE}=== UV 安装 ===${NC}"
    echo ""

    local python_services=(
        "orchestrator-python"
        "model-gateway-python"
        "knowledge-python"
    )

    # Step 1: UV Installation
    echo -e "${CYAN}Step 1: UV 安装${NC}"

    if command -v uv &>/dev/null; then
        UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
        print_status "uv: $UV_VERSION"
    else
        print_warn "uv 未安装"
        print_info "正在安装 uv..."

        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"

        if command -v uv &>/dev/null; then
            print_status "uv 安装成功"
        else
            print_error "uv 安装失败"
            echo "  手动安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
            return 1
        fi
    fi

    # Step 2: Python 3.12
    echo ""
    echo -e "${CYAN}Step 2: Python 3.12${NC}"

    if uv python list 2>/dev/null | grep -q "3\.12"; then
        print_status "Python 3.12 已安装"
    else
        print_info "正在安装 Python 3.12..."
        uv python install 3.12
        print_status "Python 3.12 安装成功"
    fi

    # Step 3: Setup Python Services
    echo ""
    echo -e "${CYAN}Step 3: 配置 Python 服务${NC}"

    for service in "${python_services[@]}"; do
        local service_path="$PROJECT_ROOT/services/$service"

        if [ ! -d "$service_path" ]; then
            print_warn "$service 不存在，跳过"
            continue
        fi

        echo ""
        print_info "正在配置 $service..."
        cd "$service_path"

        if [ ! -f "pyproject.toml" ]; then
            print_warn "$service: 无 pyproject.toml，跳过"
            cd "$PROJECT_ROOT"
            continue
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
        fi

        cd "$PROJECT_ROOT"
    done

    # Step 4: Verification
    echo ""
    echo -e "${CYAN}Step 4: 验证安装${NC}"

    local all_ok=true

    for service in "${python_services[@]}"; do
        local service_path="$PROJECT_ROOT/services/$service"
        local venv_path="$service_path/.venv"

        if [ ! -d "$venv_path" ]; then
            print_warn "$service: .venv 不存在"
            all_ok=false
            continue
        fi

        cd "$service_path"

        if uv run python -c "import fastapi; import pydantic" 2>/dev/null; then
            print_status "$service: 依赖验证通过"
        else
            print_warn "$service: 依赖验证失败"
            all_ok=false
        fi

        cd "$PROJECT_ROOT"
    done

    echo ""

    if [ "$all_ok" = true ]; then
        print_status "所有服务配置成功!"
    else
        print_warn "部分服务需要检查"
    fi

    echo ""
    echo -e "${GREEN}下一步:${NC}"
    echo "  1. 激活环境:  cd services/orchestrator-python && source .venv/bin/activate"
    echo "  2. 运行测试:  make test"
    echo "  3. 启动服务:  make dev"
    echo ""
}

# ============================================================
#  [3] 启动开发环境
# ============================================================
do_dev_up() {
    echo ""
    echo -e "${BLUE}=== 启动开发环境 ===${NC}"
    echo ""

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
        docker compose -f infra/docker-compose.yml up -d 2>/dev/null || \
        docker-compose -f infra/docker-compose.yml up -d
    fi

    echo ""
    print_status "服务已启动"
    echo ""
    echo -e "${BLUE}=== 服务状态 ===${NC}"
    docker compose -f infra/docker-compose.yml ps 2>/dev/null || \
    docker-compose -f infra/docker-compose.yml ps
    echo ""
    echo -e "${BLUE}=== 可用服务 ===${NC}"
    echo "  PostgreSQL:  localhost:5432"
    echo "  Redis:       localhost:6379"
    echo "  MinIO:       http://localhost:9000"
    echo "  Grafana:     http://localhost:3000"
    echo ""
}

# ============================================================
#  [4] 停止开发环境
# ============================================================
do_dev_down() {
    echo ""
    echo -e "${BLUE}=== 停止开发环境 ===${NC}"
    echo ""

    if [ -f "Makefile" ]; then
        make dev-down
    else
        docker compose -f infra/docker-compose.yml down 2>/dev/null || \
        docker-compose -f infra/docker-compose.yml down
    fi

    echo ""
    print_status "服务已停止"
}

# ============================================================
#  [5] 代码检查
# ============================================================
do_lint() {
    echo ""
    echo -e "${BLUE}=== 代码检查 ===${NC}"
    echo ""

    if [ -f "Makefile" ]; then
        make lint
    else
        echo "运行 ruff check..."
        if [ -d "services/orchestrator-python" ]; then
            cd services/orchestrator-python
            if command -v uv &>/dev/null; then
                uv run ruff check .
            elif command -v ruff &>/dev/null; then
                ruff check .
            else
                print_warn "ruff 不可用"
            fi
            cd "$PROJECT_ROOT"
        fi
    fi

    echo ""
    print_status "代码检查完成"
}

# ============================================================
#  [6] 格式化代码
# ============================================================
do_format() {
    echo ""
    echo -e "${BLUE}=== 格式化代码 ===${NC}"
    echo ""

    if [ -f "Makefile" ]; then
        make fmt
    else
        if [ -d "services/orchestrator-python" ]; then
            cd services/orchestrator-python
            if command -v uv &>/dev/null; then
                uv run ruff format .
            elif command -v ruff &>/dev/null; then
                ruff format .
            fi
            cd "$PROJECT_ROOT"
        fi
    fi

    echo ""
    print_status "格式化完成"
}

# ============================================================
#  [7] 运行测试
# ============================================================
do_test() {
    echo ""
    echo -e "${BLUE}=== 运行单元测试 ===${NC}"
    echo ""

    if [ -f "Makefile" ]; then
        make test
    else
        if [ -d "services/orchestrator-python" ]; then
            cd services/orchestrator-python
            if command -v uv &>/dev/null; then
                uv run pytest tests/ -v --tb=short
            elif command -v pytest &>/dev/null; then
                pytest tests/ -v --tb=short
            else
                print_warn "pytest 不可用"
            fi
            cd "$PROJECT_ROOT"
        fi
    fi

    echo ""
    print_status "测试完成"
}

# ============================================================
#  [8] 运行 E2E 测试
# ============================================================
do_e2e_test() {
    echo ""
    echo -e "${BLUE}=== 运行 E2E 测试 ===${NC}"
    echo ""

    echo "检查服务是否运行..."
    if ! docker compose -f infra/docker-compose.yml ps 2>/dev/null | grep -q "running" && \
       ! docker-compose -f infra/docker-compose.yml ps 2>/dev/null | grep -q "running"; then
        print_warn "服务未运行 - 正在启动..."
        docker compose -f infra/docker-compose.yml up -d 2>/dev/null || \
        docker-compose -f infra/docker-compose.yml up -d
        echo "等待 10 秒让服务就绪..."
        sleep 10
    fi

    if [ -d "tests/e2e" ]; then
        python3 -m pytest tests/e2e/ -v --tb=short -m "not slow" 2>/dev/null || \
        python -m pytest tests/e2e/ -v --tb=short -m "not slow"
    else
        print_warn "未找到 E2E 测试"
    fi

    echo ""
    print_status "E2E 测试完成"
}

# ============================================================
#  [9] 完整 CI 流水线
# ============================================================
do_ci() {
    echo ""
    echo -e "${BLUE}=== 完整 CI 流水线 ===${NC}"
    echo ""

    if [ -f "Makefile" ]; then
        make ci
    else
        echo "[1/2] 代码检查..."
        do_lint
        echo ""
        echo "[2/2] 运行测试..."
        do_test
    fi

    echo ""
    print_status "CI 流水线完成"
}

# ============================================================
#  [10] 安全扫描
# ============================================================
do_security() {
    echo ""
    echo -e "${BLUE}=== 安全扫描 ===${NC}"
    echo ""

    if command -v trivy &>/dev/null; then
        echo "运行 Trivy 扫描..."
        trivy fs --severity HIGH,CRITICAL .
    else
        print_warn "trivy 未安装"
        if [ "$OS" = "macOS" ]; then
            echo "  安装: brew install trivy"
        elif [ "$OS" = "Linux" ]; then
            echo "  安装: curl -sf https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh"
        fi
    fi

    if command -v gitleaks &>/dev/null; then
        echo "运行 Gitleaks 扫描..."
        gitleaks detect --source . --verbose
    else
        print_warn "gitleaks 未安装"
        if [ "$OS" = "macOS" ]; then
            echo "  安装: brew install gitleaks"
        fi
    fi

    echo ""
    print_status "安全扫描完成"
}

# ============================================================
#  主循环
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
        *)           print_error "未知操作: $1" ;;
    esac
    exit 0
fi

# 交互模式
while true; do
    show_menu
    read -r -p "请选择操作 (0-10): " CHOICE

    case "$CHOICE" in
        0) echo "再见!"; exit 0 ;;
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
        *) print_error "无效选择" ;;
    esac

    echo ""
    read -r -p "按回车继续..."
done