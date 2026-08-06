from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import importlib
import inspect
from pathlib import Path
import pkgutil
from typing import Any, ClassVar

from zhenxun.services.log import logger


class AbstractTool(ABC):
    name: str
    """工具名称"""
    parameters: ClassVar[dict[str, Any]]
    """符合 JSON Schema 的参数定义"""
    description: str
    """工具描述"""
    max_calls_per_run: int | None = None
    """单次 Agent 运行中的软调用上限，超限时返回已有结果而不中断。"""

    @abstractmethod
    async def func(self, session: Any, *args: Any, **kwargs: Any) -> str:
        """由工具类实现的调用逻辑"""

class ToolRegistry:
    _registry: ClassVar[dict[str, AbstractTool]] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def load_modules(cls, disable_tools: list[str] | None = None) -> None:
        async with cls._lock:
            if not cls._registry:
                await cls._load_all_modules()
            if disable_tools:
                cls.apply_disabled(disable_tools)

    @classmethod
    async def _load_all_modules(cls) -> None:
        tools_dir = Path(__file__).parent
        if not tools_dir.exists():
            logger.warning("工具目录不存在，无法加载工具。", "chat_toolkit.tools")
            return
        for module_info in pkgutil.iter_modules([str(tools_dir)]):
            module_name = module_info.name
            try:
                module = importlib.import_module(f".{module_name}", package=__package__)
            except Exception as e:
                logger.error(
                    f"加载工具模块 {module_name} 失败：{e}",
                    "chat_toolkit.tools",
                    e=e,
                )
                continue

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, AbstractTool) and obj is not AbstractTool:
                    cls.register(obj)

    @classmethod
    def apply_disabled(cls, tools: list[str]) -> None:
        for tool_name in tools:
            if tool_name in cls._registry:
                del cls._registry[tool_name]
                logger.info(f"已禁用工具 {tool_name}", "chat_toolkit.tools")

    @classmethod
    def register(cls, tool_cls: type[AbstractTool]) -> None:
        instance = tool_cls()
        if instance.name in cls._registry:
            logger.warning(
                f"工具 {instance.name} 已存在，忽略重复注册。",
                "chat_toolkit.tools",
            )
            return
        cls._registry[instance.name] = instance
        logger.success(f"注册工具 {instance.name} 成功", "chat_toolkit.tools")

    @classmethod
    def get_tools(cls) -> list[AbstractTool]:
        return list(cls._registry.values())

registry = ToolRegistry()
