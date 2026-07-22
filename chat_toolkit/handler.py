import asyncio

from nonebot import get_driver, on_message
from nonebot.adapters import Bot
from nonebot.permission import SUPERUSER
from nonebot.rule import Rule, to_me
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    Arparma,
    At,
    CommandMeta,
    Image,
    MultiVar,
    Text,
    UniMessage,
    UniMsg,
    on_alconna,
)
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_uninfo import ADMIN, Uninfo

from zhenxun.services.log import logger
from zhenxun.utils.rules import ensure_group

from .config import ChatConfig
from .data_source import (
    ChatManager,
    hello,
)
from .model import ChatToolkitChatHistory
from .tools import ToolsManager
from .utils import send_face, split_text
from .utils.xmlify import xmlify_thread_sync

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
    await ToolsManager.init()


@scheduler.scheduled_job(
    "cron",
    hour=0,
    minute=0,
)
async def delete_expired_chat_history():
    day = ChatConfig.get("EXPIRE_DAY")
    if day < 0:
        logger.info("跳过清理过期会话任务: 用户设置永不过期", "chat_toolkit")
        return
    try:
        deleted = await ChatToolkitChatHistory.delete_old_records(day)
        logger.info(f"成功清理 {deleted} 条过期会话 记录", "chat_toolkit")
    except Exception as e:
        logger.error("清理过期会话记录失败", "chat_toolkit", e=e)


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
    if ensure_group(session):
        history = await bot.get_group_msg_history(
            group_id=int(session.scene.id),
            count=ChatConfig.get("CONTEXT_WINDOW"),
        )
    else:
        history = await bot.get_friend_msg_history(
            user_id=int(session.user.id),
            count=ChatConfig.get("CONTEXT_WINDOW"),
        )
    thread = xmlify_thread_sync(history, bot=bot)

    result = await ChatManager.normal_chat_result(
        thread=thread.xml_content, session=session
    )
    if not result:
        return

    if result.startswith("出错了"):
        await UniMessage(Text(result)).finish(reply_to=True)

    for r, delay in await split_text(result):
        await UniMessage(r).send(reply_to=True)
        await asyncio.sleep(delay)
    if face := await send_face(bot):
        await face.send()


@clear_my_chat.handle()
async def _(session: Uninfo):
    uid = session.user.id
    await clear_my_chat.send(
        Text(f"已清理 {uid} 的 {await ChatManager.clear_history(uid)} 条数据"),
        reply_to=True,
    )


@clear_all_chat.handle()
async def _():
    await clear_all_chat.send(
        Text(f"已清理 {await ChatManager.clear_history()} 条用户数据"),
        reply_to=True,
    )


@clear_chat.handle()
async def _(param: Arparma):
    targets = []
    for t in param.query("target"):  # type: ignore
        if isinstance(t, At):
            targets.append(t.target)
        elif isinstance(t, Text):
            targets.append(t.text.strip())
        else:
            targets.append(str(t))

    tasks = [ChatManager.clear_history(t) for t in targets]
    results = await asyncio.gather(*tasks)
    counts = dict(zip(targets, results))

    result = [Text(f"• {t}: {count} 条数据\n") for t, count in counts.items()]
    summary = Text(f"已清理 {len(targets)} 个目标的聊天记录：\n")
    messages = [summary, *result]

    await clear_chat.send(UniMessage(messages), reply_to=True)
