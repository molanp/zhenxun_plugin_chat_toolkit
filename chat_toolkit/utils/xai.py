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
from zhenxun.services.ai.core.models import ModelName
from zhenxun.services.ai.core.options import GenerationConfig
from zhenxun.services.ai.llm.builder import IntentBuilder
from zhenxun.services.ai.llm.engine.router import LLMOrchestrator
from zhenxun.services.ai.message_builder import MessageBuilder
from zhenxun.services.ai.utils.logger import log_llm as logger


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

        request = ChatRequest(
            messages=messages, config=resolved_config, timeout=timeout, tools=tools
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
