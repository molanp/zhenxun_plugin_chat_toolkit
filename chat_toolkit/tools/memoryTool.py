from typing import ClassVar

from nonebot_plugin_uninfo import Uninfo

from ..memory import MemoryStore, make_scope
from .AbstractTool import AbstractTool


class RememberTool(AbstractTool):
    name = "remember"
    description = "记住一条有关当前会话对象的记忆"

    parameters: ClassVar = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "记忆的内容",
            },
        },
        "required": ["content"],
    }

    async def func(self, session: Uninfo, content: str) -> str:
        entry = await MemoryStore.remember(scope=make_scope(session), content=content)
        return str(entry)

class ForgetTool(AbstractTool):
    name = "forget"
    description = "忘记一条有关当前会话对象的记忆"

    parameters: ClassVar = {
        "type": "object",
        "properties": {
            "id": {
                "type": "integer",
                "description": "记忆的 ID",
            },
        },
        "required": ["id"],
    }

    async def func(self, session: Uninfo, id: int) -> str:
        entry = await MemoryStore.forget(scope=make_scope(session), id=id)
        return str(entry)
