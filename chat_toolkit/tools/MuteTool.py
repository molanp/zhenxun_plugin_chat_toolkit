import random
from typing import ClassVar

from nonebot import get_bot
from nonebot_plugin_uninfo import Uninfo

from zhenxun.models.level_user import LevelUser
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

        bot = get_bot(self_id=session.self_id)
        gid = session.scene.id
        target_uid = session.user.id

        level = await LevelUser.get_user_level(session.user.id, gid)
        if level < 5 and target_uid != session.user.id:
            return "error: permission_denied (current user level is less than 5)"

        mute_time = minute or random.randint(1, 100)
        try:
            await PlatformUtils.ban_user(bot, target_uid, gid, mute_time)
            return f"success: 禁言当前用户({target_uid}) {mute_time} 分钟成功"

        except Exception:
            return "error: 没有权限进行禁言操作，你可以尝试拉黑"


# class UnMuteTool(AbstractTool):
#     """取消用户禁言的工具"""

#     name = "unmute"
#     description = "安全与管理工具。仅在收到明确帮他人解除禁言的指令，且对话中给出了具体用户id时调用。日常闲聊绝对禁止调用。"  # noqa: E501
#     parameters = {
#         "type": "object",
#         "properties": {
#             "uid": {
#                 "type": "number",
#                 "description": "需要解除禁言的目标用户id。必须从用户指令中准确提取具体数字，严禁留空或胡编乱造。",  # noqa: E501
#             },
#         },
#         "required": ["uid"],
#     }

#     async def func(self, session: Uninfo, uid: str) -> str:
#         if not session.scene.is_group:
#             return "不是群聊环境，不能执行此操作"
#         bot = get_bot(self_id=session.self_id)
#         gid = session.scene.id
#         level = await LevelUser.get_user_level(session.user.id, gid)
#         if level < 5 and uid != session.user.id:
#             return "用户权限不足，不能执行此操作"
#         try:
#             await PlatformUtils.ban_user(bot, uid, gid, 0)
#             return f"取消禁言用户{uid} 成功"
#         except Exception:
#             return f"失败了，我在这个群聊 {gid} 没有权限解禁别人"
