import random
from typing import ClassVar

from nonebot import get_bot
from nonebot_plugin_uninfo import Uninfo

from zhenxun.utils.platform import PlatformUtils

from .AbstractTool import AbstractTool


class MuteTool(AbstractTool):
    name = "mute"
    description = (
        "在群聊环境中，用户明确要求“禁言我”、“让我闭嘴”等自我惩罚或你非常讨厌用户时调用。"
        "若用户只是日常开玩笑、吐槽、表示想静静，绝对禁止调用此工具。"
    )

    parameters: ClassVar = {
        "type": "object",
        "properties": {
            "minute": {
                "type": "number",
                "description": (
                    "禁言时长（分钟）。"
                    "若用户要求长期禁言或情节严重，你可自主决定填写 60（1小时）、1440（1天）等具体数字；"  # noqa: E501
                    "若用户未指定时间或要求随机，此项必须留空。"
                ),
                "minimum": 1,
                "maximum": 43200,
            },
        },
        "required": [],
    }

    async def func(self, session: Uninfo, minute: int | None = None) -> str:
        if not session.scene.is_group:
            return "error: 不是群聊环境"
        assert session.member

        bot = get_bot(self_id=session.self_id)
        gid = session.scene.id
        target_uid = session.user.id

        is_admin = session.user.id in bot.config.superusers or any(
            r.id in {"ADMINISTRATOR", "OWNER"} for r in session.member.roles
        )
        if not is_admin and target_uid != session.user.id:
            return "error: permission_denied (current user is not admin)"

        mute_time = minute or random.randint(1, 100)
        try:
            await PlatformUtils.ban_user(bot, target_uid, gid, mute_time)
            return f"success: 禁言当前用户({target_uid}) {mute_time} 分钟成功"

        except Exception:
            return "error: 没有权限进行禁言操作，你可以尝试拉黑"
