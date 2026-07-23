from __future__ import annotations

from typing import ClassVar, Literal, TypedDict
from typing_extensions import Self

from nonebot_plugin_uninfo import Uninfo
from tortoise import fields

from zhenxun.services.db_context import Model

from .config import ChatConfig

MEMORY_TABLE = "chat_toolkit_memory"

MemoryScene = Literal["friend", "group"]


def make_scope(session: Uninfo) -> MemoryScope:
    return MemoryScope(
        self_id=session.self_id,
        scene="group" if session.scene.is_group else "friend",
        peer_id=session.scene.id if session.scene.is_group else session.user.id,
    )


class MemoryScope(TypedDict):
    self_id: str
    scene: MemoryScene
    peer_id: str


class MemoryStore(Model):
    id = fields.IntField(pk=True, generated=True, auto_increment=True)
    self_id = fields.CharField(255)
    scene = fields.CharField(255)
    peer_id = fields.CharField(255)
    content = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:  # pyright: ignore [reportIncompatibleVariableOverride]
        table = MEMORY_TABLE
        table_description = "chat_toolkit记忆列表"
        indexes: ClassVar = [("self_id", "scene", "peer_id", "created_at")]

    @classmethod
    async def recall(cls, scope: MemoryScope) -> list[Self]:
        """读取当前对话场景内最近的记忆，并按创建顺序返回"""
        rows = await (
            cls.scope_query(scope)
            .order_by("-created_at")
            .limit(ChatConfig.get("MEMORY_MAX_WINDOW"))
            .all()
        )
        return list(reversed(rows))

    @classmethod
    async def remember(cls, scope: MemoryScope, content: str) -> Self:
        """写入一条记忆，并清理同一场景下超出上限的旧记录"""
        trimmed = content.strip()
        if not trimmed:
            raise ValueError("memory content must not be empty")

        self_id, scene, peer_id = cls.normalize_scope(scope)
        row = await cls.create(
            self_id=self_id,
            scene=scene,
            peer_id=peer_id,
            content=trimmed,
        )
        await cls.prune(scope)
        return row

    @classmethod
    async def forget(cls, scope: MemoryScope, id: int) -> bool:
        """删除当前对话场景内指定 id 的记忆"""
        deleted_count = await cls.scope_query(scope).filter(id=id).delete()
        return deleted_count > 0

    @classmethod
    async def prune(cls, scope: MemoryScope) -> None:
        max_scope_count = ChatConfig.get("MEMORY_MAX_SCOPE_COUNT")
        if max_scope_count <= 0:
            return

        overflow = await (
            cls.scope_query(scope)
            .order_by("-created_at")
            .offset(max_scope_count)
            .values_list("id", flat=True)
        )
        if not overflow:
            return

        await cls.filter(id__in=list(overflow)).delete()

    @classmethod
    def scope_query(cls, scope: MemoryScope):
        self_id, scene, peer_id = cls.normalize_scope(scope)
        return cls.filter(self_id=self_id, scene=scene, peer_id=peer_id)

    @staticmethod
    def normalize_scope(scope: MemoryScope) -> tuple[str, MemoryScene, str]:
        scene = scope["scene"]
        if scene not in ("friend", "group"):
            raise ValueError("memory scene must be friend or group")
        return scope["self_id"], scene, scope["peer_id"]
