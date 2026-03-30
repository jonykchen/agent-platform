#!/usr/bin/env bash
# ============================================================
#  Agent Platform - UV Setup Script (macOS / Linux / Git Bash)
#  用法: ./scripts/setup-uv.sh
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 参数解析
SKIP_PYTHON=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-python) SKIP_PYTHON=true; shift ;;
        --force) FORCE=true; shift ;;
        *) shift ;;
    esac
done

# 打印函数
print_status() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warn()   { echo -e "${YELLOW}[*]${NC} $1"; }
print_error()  { echo -e "${RED}[X]${NC} $1"; }
print_info()   { echo -e "${CYAN}[i]${NC} $1"; }

# Python 服务列表
PYTHON_SERVICES=(
    "orchestrator-python"
    "model-gateway-python"
    "knowledge-python"
)

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo ""
echo -e "${BLUE}=== Agent Platform - UV Setup ===${NC}"
echo "Project root: $PROJECT_ROOT"
echo ""

# ============================================================
#  1. 检查/安装 uv
# ============================================================
echo -e "${BLUE}=== Step 1: UV Installation ===${NC}"

if command -v uv &>/dev/null; then
    UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
    print_status "uv: $UV_VERSION"
else
    print_warn "uv not installed"
    print_info "Installing uv..."

    curl -LsSf https://astral.sh/uv/install.sh | sh

    # 刷新 PATH
    export PATH="$HOME/.local/bin:$PATH"

    if command -v uv &>/dev/null; then
        print_status "uv installed successfully"
    else
        print_error "Failed to install uv"
        echo "  Please install manually: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi

# ============================================================
#  2. 检查/安装 Python 3.12
# ============================================================
echo ""
echo -e "${BLUE}=== Step 2: Python 3.12 ===${NC}"

if [ "$SKIP_PYTHON" = true ]; then
    print_warn "Skipping Python installation (--skip-python)"
else
    if uv python list 2>/dev/null | grep -q "3\.12"; then
        print_status "Python 3.12 already installed"
    else
        print_info "Installing Python 3.12..."
        uv python install 3.12
        print_status "Python 3.12 installed"
    fi
fi

# ============================================================
#  3. 为每个服务创建虚拟环境并安装依赖
# ============================================================
echo ""
echo -e "${BLUE}=== Step 3: Setup Python Services ===${NC}"

for service in "${PYTHON_SERVICES[@]}"; do
    service_path="$PROJECT_ROOT/services/$service"

    if [ ! -d "$service_path" ]; then
        print_warn "$service not found, skipping"
        continue
    fi

    echo ""
    print_info "Setting up $service..."

    cd "$service_path"

    # 检查 pyproject.toml
    if [ ! -f "pyproject.toml" ]; then
        print_warn "$service: no pyproject.toml, skipping"
        cd "$PROJECT_ROOT"
        continue
    fi

    # 创建虚拟环境
    if [ -d ".venv" ] && [ "$FORCE" = true ]; then
        print_info "Removing existing .venv..."
        rm -rf ".venv"
    fi

    if [ ! -d ".venv" ]; then
        print_info "Creating virtual environment..."
        uv venv --python 3.12
    else
        print_status ".venv already exists"
    fi

    # 安装依赖
    print_info "Installing dependencies..."
    if uv sync --all-extras; then
        print_status "$service setup complete"
    else
        print_error "Failed to install dependencies for $service"
    fi

    cd "$PROJECT_ROOT"
done

# ============================================================
#  4. 验证安装
# ============================================================
echo ""
echo -e "${BLUE}=== Step 4: Verification ===${NC}"

ALL_OK=true

for service in "${PYTHON_SERVICES[@]}"; do
    service_path="$PROJECT_ROOT/services/$service"
    venv_path="$service_path/.venv"

    if [ ! -d "$venv_path" ]; then
        print_warn "$service: .venv not found"
        ALL_OK=false
        continue
    fi

    cd "$service_path"

    if uv run python -c "import fastapi; import pydantic" 2>/dev/null; then
        print_status "$service: packages verified"
    else
        print_warn "$service: package verification failed"
        ALL_OK=false
    fi

    cd "$PROJECT_ROOT"
done

# ============================================================
#  完成
# ============================================================
echo ""

if [ "$ALL_OK" = true ]; then
    print_status "All services setup successfully!"
else
    print_warn "Some services may need attention"
fi

echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "  1. Activate environment:  cd services/orchestrator-python && source .venv/bin/activate"
echo "  2. Run tests:             make test"
echo "  3. Start dev server:      make dev"
echo ""
