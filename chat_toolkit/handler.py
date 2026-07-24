from nonebot import get_driver, on_message
from nonebot.adapters import Bot
from nonebot.rule import Rule, to_me
from nonebot_plugin_alconna import (
    Image,
    Text,
    UniMessage,
    UniMsg,
)
from nonebot_plugin_uninfo import Uninfo

from .config import ChatConfig, ThreadCache
from .data_source import (
    ChatManager,
    hello,
)
from .tools import ToolsManager
from .utils import clean_reply_xml, send_face
from .utils.xmlify import XmlifyOptions, xmlify_thread_sync, ResourceIndex

INIT = True

BLOCK_RANGES = [
    (3328144510, 3328144510),
    (66600000, 66600000),
    (2854196301, 2854216399),
    (3889000000, 3889999999),
    (4010000000, 4019999999),
]


async def block_qbot(session: Uninfo) -> bool:
    """过滤常见 QQ 机器人账号，返回 False 表示应被拦截。"""
    uid = session.user.id
    if not uid.isdigit():
        return True

    qq = int(uid)
    return not any(start <= qq <= end for start, end in BLOCK_RANGES)


@get_driver().on_startup
async def init_tools():
    if ChatConfig.get("MEMORY_ENABLED"):
        await ToolsManager.init()
    else:
        await ToolsManager.init(disable_tools=["remember", "forget"])


chat = on_message(
    priority=999,
    block=True,
    rule=to_me() & Rule(block_qbot),
)


@chat.handle()
async def _(bot: Bot, msg: UniMsg, session: Uninfo):
    plain_text = msg.extract_plain_text().strip()
    if not plain_text:
        text, image_path = hello()
        await UniMessage([Text(text), Image(path=image_path)]).finish(reply_to=True)
    if session.scene.is_group:
        history = await bot.get_group_msg_history(
            group_id=int(session.scene.id),
            count=ChatConfig.get("CONTEXT_WINDOW"),
        )
    else:
        history = await bot.get_friend_msg_history(
            user_id=int(session.user.id),
            count=ChatConfig.get("CONTEXT_WINDOW"),
        )
    resource_index = ResourceIndex()
    thread = xmlify_thread_sync(
        messages=history,
        bot=bot,
        options=XmlifyOptions(
            max_forward_depth=ChatConfig.get("MAX_FORWARD_DEPTH"),
            resource_index=resource_index,
        ),
    )
    ThreadCache.set(session.user.id, thread, resource_index)

    result = await ChatManager.normal_chat_result(
        thread=thread.xml_content, session=session
    )
    if not result:
        return

    if result.startswith("出错了"):
        await UniMessage(Text(result)).finish(reply_to=True)

    await UniMessage(clean_reply_xml(result)).send(reply_to=True)
    if face := await send_face(bot):
        await face.send()
