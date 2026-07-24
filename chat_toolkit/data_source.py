import os
from pathlib import Path
import random

from nonebot_plugin_uninfo import Uninfo

from zhenxun.configs.config import BotConfig
from zhenxun.configs.path_config import IMAGE_PATH
from zhenxun.models.ban_console import BanConsole
from zhenxun.services.ai.core.messages.models import LLMMessage
from zhenxun.services.ai.core.messages.parts import ToolCallPart
from zhenxun.services.ai.core.messages.responses import ChatResponse
from zhenxun.services.ai.core.options import GenerationConfig
from zhenxun.services.log import logger

from .config import ChatConfig, get_prompt
from .memory import MemoryStore, make_scope
from .tools import ToolsManager
from .utils import (
    build_prompt,
    is_harmful_output,
)
from .utils.xai import generate


def hello() -> tuple[str, Path]:
    """一些打招呼的内容"""
    result = random.choice(
        [
            "哦豁？！",
            "你好！Ov<",
            f"库库库，呼唤{BotConfig.self_nickname}做什么呢",
            "我在呢！",
            "呼呼，叫俺干嘛",
        ]
    )
    img = random.choice(os.listdir(IMAGE_PATH / "zai"))
    return result, IMAGE_PATH / "zai" / img


class ChatManager:
    @classmethod
    async def _resolve_tool_chain(
        cls,
        session: Uninfo,
        round_records: list[LLMMessage],
        max_tool_calls: int,
        initial_result: ChatResponse,
    ) -> ChatResponse:
        """处理模型可能发起的一条或多条工具调用链。"""
        if max_tool_calls <= 0 or not initial_result.tool_calls:
            return initial_result

        result = initial_result
        used_tool_calls = 0

        while result.tool_calls and used_tool_calls < max_tool_calls:
            tool_calls = result.tool_calls
            for tool_call in tool_calls:
                if used_tool_calls >= max_tool_calls:
                    logger.warning(
                        f"达到单次对话最大工具调用次数 {max_tool_calls}，"
                        "后续工具调用将被忽略",
                        "chat_toolkit",
                        session=session,
                    )
                    round_records.append(
                        LLMMessage.tool_response(
                            tool_call_id=tool_call.id,
                            function_name=tool_call.tool_name,
                            result="本次会话已达工具调用次数上限",
                        )
                    )
                    return result

                tool_result = await cls.parse_function_call(session, tool_call)
                round_records.append(
                    LLMMessage.tool_response(
                        tool_call_id=tool_call.id,
                        function_name=tool_call.tool_name,
                        result=tool_result,
                    )
                )
                used_tool_calls += 1

            # 当前这轮 tool_calls 处理完后，
            # 如果已经达到上限，则不再让模型继续发起新的工具调用
            if used_tool_calls >= max_tool_calls:
                break

            try:
                result = await cls.get_zhipu_result(
                    round_records,
                    use_tool=used_tool_calls < max_tool_calls,
                )
            except Exception as e:
                logger.error(f"模型调用异常: {e}", "chat_toolkit", e=e)
                raise e

            round_records.append(
                LLMMessage.assistant_tool_calls(
                    tool_calls=result.tool_calls, content=result.text
                )
            )

        return result

    @classmethod
    async def normal_chat_result(cls, thread: str, session: Uninfo) -> str | None:
        uid = session.user.id
        memories = await MemoryStore.recall(make_scope(session))
        user_rec = LLMMessage.user(build_prompt(thread=thread, memories=memories))
        round_records: list[LLMMessage] = [user_rec]
        try:
            result = await cls.get_zhipu_result(round_records)
        except Exception as e:
            logger.error(f"获取结果失败 e:{e}", "chat_toolkit", session=session)
            return f"出错了: {e}"

        if result.text and await is_harmful_output(result.text):
            logger.warning(
                f"UID {uid} 用户试图套取人设: 封禁用户 {session.user.id} 5 分钟",
                "chat_toolkit",
                session=session,
            )
            await BanConsole.ban(
                session.user.id,
                None,
                9999,
                "试图套取人设",
                300,
            )
            return ChatConfig.get("BLOCK_TIP")

        # 模型第一次回复（可能带 tool_calls），先暂存
        round_records.append(
            LLMMessage.assistant_tool_calls(result.tool_calls, result.text)
        )

        max_tool_calls = max(0, int(ChatConfig.get("MAX_TOOL_CALLS_PER_TURN")))
        try:
            result = await cls._resolve_tool_chain(
                session, round_records, max_tool_calls, result
            )
        except Exception as e:
            logger.error(f"工具链处理异常: {e}", "chat_toolkit", session=session, e=e)
            return f"出错了: {e}"

        return result.text

    @classmethod
    async def get_zhipu_result(
        cls, messages: list[LLMMessage], use_tool: bool = True
    ) -> ChatResponse:
        tools = ToolsManager.get_tools() if use_tool else []
        config = GenerationConfig()
        config.common.max_tokens = int(ChatConfig.get("MAX_TOKENS"))
        try:
            return await generate(
                messages=messages,
                model=ChatConfig.get("PROVIDER"),
                tools=tools,
                config=config,
                instruction=await get_prompt(),
            )
        except Exception as e:
            raise e

    @classmethod
    async def parse_function_call(cls, session: Uninfo, tool_call: ToolCallPart):
        args = tool_call.args
        logger.info(
            f"调用工具 {tool_call.tool_name} | 参数 {args}",
            "chat_toolkit",
            session=session,
        )
        return await ToolsManager.call_func(session, tool_call.tool_name, args)
