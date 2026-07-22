from dataclasses import dataclass
import datetime
import os
from pathlib import Path
import random

from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_uninfo import Uninfo

from zhenxun.configs.config import BotConfig
from zhenxun.configs.path_config import IMAGE_PATH
from zhenxun.models.ban_console import BanConsole
from zhenxun.services.ai.core.messages.models import LLMMessage
from zhenxun.services.ai.core.messages.parts import ToolCallPart
from zhenxun.services.ai.core.messages.responses import ChatResponse
from zhenxun.services.ai.core.options import GenerationConfig
from zhenxun.services.log import logger

from .config import ChatConfig, LimitedSizeDict, get_prompt
from .model import ChatToolkitChatHistory
from .tools import ToolsManager
from .utils import (
    build_prompt,
    is_harmful_output,
)
from .utils.xai import generate

CHAT_HISTORY_TTL_SECONDS = 120 * 60  # 120 分钟
CHAT_HISTORY_MAX_LEN = 50


@dataclass
class HistoryEntry:
    last_access: datetime.datetime
    data: list[LLMMessage]


@dataclass
class HistoryCache:
    ttl_seconds: int
    max_len: int
    _store = LimitedSizeDict[str, HistoryEntry](max_size=50)

    def get(self, uid: str) -> list[LLMMessage] | None:
        now = datetime.datetime.now()
        info = self._store.get(uid)
        if not info:
            return None
        if (now - info.last_access).total_seconds() > self.ttl_seconds:
            self._store.pop(uid, None)
            return None
        info.last_access = now
        return info.data

    def set(self, uid: str, history: list[LLMMessage]) -> None:
        self._store[uid] = HistoryEntry(
            last_access=datetime.datetime.now(),
            data=history[-self.max_len :],
        )

    def add_records(self, uid: str, records: list[LLMMessage]) -> None:
        if uid not in self._store:
            return
        history = self._store[uid].data
        history.extend(records)
        self._store[uid].data = history[-self.max_len :]
        self._store[uid].last_access = datetime.datetime.now()

    def clear(self, uid: str | None = None) -> None:
        if uid is None:
            self._store.clear()
        else:
            self._store.pop(uid, None)

    def prune(self) -> int:
        now = datetime.datetime.now()
        expired = [
            uid
            for uid, info in self._store.items()
            if (now - info.last_access).total_seconds() > self.ttl_seconds
        ]
        for uid in expired:
            self._store.pop(uid, None)
        if expired:
            logger.debug(
                f"normal_chat 缓存清理: 移除 {len(expired)} 个 uid 的历史缓存",
                "chat_toolkit",
            )
        return len(expired)


_history_cache = HistoryCache(CHAT_HISTORY_TTL_SECONDS, CHAT_HISTORY_MAX_LEN)


@scheduler.scheduled_job("interval", hours=1, id="zhipu_normal_chat_cache_prune")
async def prune_history_cache_job() -> None:
    """定时任务：周期性清理 normal_chat 的内存缓存."""
    _history_cache.prune()


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
        uid: str,
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
                    await cls.get_chat_history(uid) + round_records,
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
    async def _flush_round_history(cls, uid: str, records: list[LLMMessage]) -> None:
        """将一轮对话（用户 + 模型返回 + 工具调用）写入数据库并同步更新缓存。

        前提:
            - 调用方保证只有在模型返回结构正常时才调用。
        """
        if not records:
            return

        # 1. 顺序写入数据库
        for rec in records:
            await ChatToolkitChatHistory.create(
                uid=uid,
                content=rec.to_storage_dict(),
            )

        # 2. 同步更新内存缓存
        _history_cache.add_records(uid, records)

    @classmethod
    async def normal_chat_result(cls, thread: str, session: Uninfo) -> str | None:
        uid = session.user.id
        user_rec = LLMMessage.user(build_prompt(thread))
        round_records: list[LLMMessage] = [user_rec]
        try:
            result = await cls.get_zhipu_result(
                (await cls.get_chat_history(uid)) + round_records,
            )
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
                uid, session, round_records, max_tool_calls, result
            )
        except Exception as e:
            logger.error(f"工具链处理异常: {e}", "chat_toolkit", session=session, e=e)
            return f"出错了: {e}"

        if "no_reply" in result.text:
            logger.warning(
                f"Rejected message from {session.user.id} in {session.scene.name}"
                f" {session.scene.id}: {result.text}"
            )
            return

        # 到这里，整轮对话都是“结构正常”的，可以一次性写入 DB + 缓存
        await cls._flush_round_history(uid, round_records)
        return result.text

    @classmethod
    async def clear_history(cls, uid: str | None = None) -> int:
        """清理历史记录，并同步清空内存缓存。"""
        _history_cache.clear(uid)
        return await ChatToolkitChatHistory.clear_history(uid)

    @classmethod
    async def get_chat_history(cls, uid: str) -> list[LLMMessage]:
        """统一获取对话历史的入口，带内存缓存 + TTL。

        行为:
            - 若缓存中存在并且在 TTL 内，则直接返回缓存中的历史；
            - 否则从数据库加载最近若干条记录，写入缓存并返回。
        """
        if cached_history := _history_cache.get(uid):
            return cached_history

        # 缓存不存在或已过期，从数据库获取完整历史
        history = await ChatToolkitChatHistory.get_history(uid)
        _history_cache.set(uid, history)
        return history

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
