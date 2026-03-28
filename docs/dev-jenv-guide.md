# jenv Java 版本管理指南

> 本文档介绍如何使用 jenv 管理 Java 多版本环境，适用于 macOS/Linux 开发环境。

---

## 一、jenv 是什么

### 1.1 定位

jenv 是一个轻量级的 Java 版本管理器，类似于 Ruby 的 rbenv 和 Python 的 pyenv。

**核心理念**：只做版本切换，不负责安装 JDK。

```
┌─────────────────────────────────────────────────────────────┐
│                      版本管理工具链                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   安装 JDK        管理版本        项目级锁定                  │
│      │              │               │                       │
│      ▼              ▼               ▼                       │
│  ┌─────────┐    ┌─────────┐    ┌─────────────┐             │
│  │ Homebrew│    │  jenv   │    │ .java-version│            │
│  │ SDKMAN! │───▶│  切换   │───▶│ 项目自动切换 │            │
│  │ 手动下载 │    │ JAVA_HOME│    │             │             │
│  └─────────┘    └─────────┘    └─────────────┘             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 工作原理

jenv 通过修改 `JAVA_HOME` 环境变量和调整 `PATH` 来切换 Java 版本：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  jenv local │────▶│  写入当前   │────▶│  Shell 进入 │
│    21       │     │.java-version│     │  该目录     │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │ jenv 自动    │
                                        │ 设置 JAVA_HOME│
                                        └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │ java -version│
                                        │    21        │
                                        └─────────────┘
```

**核心机制：**

1. **JAVA_HOME 管理**：jenv 维护已注册 JDK 的路径映射
2. **PATH 注入**：在 PATH 前面插入当前版本的 `bin` 目录
3. **目录级锁定**：检测 `.java-version` 文件自动切换
4. **Shell 钩子**：通过 shell hook 在每次目录切换时检查版本

---

## 二、安装配置

### 2.1 安装 jenv

**macOS (Homebrew):**
```bash
brew install jenv
```

**Linux:**
```bash
git clone https://github.com/jenv/jenv.git ~/.jenv
```

### 2.2 配置 Shell

**Zsh (推荐):**
```bash
# 添加到 ~/.zshrc
export PATH="$HOME/.jenv/bin:$PATH"
eval "$(jenv init -)"

# 生效
source ~/.zshrc
```

**Bash:**
```bash
# 添加到 ~/.bashrc
export PATH="$HOME/.jenv/bin:$PATH"
eval "$(jenv init -)"

# 生效
source ~/.bashrc
```

**Fish Shell:**
```bash
# 添加到 ~/.config/fish/config.fish
set -x PATH $HOME/.jenv/bin $PATH
status --is-interactive; and source (jenv init -|psub)
```

### 2.3 验证安装

```bash
jenv version
# 输出: system (表示使用系统默认)

jenv --version
# 输出: jenv 0.5.x
```

---

## 三、基本用法

### 3.1 安装 JDK（通过 Homebrew）

jenv 不安装 JDK，需要先通过 Homebrew 或手动安装：

```bash
# 安装 JDK 17
brew install openjdk@17

# 安装 JDK 21
brew install openjdk@21

# 安装 JDK 8（旧项目兼容）
brew install openjdk@8
```

### 3.2 注册 JDK 到 jenv

```bash
# 查看 Homebrew 安装的 JDK 路径
ls -la /usr/local/opt/openjdk@*/

# 注册 JDK 17
jenv add /usr/local/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home

# 注册 JDK 21
jenv add /usr/local/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home

# 注册系统自带 JDK（如果有）
jenv add /Library/Java/JavaVirtualMachines/jdk-xx.jdk/Contents/Home
```

**输出示例：**
```
openjdk64-21.0.2 added
21.0.2 added
21.0 added
21 added
```

### 3.3 查看已注册版本

```bash
# 列出所有已注册版本
jenv versions

# 输出示例：
#   system
#   17.0
#   17.0.10
# * 21.0
#   21.0.2
#   openjdk64-17.0.10
#   openjdk64-21.0.2
```

### 3.4 切换版本

**全局切换（所有终端生效）：**
```bash
jenv global 21

# 验证
java -version
# openjdk version "21.0.2" 2024-01-16
```

**当前 Shell 会话切换（临时）：**
```bash
jenv shell 17

# 仅当前终端生效，关闭后恢复
java -version
# openjdk version "17.0.10" 2024-01-16
```

**项目级切换（推荐）：**
```bash
cd /path/to/your-project

# 设置项目版本（创建 .java-version 文件）
jenv local 21

# 验证
cat .java-version
# 21

# 进入该目录自动切换版本
java -version
# openjdk version "21.0.2"
```

### 3.5 查看当前版本

```bash
# 当前使用的版本
jenv version
# 21.0 (set by /Users/you/project/.java-version)

# 详细信息
jenv version-name
# 21.0.2

# JAVA_HOME 路径
jenv prefix
# /Users/you/.jenv/versions/21.0.2
```

---

## 四、进阶用法

### 4.1 版本别名

```bash
# 添加别名
jenv alias production 21.0.2
jenv alias development 17.0.10

# 使用别名
jenv local production
```

### 4.2 Maven/Gradle 集成

jenv 可以管理 Maven 和 Gradle 的 Java 版本：

```bash
# 启用 maven 插件
jenv enable-plugin maven

# 启用 gradle 插件
jenv enable-plugin gradle

# 验证
jenv version -v
```

### 4.3 多版本共存（同一项目不同模块）

```bash
# 项目根目录
jenv local 21

# 某个旧模块需要 JDK 17
cd legacy-module
jenv local 17
```

### 4.4 CI/CD 环境使用

```bash
# 在 CI 脚本中
export PATH="$HOME/.jenv/bin:$PATH"
eval "$(jenv init -)"
jenv local 21
```

---

## 五、命令速查

| 命令 | 说明 |
|------|------|
| `jenv versions` | 列出所有已注册版本 |
| `jenv version` | 显示当前版本 |
| `jenv global <version>` | 设置全局默认版本 |
| `jenv local <version>` | 设置当前目录版本 |
| `jenv shell <version>` | 设置当前 Shell 会话版本 |
| `jenv add <path>` | 注册新 JDK |
| `jenv remove <version>` | 移除已注册版本 |
| `jenv alias <name> <version>` | 创建别名 |
| `jenv uninstall <version>` | 卸载版本 |
| `jenv plugins` | 列出可用插件 |
| `jenv enable-plugin <name>` | 启用插件 |
| `jenv prefix` | 显示当前 JAVA_HOME |
| `jenv exec <cmd>` | 使用指定版本执行命令 |

---

## 六、常见问题

### Q1: jenv 版本不生效，仍显示系统默认

**原因**：Shell 未正确初始化 jenv。

**解决方案**：
```bash
# 检查 Shell 配置
cat ~/.zshrc | grep jenv

# 确保包含以下内容
export PATH="$HOME/.jenv/bin:$PATH"
eval "$(jenv init -)"

# 重新加载
source ~/.zshrc

# 验证
which java
# 应输出: /Users/you/.jenv/shims/java
```

### Q2: java -version 显示错误版本

**原因**：PATH 中有其他 Java 路径优先级更高。

**解决方案**：
```bash
# 检查 PATH
echo $PATH

# 检查 java 实际路径
which java

# 如果不是 jenv 路径，检查 ~/.zshrc 中是否有硬编码的 JAVA_HOME
grep JAVA_HOME ~/.zshrc ~/.bashrc ~/.zprofile 2>/dev/null

# 删除或注释掉硬编码的 JAVA_HOME
# export JAVA_HOME=/Library/Java/...  # 删除这行
```

### Q3: 如何删除已注册的版本

```bash
# 查看已注册版本
jenv versions

# 删除指定版本
jenv remove 17.0.10

# 或删除别名
jenv remove openjdk64-17.0.10
```

### Q4: IDE（IntelliJ IDEA）不识别 jenv 版本

**解决方案**：在 IDE 中手动配置 JAVA_HOME。

```bash
# 获取 jenv 管理的 JAVA_HOME
jenv prefix

# IntelliJ IDEA 配置：
# Preferences → Build, Execution, Deployment → Build Tools → Gradle
# Gradle JVM → 选择 "Add JDK" → 输入 jenv prefix 输出的路径
```

**推荐做法**：在项目根目录创建 `gradle.properties`：
```properties
org.gradle.java.home=/Users/you/.jenv/versions/21.0.2
```

### Q5: 多个 Shell 版本不一致

**原因**：不同 Shell 配置文件未同步。

**解决方案**：
```bash
# 确保所有 Shell 配置文件都包含 jenv 初始化
for file in ~/.zshrc ~/.bashrc ~/.bash_profile ~/.profile; do
  if [ -f "$file" ]; then
    grep -q "jenv init" "$file" || echo '
# jenv
export PATH="$HOME/.jenv/bin:$PATH"
eval "$(jenv init -)"' >> "$file"
  fi
done
```

### Q6: 升级 JDK 后 jenv 找不到

**原因**：Homebrew 升级 JDK 后路径变化。

**解决方案**：
```bash
# 移除旧版本
jenv remove 21.0.2

# 重新添加
jenv add /usr/local/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
```

### Q7: 如何查看 jenv 管理的所有 JDK 路径

```bash
# 查看版本目录
ls -la ~/.jenv/versions/

# 或查看详细映射
jenv versions --verbose
```

### Q8: .java-version 文件应该提交到 Git 吗？

**推荐做法**：**应该提交**。

```bash
# 添加到版本控制
git add .java-version

# 好处：
# 1. 团队成员自动使用正确的 Java 版本
# 2. CI/CD 环境可以读取该文件
# 3. 避免 "在我的机器上能跑" 问题
```

**`.gitignore` 中不要忽略**：
```bash
# 错误做法
# .java-version  # 不要添加到 .gitignore
```

---

## 七、最佳实践

### 7.1 项目级版本锁定（推荐）

```bash
# 每个项目根目录设置版本
cd /path/to/project
jenv local 21

# 提交到 Git
git add .java-version
git commit -m "chore: lock Java version to 21"
```

### 7.2 团队协作规范

```bash
# 项目根目录
project/
├── .java-version    # 提交到 Git
├── .sdkmanrc        # 如果团队使用 SDKMAN!，可同时保留
├── pom.xml
└── README.md
```

### 7.3 常用版本管理脚本

```bash
#!/bin/bash
# scripts/list-java-versions.sh

echo "=== 已安装的 Java 版本 ==="
jenv versions

echo ""
echo "=== 当前使用的版本 ==="
jenv version

echo ""
echo "=== JAVA_HOME ==="
jenv prefix

echo ""
echo "=== java -version ==="
java -version 2>&1 | head -3
```

---

## 八、与项目集成

### 8.1 本项目配置

Agent Platform 项目已配置：

```bash
# 项目根目录 .java-version 文件内容
cat /Users/jonychen/IdeaProjects/agent-platform/.java-version
# 21
```

### 8.2 开发环境设置步骤

```bash
# 1. 进入项目目录
cd /Users/jonychen/IdeaProjects/agent-platform

# 2. 安装 JDK 21（如果未安装）
brew install openjdk@21

# 3. 注册到 jenv
jenv add /usr/local/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home

# 4. 验证（自动读取 .java-version）
java -version
# 应输出: openjdk version "21.0.2"

# 5. 编译项目
cd services/gateway-java
mvn compile
```

---

## 九、参考资料

- [jenv 官方文档](https://www.jenv.be/)
- [jenv GitHub 仓库](https://github.com/jenv/jenv)
- [Homebrew OpenJDK](https://formulae.brew.sh/cask/openjdk)
