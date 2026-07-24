from nonebot.plugin import PluginMetadata

from zhenxun.configs.config import BotConfig
from zhenxun.configs.utils import PluginExtraData, RegisterConfig

from .handler import INIT as INIT

__plugin_meta__ = PluginMetadata(
    name="通用聊天AI",
    description="通用聊天ai插件，享受纯粹聊天",
    usage=f"""
    usage:
        与机器人聊天，{BotConfig.self_nickname}是可以看懂大家的表情包的...
    例如；
        @Bot 老婆老婆
        {BotConfig.self_nickname}宝宝
    """.strip(),
    extra=PluginExtraData(
        author="molanp",
        version="1.4",
        configs=[
            RegisterConfig(
                key="PROVIDER",
                value="",
                type=str,
                help="用于对话的语言模型，包含name/model",
                default_value="",
            ),
            RegisterConfig(
                key="VISION_PROVIDER",
                value="",
                type=str,
                help="用于图像识别的语言模型，若未指定则默认使用 PROVIDER 中指定的模型",
                default_value="",
            ),
            RegisterConfig(
                key="CONTEXT_WINDOW",
                value=10,
                type=int,
                help="上下文窗口大小，即提供给大模型的消息总数，默认值为 20",
                default_value=10,
            ),
            RegisterConfig(
                key="MAX_TOOL_CALLS_PER_TURN",
                value=3,
                type=int,
                help="单次对话中允许的最大工具迭代次数，0表示禁用工具调用",
                default_value=3,
            ),
            RegisterConfig(
                key="FACE_SEND_FREQUENCY",
                value=20,
                type=float,
                help="触发对话后，发送表情包的概率(百分比)",
                default_value=20,
            ),
            RegisterConfig(
                key="BLOCK_TIP",
                value="咱的脑回路是加密的，偷看要收硬币哦！",
                type=str,
                help="用户触发安全策略时的提示",
                default_value="咱的脑回路是加密的，偷看要收硬币哦！",
            ),
            RegisterConfig(
                key="MAX_TOKENS",
                value=4096,
                type=int,
                help="模型最大返回token数",
                default_value=4096,
            ),
            RegisterConfig(
                key="MEMORY_ENABLED",
                value=True,
                type=bool,
                help="是否启用记忆功能",
                default_value=True,
            ),
            RegisterConfig(
                key="MEMORY_MAX_WINDOW",
                value=20,
                type=int,
                help="记忆窗口大小，即在对话中最多注入的记忆条数，默认值为 20",
                default_value=20,
            ),
            RegisterConfig(
                key="MEMORY_MAX_SCOPE_COUNT",
                value=50,
                type=int,
                help="对于每个对话场景，最多允许的记忆条数，默认值为 50",
                default_value=50,
            ),
            RegisterConfig(
                key="MAX_FORWARD_DEPTH",
                value=0,
                type=int,
                help="若上下文中包含合并转发消息，则最多展开的层数，默认值为 0，即不展开",  # noqa: E501
                default_value=0,
            ),
        ],
    ).dict(),
)
