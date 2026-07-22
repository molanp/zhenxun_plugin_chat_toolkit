"""chat_toolkit 对 zhenxun.services.ai 的薄封装。

关键点：
底层 LLM 适配器 `_resolve_and_split_tools` 只会处理：
1. 带 `get_definition()` 的客户端工具（BaseTool / FunctionTool）
2. `execution_side == "server"` 的云端内置工具

chat_toolkit 自己的 AbstractTool.to_schema() 产出的是 OpenAI 风格 dict，
直接塞进 ChatRequest.tools 会被静默丢弃，模型收不到任何 tools。

因此本模块在调用 LLM 前，把 dict / ToolDefinition 包装成“仅声明 Schema
的伪 ToolExecutable”，只负责把工具描述发给模型；真正执行仍由
ToolsManager.call_func 在插件侧完成。
"""

from __future__ import annotations

from typing import Any

from zhenxun.services.ai.core.exceptions import (
    ControlFlowExit,
    LLMException,
    ModelRetry,
    get_user_friendly_error_message,
)
from zhenxun.services.ai.core.messages.models import LLMMessage
from zhenxun.services.ai.core.messages.requests import ChatRequest
from zhenxun.services.ai.core.messages.responses import ChatResponse
from zhenxun.services.ai.core.models import ModelName, ToolDefinition
from zhenxun.services.ai.core.options import GenerationConfig
from zhenxun.services.ai.llm.builder import IntentBuilder
from zhenxun.services.ai.llm.engine.router import LLMOrchestrator
from zhenxun.services.ai.message_builder import MessageBuilder
from zhenxun.services.ai.utils.logger import log_llm as logger


class SchemaOnlyTool:
    """
    适配层：让“只有 JSON Schema、没有服务层执行体”的工具也能被适配器识别。

    底层检查的是 hasattr(tool, "get_definition")，因此只要实现这个方法，
    工具声明就会进入 tool_defs，最终被序列化进 API 请求的 tools 字段。
    """

    execution_side: str = "client"

    def __init__(
        self,
        name: str,
        description: str = "",
        parameters: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.name = name
        self.description = description or ""
        self.parameters = parameters or {"type": "object", "properties": {}}
        self.metadata = metadata or {}

    async def get_definition(self, context: Any = None) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            metadata=self.metadata,
        )

    @classmethod
    def from_openai_schema(cls, schema: dict[str, Any]) -> SchemaOnlyTool | None:
        """解析 OpenAI tools 格式或扁平 {name, description, parameters}。"""
        payload = schema
        if isinstance(schema.get("function"), dict):
            payload = schema["function"]

        name = payload.get("name")
        if not name or not isinstance(name, str):
            return None

        parameters = payload.get("parameters") or {
            "type": "object",
            "properties": {},
        }
        if not isinstance(parameters, dict):
            parameters = {"type": "object", "properties": {}}

        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        return cls(
            name=name,
            description=str(payload.get("description") or ""),
            parameters=parameters,
            metadata=metadata,
        )


def normalize_tools(tools: list[Any] | None) -> list[Any] | None:
    """
    把各种工具入参统一成适配器能认的对象列表。

    已支持：
    - 已有 get_definition 的对象（原样保留）
    - 云端工具 execution_side == "server"（原样保留）
    - ToolDefinition
    - OpenAI / 扁平 dict schema
    - 上述对象的 list / dict.values()
    """
    if not tools:
        return tools

    raw = list(tools.values()) if isinstance(tools, dict) else list(tools)
    normalized: list[Any] = []

    for item in raw:
        if item is None:
            continue

        # 适配器原生可识别
        if getattr(item, "execution_side", "client") == "server":
            normalized.append(item)
            continue
        if hasattr(item, "get_definition"):
            normalized.append(item)
            continue

        # 服务层标准定义对象
        if isinstance(item, ToolDefinition):
            normalized.append(
                SchemaOnlyTool(
                    name=item.name,
                    description=item.description,
                    parameters=item.parameters or {},
                    metadata=item.metadata or {},
                )
            )
            continue

        # chat_toolkit AbstractTool.to_schema() 等 OpenAI dict
        if isinstance(item, dict):
            wrapped = SchemaOnlyTool.from_openai_schema(item)
            if wrapped is not None:
                normalized.append(wrapped)
            else:
                logger.warning(f"忽略无法解析的工具 schema dict: {item!r}")
            continue

        # 兼容 chat_toolkit 的 AbstractTool 实例（若直接传入）
        to_schema = getattr(item, "to_schema", None)
        if callable(to_schema):
            try:
                schema = to_schema()
            except Exception as e:
                logger.warning(f"调用 to_schema() 失败，已跳过: {e}")
                continue
            if isinstance(schema, dict):
                wrapped = SchemaOnlyTool.from_openai_schema(schema)
                if wrapped is not None:
                    normalized.append(wrapped)
                    continue

        logger.warning(
            "忽略无法识别的工具项（请传 dict schema / ToolDefinition / "
            f"带 get_definition 的对象）: {type(item).__name__}"
        )

    return normalized


async def generate(
    messages: list[LLMMessage],
    *,
    tools: list[Any] | None = None,
    instruction: str | None = None,
    model: ModelName = None,
    config: GenerationConfig | IntentBuilder | None = None,
    timeout: float | None = None,
) -> ChatResponse:
    try:
        messages = await MessageBuilder.normalize_to_llm_messages(
            messages, instruction=instruction
        )
        resolved_config: GenerationConfig | None = None
        if isinstance(config, IntentBuilder):
            resolved_config = config.build()
        else:
            resolved_config = config

        # 关键：dict schema -> SchemaOnlyTool，否则模型请求体里 tools 为空
        resolved_tools = normalize_tools(tools)

        request = ChatRequest(
            messages=messages,
            config=resolved_config,
            timeout=timeout,
            tools=resolved_tools,
        )

        sys_caps = request.extra.pop("__sys_capabilities", [])
        run_ctx = request.extra.pop("run_context", None)

        if sys_caps:
            from zhenxun.services.ai.capabilities import CombinedCapability
            from zhenxun.services.ai.core.models import LLMContext
            from zhenxun.services.ai.run import RunContext

            run_context = run_ctx or RunContext()
            llm_context = LLMContext(request=request)
            combined_cap = CombinedCapability(sys_caps)

            async def inner_handler(
                ctx: LLMContext[ChatRequest, ChatResponse],
            ) -> ChatResponse:
                return await LLMOrchestrator.invoke(
                    ctx.request,
                    model_name=model,
                    task="chat",
                    override_config=resolved_config,
                )

            return await combined_cap.wrap_model_request(
                run_context, llm_context, inner_handler
            )
        else:
            return await LLMOrchestrator.invoke(
                request, model_name=model, task="chat", override_config=resolved_config
            )
    except (LLMException, ModelRetry, ControlFlowExit) as e:
        raise e.with_traceback(None) from None
    except Exception as e:
        friendly_msg = get_user_friendly_error_message(e)
        logger.error(f"生成响应失败: {e} | 建议: {friendly_msg}", e=e)
        raise LLMException(f"生成响应失败: {friendly_msg}").with_traceback(
            None
        ) from None
