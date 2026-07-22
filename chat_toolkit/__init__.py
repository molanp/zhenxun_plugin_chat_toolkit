from nonebot.plugin import PluginMetadata

from zhenxun.configs.config import BotConfig
from zhenxun.configs.utils import PluginExtraData, RegisterConfig

from .handler import INIT as INIT

__plugin_meta__ = PluginMetadata(
    name="通用聊天AI",
    description="通用聊天ai插件，享受纯粹聊天",
    usage=f"""
    usage:
        清理我的会话:   用于清理你与AI的聊天记录
        与机器人聊天，{BotConfig.self_nickname}是可以看懂大家的表情包的...
    例如；
        @Bot 抱抱
        {BotConfig.self_nickname}老婆
    """.strip(),
    extra=PluginExtraData(
        author="molanp",
        version="1.2",
        superuser_help="""
        超级管理员额外命令
        格式:
            清理会话 @user / uid : 用于清理指定用户的会话记录,支持多个目标
            清理全部会话: 清理Bot缓存的全部会话记录
        """,
        configs=[
            RegisterConfig(
                key="PROVIDER",
                value="",
                type=str,
                help="文字ai模块的提供者，包含name/model",
                default_value="",
            ),
            RegisterConfig(
                key="VISION_PROVIDER",
                value="",
                type=str,
                help="图像理解ai模块的提供者，包含name/model",
                default_value="",
            ),
            RegisterConfig(
                key="CONTEXT_WINDOW",
                value=10,
                type=int,
                help="单次对话参考上下文数量",
                default_value=10,
            ),
            RegisterConfig(
                key="EXPIRE_DAY",
                value=3,
                type=int,
                help="用户对话记录保存时间(天), -1表示永久保存",
                default_value=3,
            ),
            RegisterConfig(
                key="TEXT_MAX_SPLIT",
                value=3,
                type=int,
                help="单次对话消息最大分割段数, 0表示无限分割, -1表示不分割",
                default_value=3,
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
        ],
    ).dict(),
)
