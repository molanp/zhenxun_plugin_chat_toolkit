from typing import ClassVar

from nonebot_plugin_uninfo import Uninfo

from ..config import ThreadCache
from .AbstractTool import AbstractTool
from zhenxun.services.log import logger
from ..utils.xmlify import XmlifyOptions, xmlify_thread_sync
from nonebot import get_bot


class getMessageTool(AbstractTool):
    name = "get_message"
    description = "获取指定消息的内容，包括合并转发消息的具体内容"

    parameters: ClassVar = {
        "type": "object",
        "properties": {
            "seq": {
                "type": "integer",
                "description": "消息的 seq",
            },
        },
        "required": ["seq"],
    }

    async def func(self, session: Uninfo, seq: int) -> str:
        thread = ThreadCache.get(session.user.id)
        if not thread:
            logger.warning(f"{session.user.id} 没有缓存上下文")
            return "fail: 没有缓存上下文"
        bot = get_bot(self_id=session.self_id)
        message = await bot.get_msg(message_id=seq)
        return xmlify_thread_sync(
            messages=message, bot=bot, options=XmlifyOptions(resource_index=thread[1])
        ).xml_content
