from datetime import datetime, timedelta
from typing import ClassVar

from tortoise import fields
from tortoise.functions import Count
from tortoise.transactions import in_transaction

from zhenxun.services.ai.core.messages.models import LLMMessage
from zhenxun.services.db_context import Model


class ChatToolkitChatHistory(Model):
    id = fields.IntField(pk=True, generated=True, auto_increment=True)
    """自增id"""
    uid = fields.CharField(255, description="用户唯一标识符（类型+用户ID组合）")
    """用户id"""
    content = fields.JSONField(null=True)
    """LLMMessage内容模型"""
    create_time = fields.DatetimeField(auto_now_add=True)
    """创建时间"""

    class Meta:  # pyright: ignore [reportIncompatibleVariableOverride]
        table = "chat_toolkit_chat_history"
        table_description = "ai对话历史表"
        indexes: ClassVar = [("uid",)]

    @classmethod
    async def clear_history(cls, uid: str | None = None) -> int:
        async with in_transaction():
            return (
                await cls.filter(uid=uid).delete() if uid else await cls.all().delete()
            )

    @classmethod
    async def get_history(cls, uid: str) -> list[LLMMessage]:
        """
        获取指定用户的所有对话记录

        :param uid: 用户唯一标识符
        :return: 包含所有历史记录的列表
        """
        records = await cls.filter(uid=uid).order_by("id").all()
        return [LLMMessage(**dict(record.content)) for record in records]

    @classmethod
    async def get_user_list(cls) -> list[tuple[str, int]]:
        """获取所有用户的uid及其记录数量（元组列表形式）"""
        results = (
            await cls.all()
            .annotate(record_count=Count("id"))
            .group_by("uid")
            .values("uid", "record_count")
        )
        return [(item["uid"], item["record_count"]) for item in results]

    @classmethod
    async def delete_old_records(cls, days: int) -> int:
        """删除 n 天前的所有记录"""
        cutoff = datetime.now() - timedelta(days=days)

        async with in_transaction():
            deleted = await cls.filter(create_time__lt=cutoff).delete()

        return deleted
