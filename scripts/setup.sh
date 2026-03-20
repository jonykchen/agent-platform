#!/usr/bin/env bash
# ============================================================
#  Agent Platform - Cross-Platform Setup Script
#  支持: macOS, Linux, Windows (Git Bash / WSL)
# ============================================================

set -e

# 颜色定义（跨平台）
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检测操作系统
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos" ;;
        Linux*)     echo "linux" ;;
        MINGW*|MSYS*|CYGWIN*)  echo "windows" ;;
        *)          echo "unknown" ;;
    esac
}

OS=$(detect_os)
echo -e "${BLUE}检测到操作系统: ${OS}${NC}"

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 打印状态
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# ============================================================
#  检查必需工具
# ============================================================
echo ""
echo -e "${BLUE}=== 检查必需工具 ===${NC}"

# Git
if command_exists git; then
    GIT_VERSION=$(git --version | head -1)
    print_status "Git: ${GIT_VERSION}"
else
    print_error "未安装 Git"
    exit 1
fi

# Python
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    print_status "${PYTHON_VERSION}"
elif command_exists python; then
    PYTHON_VERSION=$(python --version 2>&1)
    print_status "${PYTHON_VERSION}"
else
    print_error "未安装 Python"
    exit 1
fi

# Java
if command_exists java; then
    JAVA_VERSION=$(java -version 2>&1 | head -1)
    print_status "Java: ${JAVA_VERSION}"
else
    print_warning "未安装 Java (仅 Agent 编排不需要，完整开发需要 JDK 21)"
fi

# Docker
if command_exists docker; then
    DOCKER_VERSION=$(docker --version)
    print_status "${DOCKER_VERSION}"
else
    print_warning "未安装 Docker (需要 Docker Desktop 或 Docker Engine)"
fi

# Make
if command_exists make; then
    print_status "Make: 已安装"
else
    print_warning "未安装 Make"
    if [ "$OS" = "macos" ]; then
        echo "  安装: xcode-select --install"
    elif [ "$OS" = "linux" ]; then
        echo "  安装: sudo apt-get install build-essential"
    fi
fi

# ============================================================
#  安装 Python 工具
# ============================================================
echo ""
echo -e "${BLUE}=== Python 工具 ===${NC}"

# uv (推荐)
if command_exists uv; then
    UV_VERSION=$(uv --version)
    print_status "uv: ${UV_VERSION}"
else
    print_warning "未安装 uv (推荐)"
    echo "  安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# pip
if command_exists pip3 || command_exists pip; then
    print_status "pip: 已安装"
else
    print_warning "未安装 pip"
fi

# ruff
if command_exists ruff; then
    RUFF_VERSION=$(ruff --version)
    print_status "ruff: ${RUFF_VERSION}"
else
    print_warning "未安装 ruff"
    echo "  安装: pip install ruff 或 uv tool install ruff"
fi

# pytest
if command_exists pytest; then
    PYTEST_VERSION=$(pytest --version 2>&1 | head -1)
    print_status "pytest: ${PYTEST_VERSION}"
else
    print_warning "未安装 pytest"
fi

# ============================================================
#  安装 Proto 工具
# ============================================================
echo ""
echo -e "${BLUE}=== Proto 工具 ===${NC}"

if command_exists buf; then
    BUF_VERSION=$(buf --version 2>&1)
    print_status "buf: ${BUF_VERSION}"
else
    print_warning "未安装 buf"
    echo "  macOS: brew install bufbuild/buf/buf"
    echo "  Linux: curl -sSL https://github.com/bufbuild/buf/releases/latest/download/buf-\$(uname -s)-\$(uname -m) -o /usr/local/bin/buf && chmod +x /usr/local/bin/buf"
    echo "  Windows: scoop install buf"
fi

# ============================================================
#  配置 Claude Code
# ============================================================
echo ""
echo -e "${BLUE}=== Claude Code 配置 ===${NC}"

CLAUDE_DIR=".claude"
CLAUDE_MD="CLAUDE.md"

if [ -f "$CLAUDE_MD" ]; then
    print_status "CLAUDE.md 存在"
else
    print_error "CLAUDE.md 不存在"
fi

if [ -d "$CLAUDE_DIR" ]; then
    print_status ".claude/ 目录存在"
else
    print_warning ".claude/ 目录不存在"
fi

# 检查 settings.json
SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
if [ -f "$SETTINGS_FILE" ]; then
    # 验证 JSON 格式
    if command_exists python3; then
        if python3 -m json.tool "$SETTINGS_FILE" >/dev/null 2>&1; then
            print_status "settings.json 格式正确"
        else
            print_error "settings.json 格式错误"
        fi
    elif command_exists jq; then
        if jq . "$SETTINGS_FILE" >/dev/null 2>&1; then
            print_status "settings.json 格式正确"
        else
            print_error "settings.json 格式错误"
        fi
    fi
else
    print_error "settings.json 不存在"
fi

# ============================================================
#  检查 memory 目录
# ============================================================
MEMORY_DIR="${CLAUDE_DIR}/projects"
if [ -d "$MEMORY_DIR" ]; then
    print_status "Memory 目录存在"
else
    print_warning "Memory 目录不存在，正在创建..."
    mkdir -p "$MEMORY_DIR"
    print_status "Memory 目录已创建"
fi

# ============================================================
#  设置完成
# ============================================================
echo ""
echo -e "${GREEN}=== 设置检查完成 ===${NC}"
echo ""
echo "下一步:"
echo "  1. 启动开发环境: make dev"
echo "  2. 运行测试: make test"
echo "  3. 开始开发!"
echo ""
