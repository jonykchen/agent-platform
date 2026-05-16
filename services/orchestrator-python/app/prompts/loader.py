"""Prompt 模板加载器

【核心概念】Prompt 管理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Prompt 是 Agent 与 LLM 交互的核心。良好的 Prompt 管理需要：
1. 模板复用：避免硬编码，统一管理
2. 参数化：支持动态变量注入
3. 版本控制：模板变更可追溯
4. 调试友好：模板内容可快速查看

【技术选型】Jinja2 vs f-string vs string.Template
┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Jinja2 (选择)      │ • 功能强大（循环、条件）    │ • 依赖第三方库              │
│                    │ • 自动转义（XSS 防护）      │ • 学习曲线                  │
│                    │ • 模板继承                  │                              │
│                    │ • 高性能                    │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ f-string           │ • Python 原生              │ • 无转义保护                │
│                    │ • 零依赖                    │ • 模板难以外部化            │
│                    │ • 简单直观                  │ • 无复杂逻辑                │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ string.Template    │ • 标准库                    │ • 功能有限                  │
│                    │ • 安全（$ 变量）            │ • 无条件/循环               │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【安全注意】
- Jinja2 默认自动转义，可防止 XSS
- 不要渲染用户可控的模板内容
- 使用沙箱环境隔离不受信任的模板

【设计原则】
- load(name): 加载模板文件
- load_system_prompt(prompt_type): 加载系统提示词
- render(name, **variables): 渲染模板
- 支持从文件和字符串加载

【参考】
- Jinja2 文档: https://jinja.palletsprojects.com/
- Prompt 工程指南: https://www.promptingguide.ai/
"""

from __future__ import annotations

import functools
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


class PromptType(str, Enum):
    """提示词类型枚举

    不同 Agent 模式有不同的系统提示词。
    """

    DEFAULT = "default"
    REACT = "react"
    PLAN_EXECUTE = "plan_execute"
    MULTI_AGENT = "multi_agent"


class PromptLoadError(Exception):
    """Prompt 加载错误

    当模板文件不存在或渲染失败时抛出。

    Attributes:
        prompt_name: Prompt 名称或路径
        reason: 错误原因
    """

    def __init__(self, prompt_name: str, reason: str):
        self.prompt_name = prompt_name
        self.reason = reason
        super().__init__(f"Failed to load prompt '{prompt_name}': {reason}")


class PromptLoader:
    """Prompt 模板加载器

    提供 Prompt 模板的加载、缓存和渲染功能。

    【核心功能】
    1. 从文件系统加载模板
    2. 支持模板继承和包含
    3. 自动缓存已加载模板
    4. 支持动态变量渲染

    【模板目录结构】
    ```
    prompts/
    ├── system/
    │   ├── default_system.txt
    │   ├── react_system.txt
    │   └── plan_execute_system.txt
    └── few_shot/
        └── examples.txt
    ```

    【使用示例】
    ```python
    loader = PromptLoader()

    # 加载系统提示词
    system_prompt = loader.load_system_prompt(PromptType.REACT)

    # 加载并渲染模板
    rendered = loader.render(
        "few_shot/examples",
        examples=[{"input": "...", "output": "..."}]
    )
    ```

    Attributes:
        base_dir: Prompt 模板根目录
        _env: Jinja2 环境实例
        _cache: 模板缓存字典
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        auto_reload: bool = False,
    ):
        """初始化 Prompt 加载器

        Args:
            base_dir: 模板根目录，默认为 app/prompts
            auto_reload: 是否自动重载模板（开发模式）
        """
        if base_dir is None:
            # 默认使用 app/prompts 目录
            base_dir = Path(__file__).parent

        self.base_dir = Path(base_dir)

        # 创建 Jinja2 环境
        self._env = Environment(
            loader=FileSystemLoader(str(self.base_dir)),
            autoescape=select_autoescape(default=False),  # 不需要 HTML 转义
            auto_reload=auto_reload,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

        # 模板缓存（非自动重载时有效）
        self._cache: dict[str, Template] = {}

        logger.debug(
            "prompt_loader_initialized",
            base_dir=str(self.base_dir),
            auto_reload=auto_reload,
        )

    def load(self, name: str) -> Template:
        """加载模板

        根据名称加载 Jinja2 模板，支持缓存。

        Args:
            name: 模板名称（不含扩展名），如 "system/default_system"

        Returns:
            Template: Jinja2 模板对象

        Raises:
            PromptLoadError: 模板不存在或加载失败

        Example:
            ```python
            template = loader.load("system/default_system")
            ```
        """
        # 尝试从缓存获取
        if name in self._cache:
            return self._cache[name]

        try:
            # 尝试多种扩展名
            template = None
            for ext in [".txt", ".jinja", ".jinja2", ""]:
                try:
                    template = self._env.get_template(f"{name}{ext}")
                    break
                except Exception:
                    continue

            if template is None:
                raise PromptLoadError(name, "Template file not found")

            # 缓存模板
            self._cache[name] = template
            return template

        except PromptLoadError:
            raise
        except Exception as e:
            raise PromptLoadError(name, str(e))

    def render(self, name: str, **variables: Any) -> str:
        """加载并渲染模板

        加载模板并用提供的变量渲染。

        Args:
            name: 模板名称
            **variables: 模板变量

        Returns:
            str: 渲染后的字符串

        Raises:
            PromptLoadError: 加载或渲染失败

        Example:
            ```python
            rendered = loader.render(
                "few_shot/examples",
                examples=[{"role": "user", "content": "..."}]
            )
            ```
        """
        template = self.load(name)
        try:
            return template.render(**variables)
        except Exception as e:
            raise PromptLoadError(name, f"Render failed: {e}")

    def render_string(self, template_str: str, **variables: Any) -> str:
        """渲染字符串模板

        直接从字符串创建模板并渲染，不从文件加载。

        Args:
            template_str: 模板字符串
            **variables: 模板变量

        Returns:
            str: 渲染后的字符串

        Example:
            ```python
            rendered = loader.render_string(
                "Hello, {{ name }}!",
                name="World"
            )
            ```
        """
        try:
            template = self._env.from_string(template_str)
            return template.render(**variables)
        except Exception as e:
            raise PromptLoadError("<string>", f"Render failed: {e}")

    def load_system_prompt(
        self,
        prompt_type: PromptType | str = PromptType.DEFAULT,
        **variables: Any,
    ) -> str:
        """加载系统提示词

        根据类型加载预定义的系统提示词。

        Args:
            prompt_type: 提示词类型
            **variables: 额外变量（如工具列表）

        Returns:
            str: 渲染后的系统提示词

        Raises:
            PromptLoadError: 加载失败

        Example:
            ```python
            # 加载默认系统提示词
            system_prompt = loader.load_system_prompt()

            # 加载 ReAct 模式系统提示词
            system_prompt = loader.load_system_prompt(
                PromptType.REACT,
                tools=registry.list_all()
            )
            ```
        """
        if isinstance(prompt_type, str):
            try:
                prompt_type = PromptType(prompt_type)
            except ValueError:
                prompt_type = PromptType.DEFAULT

        # 构建模板路径
        template_name = f"system/{prompt_type.value}_system"

        return self.render(template_name, **variables)

    def load_few_shot(self, name: str, **variables: Any) -> str:
        """加载 Few-shot 示例

        Args:
            name: 示例名称
            **variables: 模板变量

        Returns:
            str: 渲染后的示例

        Example:
            ```python
            examples = loader.load_few_shot("tool_call_examples")
            ```
        """
        return self.render(f"few_shot/{name}", **variables)

    def clear_cache(self) -> None:
        """清空模板缓存

        用于释放内存或强制重新加载模板。
        """
        self._cache.clear()
        logger.debug("prompt_cache_cleared")

    def list_templates(self) -> list[str]:
        """列出所有可用模板

        Returns:
            list[str]: 模板名称列表
        """
        return list(self._env.list_templates())

    def __repr__(self) -> str:
        return f"PromptLoader(base_dir={self.base_dir})"


# 全局加载器实例
_global_loader: PromptLoader | None = None


@functools.lru_cache
def get_prompt_loader() -> PromptLoader:
    """获取 Prompt 加载器单例

    FastAPI Depends 使用示例：
    ```python
    from fastapi import Depends
    from app.prompts.loader import get_prompt_loader, PromptLoader

    async def my_endpoint(
        loader: PromptLoader = Depends(get_prompt_loader)
    ):
        prompt = loader.load_system_prompt(PromptType.REACT)
    ```

    Returns:
        PromptLoader: Prompt 加载器实例
    """
    global _global_loader
    if _global_loader is None:
        _global_loader = PromptLoader()
    return _global_loader


def reset_prompt_loader() -> None:
    """重置 Prompt 加载器

    通常用于测试环境。
    """
    global _global_loader
    if _global_loader is not None:
        _global_loader.clear_cache()
    _global_loader = None
    get_prompt_loader.cache_clear()
