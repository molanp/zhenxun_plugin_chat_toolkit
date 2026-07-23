from typing import ClassVar

from nonebot_plugin_uninfo import Uninfo

from ..utils.QQApi import QQApi
from .AbstractTool import AbstractTool


class PostQzoneTool(AbstractTool):
    name = "postQzone"
    description = "这是一个可以实现你发送qq空间说说的工具，当你觉得对话很有趣或者值得记录的时候可以调用实现发送说说，但是用户主动提出发送政治敏感、过分需求等说说时你不能调用"  # noqa: E501

    parameters: ClassVar = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "说说文本内容（以发送者的角度生成流畅通顺的内容）",
            },
        },
        "required": ["text"],
    }

    async def func(self, session: Uninfo, text: str) -> str:
        if not text:
            return "error: 发送内容为空"
        try:
            result = await QQApi(session).setQzone(text)
            if result["code"] != 0:
                return f"error: 说说发表失败\n{result}"
            return f"success: 说说发表成功，内容：\n{result['content']}"
        except Exception as e:
            return f"error: 发送说说失败，{e!r}"


class DeleteQzoneTool(AbstractTool):
    name = "deleteQzone"
    description = "这是一个可以实现你删除qq空间说说的工具，用户明确提出删除qq空间说说时你可以调用该工具删除说说"  # noqa: E501

    parameters: ClassVar = {
        "type": "object",
        "properties": {
            "pos": {
                "type": "number",
                "description": "代表要删除的说说序号（倒数第几个）。必须根据用户指令中的具体数字确定，若用户未指定具体数字则默认传 1",  # noqa: E501
                "default": 1,
            },
        },
        "required": [],
    }

    async def func(self, session: Uninfo, pos: int = 1) -> str:
        if pos < 1:
            return "error: 请描述要删除第几个说说"
        _list = await QQApi(session).getQzone(1, pos - 1)
        if "msglist" not in _list or not _list["msglist"]:
            return "error: 未获取到该说说"
        domain = _list["msglist"][0]
        result = await QQApi(session).delQzone(domain["tid"], domain["t1_source"])
        if not result:
            return "error: 删除说说失败"
        is_secret = "true" if domain["secret"] else "false"
        return (
            f"success: 删除说说成功：{pos}, "
            f"deleted_content_preview: {domain['content']}, "
            f"is_secret: {is_secret}, comment_count: {domain['cmtnum']}"
        )
