import os
from pathlib import Path
import random

from nonebot_plugin_uninfo import Uninfo

from zhenxun.configs.config import BotConfig
from zhenxun.configs.path_config import IMAGE_PATH
from zhenxun.models.ban_console import BanConsole
from zhenxun.services.ai import Agent, RunContext
from zhenxun.services.ai.core.options import GenerationConfig
from zhenxun.services.log import logger

from .config import ChatConfig
from .memory import MemoryStore, make_scope
from .tools import SESSION_STATE_KEY, ToolsManager
from .utils import (
    build_prompt,
    build_system_prompt,
    is_harmful_output,
)


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
    @staticmethod
    async def _build_agent(session: Uninfo) -> Agent:
        max_tool_cycles = max(0, int(ChatConfig.get("MAX_TOOL_CALLS_PER_TURN")))
        config = GenerationConfig()
        config.common.max_tokens = int(ChatConfig.get("MAX_TOKENS"))
        return Agent(
            name="chat_toolkit",
            instruction=await build_system_prompt(session),
            model=ChatConfig.get("PROVIDER"),
            tools=ToolsManager.get_agent_tools() if max_tool_cycles else [],
            generation_config=config,
            config={
                # One extra cycle lets the model produce text after the last tool round.
                "max_cycles": max_tool_cycles + 1,
                "enable_fallback_summary": True,
                "enable_hitl": False,
            },
        )

    @classmethod
    async def normal_chat_result(cls, thread: str, session: Uninfo) -> str | None:
        uid = session.user.id
        memories = await MemoryStore.recall(make_scope(session))
        try:
            agent = await cls._build_agent(session)
            context = RunContext(state={SESSION_STATE_KEY: session})
            result = await agent.run(
                build_prompt(thread=thread, memories=memories),
                context=context,
            )
        except Exception as e:
            logger.error(f"获取结果失败 e:{e}", "chat_toolkit", session=session)
            return f"出错了: {e}"

        output = str(result.output or "")
        if output and await is_harmful_output(output):
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
        return output
