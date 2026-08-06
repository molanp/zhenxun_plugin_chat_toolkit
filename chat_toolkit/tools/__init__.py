import inspect
from typing import Any

from nonebot_plugin_uninfo import Uninfo

from zhenxun.services.ai.core.exceptions import ToolFatalError
from zhenxun.services.ai.run import RunContext
from zhenxun.services.ai.tools.core import BaseTool
from zhenxun.services.ai.tools.models import ToolResult
from zhenxun.services.log import logger

from .AbstractTool import AbstractTool, registry

SESSION_STATE_KEY = "chat_toolkit_session"
TOOL_LOG_PREVIEW_LIMIT = 1000


def _log_preview(value: Any) -> str:
    text = repr(value)
    if len(text) <= TOOL_LOG_PREVIEW_LIMIT:
        return text
    return f"{text[:TOOL_LOG_PREVIEW_LIMIT]}...（共 {len(text)} 字符）"


class AgentToolAdapter(BaseTool):
    """Expose a chat_toolkit tool through zhenxun's standard Agent runtime."""

    def __init__(self, descriptor: AbstractTool):
        self.descriptor = descriptor
        self._call_count = 0
        self._last_result: str | None = None
        super().__init__(
            name=descriptor.name,
            description=descriptor.description,
        )
        self._base_schema = descriptor.parameters

    async def run(self, context: RunContext, **kwargs: Any) -> str | ToolResult:  # pyright: ignore[reportIncompatibleMethodOverride]
        session: Uninfo | None = context.state.get(SESSION_STATE_KEY)
        if session is None:
            raise ToolFatalError("chat_toolkit 会话上下文不可用")

        max_calls = self.descriptor.max_calls_per_run
        if max_calls is not None and self._call_count >= max_calls:
            cached_result = self._last_result or "此前调用没有返回可用结果。"
            feedback = (
                f"工具 {self.descriptor.name} 本轮已经调用过，不会再次执行。"
                "请使用下面的首次调用结果直接回答用户，禁止再次调用该工具：\n\n"
                f"{cached_result}"
            )
            logger.warning(
                f"阻止工具重复调用: {self.descriptor.name}",
                "chat_toolkit.tools",
                session=session,
            )
            return ToolResult(output=feedback).as_error(is_retryable=False)

        self._call_count += 1
        func = self.descriptor.func
        logger.info(
            f"调用工具: {self.descriptor.name}, 参数: {_log_preview(kwargs)}",
            "chat_toolkit.tools",
            session=session,
        )
        if "session" in inspect.signature(func).parameters:
            kwargs["session"] = session
        try:
            result = await func(**kwargs)
        except Exception as e:
            logger.error(
                f"工具调用失败: {self.descriptor.name}",
                "chat_toolkit.tools",
                session=session,
                e=e,
            )
            failure = (
                f"工具 {self.descriptor.name} 调用失败: {type(e).__name__}: {e}。"
                "不要再次调用这个工具；请根据已有信息直接回答用户，"
                "无法完成时明确说明工具暂时不可用。"
            )
            self._last_result = failure
            return ToolResult(output=failure).as_error(is_retryable=False)
        self._last_result = result
        if max_calls is not None and self._call_count >= max_calls:
            context.run.add_system_prompt(
                f"工具 {self.descriptor.name} 本轮已完成并达到调用上限。"
                "必须使用刚才的工具结果直接回答用户，不得再次调用该工具。"
            )
        logger.info(
            f"工具返回: {self.descriptor.name}, 结果: {_log_preview(result)}",
            "chat_toolkit.tools",
            session=session,
        )
        return result


class ToolsManager:
    @staticmethod
    async def init(disable_tools: list[str] | None = None) -> None:
        """Initialize the tools registry by loading all tool modules."""
        await registry.load_modules(disable_tools)

    @staticmethod
    def get_agent_tools() -> list[BaseTool]:
        """Return tools executable by zhenxun's standard Agent runtime."""
        return [AgentToolAdapter(tool) for tool in registry.get_tools()]

