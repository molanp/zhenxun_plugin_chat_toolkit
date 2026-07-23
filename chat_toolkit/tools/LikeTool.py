from typing import ClassVar

from nonebot import get_bot
from nonebot.adapters.onebot.v11 import ActionFailed
from nonebot_plugin_uninfo import Uninfo

from .AbstractTool import AbstractTool


class LikeTool(AbstractTool):
    name = "likeTool"
    description = "点赞工具,用户请求点赞相关的操作，包括给他人点赞或请求他人给自己点赞"
    parameters: ClassVar = {
        "type": "object",
        "properties": {
            "qq": {
                "type": "string",
                "description": "目标用户QQ号。留空则使用发送者QQ",
            },
            "count": {
                "type": "number",
                "description": "点赞次数(最多50次)",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
        },
    }

    async def func(self, session: Uninfo, qq: str = "", count: int = 10) -> str:
        MAX_LIKES = 20
        actual_count = min(count, MAX_LIKES)
        target_qq = qq or session.user.id
        try:
            target_qq_num = int(target_qq)
            bot = get_bot(session.self_id)  # pyright: ignore[reportAssignmentType]
            try:
                await bot.send_like(user_id=target_qq_num, times=actual_count)
                return "success: 点赞成功"
            except ActionFailed:
                return "error: 今日同一好友点赞数已达上限"

        except ValueError:
            return "error: invalid_qq_format (must be a valid qq number string)"
        except Exception as e:
            return f"error: execution_failed, exception: {e!s}"
