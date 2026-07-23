import random
from typing import ClassVar

from nonebot_plugin_uninfo import Uninfo

from zhenxun.models.ban_console import BanConsole

from .AbstractTool import AbstractTool


class BanTool(AbstractTool):

    name = "ban"
    description = (
        "当发现当前用户正在连续发送重复的废话或你不喜欢的内容时，"
        "你可以调用此工具对该用户进行封禁惩罚。日常正常交流或有意义的提问严禁调用。"
    )
    parameters: ClassVar = {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "封禁原因",
            },
            "minute": {
                "type": "number",
                "description": (
                    "拉黑时长，单位为分钟。你必须根据当前用户的恶劣程度自主决定封禁时间。"
                    "情节严重或屡教不改者，建议直接填写 1440（1天）、10080（7天）或 43200（30天）以示严惩；"  # noqa: E501
                    "只有在用户只是轻微刷屏且你想给予随机轻微惩罚时，才允许将此项留空。"
                ),
            },
        },
        "required": ["reason"],
    }

    async def func(
        self,
        session: Uninfo,
        reason: str = "",
        minute: int | None = None,
    ) -> str:
        uid = session.user.id
        ban_time = minute or random.randint(1, 100)
        try:
            await BanConsole.ban(
                uid,
                None,
                9999,
                reason,
                ban_time * 60,
            )
            return (
                f"success: 封禁用户 {uid}，封禁时长 {ban_time} 分钟，封禁原因 {reason}"
            )
        except Exception as e:
            return f"error: {e}"


# class UnBanTool(AbstractTool):

#     name = "unban"
#     description = "取消拉黑用户的工具。仅在收到明确帮他人解除拉黑的指令时使用"
#     parameters: ClassVar = {
#         "type": "object",
#         "properties": {
#             "uid": {"type": "number", "description": "需要解封的目标用户id"},
#         },
#         "required": ["uid"],
#     }

#     async def func(self, uid: str) -> str:
#         if await BanConsole.unban(uid):
#             return f"success: user_{uid}_has_been_unbanned"
#         else:
#             return f"error: user_{uid}_not_in_black_list"
