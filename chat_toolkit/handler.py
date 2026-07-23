from nonebot import get_driver, on_message
from nonebot.adapters import Bot
from nonebot.permission import SUPERUSER
from nonebot.rule import Rule, to_me
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    At,
    CommandMeta,
    Image,
    MultiVar,
    Text,
    UniMessage,
    UniMsg,
    on_alconna,
)
from nonebot_plugin_uninfo import ADMIN, Uninfo

from .config import ChatConfig, ThreadCache
from .data_source import (
    ChatManager,
    hello,
)
from .tools import ToolsManager
from .utils import parse_reply_message, send_face
from .utils.xmlify import XmlifyOptions, xmlify_thread_sync

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


clear_my_chat = on_alconna(
    Alconna("清理我的会话"),
    priority=5,
    block=True,
    rule=Rule(block_qbot),
)

clear_all_chat = on_alconna(
    Alconna("清理全部会话"),
    permission=SUPERUSER,
    priority=5,
    block=True,
    rule=Rule(block_qbot),
)


clear_chat = on_alconna(
    Alconna(
        "清理会话",
        Args["target", MultiVar(str | int | At)],
        meta=CommandMeta(compact=True),
    ),
    permission=SUPERUSER,
    priority=5,
    block=True,
    rule=Rule(block_qbot),
)

show_chat = on_alconna(
    Alconna(
        "查看会话",
        Args["target?", str | int | At],
        meta=CommandMeta(compact=True),
    ),
    permission=ADMIN() | SUPERUSER,
    priority=5,
    block=True,
    rule=Rule(block_qbot),
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
    thread = xmlify_thread_sync(
        messages=history,
        bot=bot,
        options=XmlifyOptions(max_forward_depth=ChatConfig.get("MAX_FORWARD_DEPTH")),
    )
    ThreadCache.set(session.user.id, thread)

    result = await ChatManager.normal_chat_result(
        thread=thread.xml_content, session=session
    )
    if not result:
        return

    if result.startswith("出错了"):
        await UniMessage(Text(result)).finish(reply_to=True)

    reply_id, message = parse_reply_message(result)
    await UniMessage(message).send(reply_to=reply_id)
    if face := await send_face(bot):
        await face.send()
