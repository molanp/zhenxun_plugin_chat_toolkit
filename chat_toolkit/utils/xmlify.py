"""将 OneBot v11 历史消息序列化为 XML，供 LLM 上下文使用。

对应 milky 插件 xmlify.ts。
消息段通过 nonebot_plugin_alconna 的 UniMessage 统一解析。

入参为 onebotv11 历史消息 dict（或 get_*_msg_history 的返回值）。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from html import escape
from typing import Any
from xml.etree.ElementTree import Element

from nonebot.adapters import Bot, Message
from nonebot.adapters.onebot.v11 import Message as OB11Message
from nonebot.adapters.onebot.v11 import MessageSegment as OB11MessageSegment
from nonebot_plugin_alconna import (
    At,
    AtAll,
    Audio,
    CustomNode,
    Emoji,
    File,
    Hyper,
    Image,
    Reference,
    RefNode,
    Reply,
    Segment,
    Text,
    UniMessage,
    Video,
    Voice,
)


@dataclass
class ResourceIndex:
    image: int = 0
    record: int = 0
    video: int = 0


@dataclass
class XmlifyOptions:
    max_forward_depth: int = 0
    indent: str = "  "
    resource_index: ResourceIndex | None = None


@dataclass
class XmlifyContext:
    xml_content: str
    resources: dict[str, dict[str, str]] = field(default_factory=dict)
    files: dict[str, dict[str, Any]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# OneBot v11 历史消息归一化
# ---------------------------------------------------------------------------


def normalize_history_messages(
    data: list[dict[str, Any]] | dict[str, Any] | Iterable[Any],
) -> list[dict[str, Any]]:
    """把 get_group/friend_msg_history 的返回值归一成消息 dict 列表。

    支持：
    - {"messages": [...]}
    - [...]
    - 单条消息 dict
    - 元素本身是 pydantic / 带 model_dump 的对象
    """
    if data is None:
        return []

    if isinstance(data, dict):
        if "messages" in data and isinstance(data["messages"], list):
            raw_list = data["messages"]
        elif "message" in data or "sender" in data or "message_id" in data:
            raw_list = [data]
        else:
            # 兜底：dict 本身不可识别，当空
            raw_list = []
    elif isinstance(data, list):
        raw_list = data
    else:
        raw_list = list(data)

    result: list[dict[str, Any]] = []
    for item in raw_list:
        if item is None:
            continue
        if isinstance(item, dict):
            result.append(item)
        elif hasattr(item, "model_dump"):
            result.append(item.model_dump())
        elif hasattr(item, "dict"):
            result.append(item.dict())
        else:
            # 尝试 __dict__
            try:
                result.append(dict(item))
            except Exception:
                continue
    return result


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    try:
        return dict(value)
    except Exception:
        return {}


def _to_ob11_message(message_field: Any) -> OB11Message:
    """把 onebotv11 的 message 字段转成 Message。"""
    if isinstance(message_field, OB11Message):
        return message_field
    if message_field is None:
        return OB11Message()
    if isinstance(message_field, str):
        return OB11Message(message_field)
    if isinstance(message_field, OB11MessageSegment):
        return OB11Message(message_field)

    if isinstance(message_field, list):
        segs: list[OB11MessageSegment] = []
        for item in message_field:
            if isinstance(item, OB11MessageSegment):
                segs.append(item)
            elif isinstance(item, dict):
                segs.append(
                    OB11MessageSegment(
                        str(item.get("type") or "text"),
                        dict(item.get("data") or {}),
                    )
                )
            elif isinstance(item, str):
                segs.append(OB11MessageSegment.text(item))
            else:
                segs.append(OB11MessageSegment.text(str(item)))
        return OB11Message(segs)

    return OB11Message(str(message_field))


def _to_uni_message(message_field: Any, bot: Bot | None) -> UniMessage:
    """把 onebot 消息体转成 UniMessage。"""
    if isinstance(message_field, UniMessage):
        return message_field

    # 其它适配器 Message（非 ob11），直接交给 alconna
    if isinstance(message_field, Message) and not isinstance(
        message_field, OB11Message
    ):
        if bot is not None:
            return UniMessage.of(message_field, bot=bot)
        return UniMessage.of(message_field, adapter="OneBot V11")

    ob_msg = _to_ob11_message(message_field)
    if bot is not None:
        return UniMessage.of(ob_msg, bot=bot)
    # 无 bot 时显式指定适配器，避免依赖 current_bot
    return UniMessage.of(ob_msg, adapter="OneBot V11")


def _scene_and_peer(msg: dict[str, Any]) -> tuple[str, str]:
    message_type = str(msg.get("message_type") or "").lower()
    if message_type == "group" or msg.get("group_id") is not None:
        return "group", str(msg.get("group_id") or "")
    if message_type in {"private", "friend"} or msg.get("user_id") is not None:
        sender = _as_dict(msg.get("sender"))
        peer = msg.get("user_id") or sender.get("user_id") or ""
        return "friend", str(peer)
    # 兜底
    if msg.get("group_id") is not None:
        return "group", str(msg["group_id"])
    sender = _as_dict(msg.get("sender"))
    return "friend", str(msg.get("user_id") or sender.get("user_id") or "")


def _sender_id(msg: dict[str, Any]) -> str:
    sender = _as_dict(msg.get("sender"))
    return str(msg.get("user_id") or sender.get("user_id") or "")


def _message_seq(msg: dict[str, Any]) -> str:
    return next(
        (
            str(msg[key])
            for key in ("message_id", "message_seq", "real_id", "id")
            if msg.get(key) is not None
        ),
        "",
    )


def _message_time(msg: dict[str, Any]) -> str:
    t = msg.get("time")
    return str(t) if t is not None else ""


# ---------------------------------------------------------------------------
# XML 节点构建
# ---------------------------------------------------------------------------


def _set_attrs(element: Element, values: dict[str, Any]) -> None:
    for key, value in values.items():
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            element.set(key, "true" if value else "false")
        elif isinstance(value, (str, int, float)):
            element.set(key, str(value))


def _build_attributed_element(name: str, values: dict[str, Any]) -> Element:
    element = Element(name)
    _set_attrs(element, values)
    return element


def _build_tagged_text_node(
    tag: str,
    text: str | None,
    attrs: dict[str, Any] | None = None,
) -> Element:
    element = _build_attributed_element(tag, attrs or {})
    if text is not None:
        element.text = str(text)
    return element


def _build_plain_node(name: str, values: dict[str, Any]) -> Element:
    element = Element(name)
    for key, value in values.items():
        if value is None or value == "":
            continue
        if isinstance(value, dict):
            element.append(_build_plain_node(key, value))
        elif isinstance(value, (str, int, float, bool)):
            child = Element(key)
            if value is True:
                child.text = "true"
            elif value is False:
                child.text = "false"
            else:
                child.text = str(value)
            element.append(child)
    return element


def _stringify_segments(segments: Iterable[Any]) -> str:
    parts: list[str] = []
    for segment in segments:
        if isinstance(segment, str):
            parts.append(segment)
        elif isinstance(segment, Text):
            parts.append(segment.text)
        elif isinstance(segment, Segment):
            parts.append(f"[{segment.type}]")
        else:
            parts.append(str(segment))
    return "".join(parts)


def _media_url(segment: Image | Voice | Audio | Video | File) -> str:
    if segment.url:
        return segment.url
    return str(segment.path) if segment.path is not None else segment.id or ""


def _reply_text(reply: Reply) -> str:
    msg = reply.msg
    if msg is None:
        return ""
    if isinstance(msg, str):
        return msg
    try:
        return _stringify_segments(list(msg))  # type: ignore[arg-type]
    except TypeError:
        return str(msg)


def _reply_attrs(reply: Reply) -> dict[str, Any]:
    attrs: dict[str, Any] = {"message_seq": reply.id}
    origin = reply.origin
    if origin is None:
        return attrs

    # onebot v11 event.reply
    sender = getattr(origin, "sender", None)
    if sender is not None:
        user_id = getattr(sender, "user_id", None)
        if user_id is not None:
            attrs["sender_id"] = user_id
    if getattr(origin, "time", None) is not None:
        attrs["time"] = origin.time
    if getattr(origin, "message_id", None) is not None:
        attrs["message_seq"] = origin.message_id

    data = getattr(origin, "data", None)
    if isinstance(data, dict):
        for src, dst in (
            ("message_seq", "message_seq"),
            ("message_id", "message_seq"),
            ("sender_id", "sender_id"),
            ("time", "time"),
        ):
            if data.get(src) is not None:
                attrs[dst] = data[src]
    return attrs


class _XmlifyBuilder:
    def __init__(self, options: XmlifyOptions | None = None) -> None:
        self.options = options or XmlifyOptions()
        self.resource_index = self.options.resource_index or ResourceIndex()
        self.resources: dict[str, dict[str, str]] = {}
        self.files: dict[str, dict[str, Any]] = {}

    def _new_resource_key(self, kind: str) -> str:
        if kind == "image":
            self.resource_index.image += 1
            return f"image{self.resource_index.image}"
        if kind == "record":
            self.resource_index.record += 1
            return f"record{self.resource_index.record}"
        if kind == "video":
            self.resource_index.video += 1
            return f"video{self.resource_index.video}"
        raise ValueError(f"unknown resource type: {kind}")

    def build_element_from_segment(
        self,
        segment: Segment,
        forward_depth: int = 1,
    ) -> Element | None:
        if isinstance(segment, Text):
            return _build_tagged_text_node("text", segment.text)

        if isinstance(segment, At):
            display = segment.display or f"@{segment.target}"
            return _build_tagged_text_node(
                "mention",
                display,
                {"user_id": segment.target},
            )

        if isinstance(segment, AtAll):
            return _build_tagged_text_node("mention", "@全体成员")

        if isinstance(segment, Emoji):
            attrs: dict[str, Any] = {"id": segment.id}
            if segment.name:
                attrs["name"] = segment.name
            if segment.url:
                attrs["url"] = segment.url
            if segment.name:
                return _build_tagged_text_node("face", segment.name, attrs)
            return _build_attributed_element("face", attrs)

        if isinstance(segment, Reply):
            return _build_tagged_text_node(
                "reply",
                _reply_text(segment),
                _reply_attrs(segment),
            )

        if isinstance(segment, Image):
            return self._extracted_from_build_element_from_segment_38(segment)
        if isinstance(segment, (Voice, Audio)):
            attrs = self._extracted_from_build_element_from_segment_53(
                "record", segment
            )
            duration = getattr(segment, "duration", None)
            if duration is not None:
                attrs["duration"] = duration
            return _build_attributed_element("record", attrs)

        if isinstance(segment, Video):
            attrs = self._extracted_from_build_element_from_segment_53("video", segment)
            if segment.duration is not None:
                attrs["duration"] = segment.duration
            return _build_attributed_element("video", attrs)

        if isinstance(segment, File):
            return self._extracted_from_build_element_from_segment_70(segment)
        if isinstance(segment, Reference):
            return self._build_forward(segment, forward_depth)

        if isinstance(segment, Hyper):
            text = segment.raw or ""
            if not text and segment.content is not None:
                import json

                try:
                    text = json.dumps(segment.content, ensure_ascii=False)
                except (TypeError, ValueError):
                    text = str(segment.content)
            return _build_tagged_text_node(
                "hyper",
                text,
                {"format": segment.format},
            )

        return None

    # TODO Rename this here and in `build_element_from_segment`
    def _extracted_from_build_element_from_segment_70(self, segment):
        file_name = segment.name or "file.bin"
        self.files[file_name] = {
            "file_name": file_name,
            "id": segment.id,
            "url": segment.url,
            "path": str(segment.path) if segment.path is not None else None,
        }
        attrs = {}
        size = getattr(segment, "size", None)
        if size is not None:
            attrs["size"] = size
        return _build_tagged_text_node("file", file_name, attrs)

    # TODO Rename this here and in `build_element_from_segment`
    def _extracted_from_build_element_from_segment_38(self, segment):
        resource_key = self._new_resource_key("image")
        self.resources[resource_key] = {"url": _media_url(segment)}
        attrs: dict[str, Any] = {"id": resource_key}
        if segment.width is not None:
            attrs["width"] = segment.width
        if segment.height is not None:
            attrs["height"] = segment.height
        if segment.sticker:
            attrs["sticker"] = True
        summary = ""
        if segment.name and segment.name != Image.__default_name__:
            summary = segment.name
        return _build_tagged_text_node("image", summary, attrs)

    # TODO Rename this here and in `build_element_from_segment`
    def _extracted_from_build_element_from_segment_53(self, arg0, segment):
        resource_key = self._new_resource_key(arg0)
        self.resources[resource_key] = {"url": _media_url(segment)}
        return {"id": resource_key}

    def _build_forward(self, segment: Reference, forward_depth: int) -> Element:
        max_depth = self.options.max_forward_depth
        title = segment.id or ""

        if max_depth == 0:
            return _build_tagged_text_node(
                "forward",
                "(Forwarded message)",
                {"title": title} if title else None,
            )

        if forward_depth > max_depth:
            return _build_tagged_text_node(
                "forward",
                "(Too deeply nested)",
                {"title": title} if title else None,
            )

        attrs: dict[str, Any] = {"depth": forward_depth}
        if title:
            attrs["title"] = title
        forward_node = _build_attributed_element("forward", attrs)

        for node in segment.children:
            if isinstance(node, CustomNode):
                node_attrs: dict[str, Any] = {
                    "sender_name": node.name,
                    "time": int(node.time.timestamp()),
                }
                if node.uid:
                    node_attrs["sender_id"] = node.uid
                content_node = _build_attributed_element("node", node_attrs)
                content = node.content
                if isinstance(content, str):
                    content_node.append(_build_tagged_text_node("text", content))
                else:
                    for child_seg in content:
                        if isinstance(child_seg, Segment):
                            child_el = self.build_element_from_segment(
                                child_seg, forward_depth + 1
                            )
                            if child_el is not None:
                                content_node.append(child_el)
                forward_node.append(content_node)
            elif isinstance(node, RefNode):
                ref_attrs: dict[str, Any] = {"id": node.id}
                if node.context:
                    ref_attrs["context"] = node.context
                forward_node.append(
                    _build_tagged_text_node("node", "(Referenced message)", ref_attrs)
                )

        if len(forward_node) == 0:
            forward_node.text = "(Forwarded message)"
        return forward_node

    def build_message_element(
        self,
        msg: dict[str, Any],
        bot: Bot | None,
        *,
        in_thread: bool = False,
    ) -> Element:
        scene, peer_id = _scene_and_peer(msg)
        seq = _message_seq(msg)
        sender_id = _sender_id(msg)
        time_val = _message_time(msg)

        if in_thread:
            root_attrs = {
                "seq": seq,
                "sender_id": sender_id,
                "time": time_val,
            }
        else:
            root_attrs = {
                "scene": scene,
                "peer_id": peer_id,
                "seq": seq,
                "sender_id": sender_id,
                "time": time_val,
            }

        root = _build_attributed_element("message", root_attrs)
        content_node = Element("content")

        uni = _to_uni_message(msg.get("message"), bot)
        for segment in uni:
            if not isinstance(segment, Segment):
                continue
            element = self.build_element_from_segment(segment)
            if element is not None:
                content_node.append(element)
        root.append(content_node)

        sender = _as_dict(msg.get("sender"))
        if scene == "friend":
            root.append(
                _build_plain_node(
                    "friend",
                    {
                        "user_id": sender.get("user_id") or msg.get("user_id") or "",
                        "nickname": sender.get("nickname") or "",
                        "remark": sender.get("remark") or "",
                    },
                )
            )
        else:
            root.append(
                _build_plain_node(
                    "group",
                    {
                        "group_id": msg.get("group_id") or peer_id,
                        "group_name": msg.get("group_name") or "",
                    },
                )
            )
            root.append(
                _build_plain_node(
                    "group_member",
                    {
                        "user_id": sender.get("user_id") or msg.get("user_id") or "",
                        "card": sender.get("card") or "",
                        "nickname": sender.get("nickname") or "",
                        "role": sender.get("role") or "",
                    },
                )
            )

        return root


def _format_xml(element: Element, indent: str = "  ") -> str:
    """格式化 XML：缩进 + collapseContent（纯文本节点不换行）。"""

    def _walk(node: Element, level: int) -> list[str]:
        pad = indent * level
        attrs = "".join(
            f' {k}="{escape(v, quote=True)}"' for k, v in node.attrib.items()
        )
        children = list(node)
        text = (node.text or "").strip() if node.text else ""

        if not children:
            if text:
                return [f"{pad}<{node.tag}{attrs}>{escape(text)}</{node.tag}>"]
            return [f"{pad}<{node.tag}{attrs} />"]

        lines = [f"{pad}<{node.tag}{attrs}>"]
        if text:
            lines.append(f"{pad}{indent}{escape(text)}")
        for child in children:
            lines.extend(_walk(child, level + 1))
            child_tail = (child.tail or "").strip() if child.tail else ""
            if child_tail:
                lines.append(f"{pad}{indent}{escape(child_tail)}")
        lines.append(f"{pad}</{node.tag}>")
        return lines

    return "\n".join(_walk(element, 0))


# ---------------------------------------------------------------------------
# 公开 API（对齐 TS）
# ---------------------------------------------------------------------------


def xmlify_to_element(
    message: dict[str, Any],
    bot: Bot | None = None,
    options: XmlifyOptions | None = None,
    *,
    in_thread: bool = False,
) -> tuple[Element, dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    """单条 onebotv11 消息 dict -> XML Element + resources/files。"""
    builder = _XmlifyBuilder(options)
    node = builder.build_message_element(message, bot, in_thread=in_thread)
    return node, builder.resources, builder.files


def xmlify_sync(
    message: dict[str, Any],
    bot: Bot | None = None,
    options: XmlifyOptions | None = None,
) -> XmlifyContext:
    """对应 TS xmlify（单条消息）。"""
    opts = options or XmlifyOptions()
    node, resources, files = xmlify_to_element(message, bot, opts)
    return XmlifyContext(
        xml_content=_format_xml(node, opts.indent),
        resources=resources,
        files=files,
    )


async def xmlify(
    message: dict[str, Any],
    bot: Bot | None = None,
    options: XmlifyOptions | None = None,
) -> XmlifyContext:
    """对应 TS xmlify（async 包装，当前无额外 IO）。"""
    return xmlify_sync(message, bot, options)


def xmlify_thread_sync(
    messages: list[dict[str, Any]] | dict[str, Any] | Iterable[Any],
    bot: Bot | None = None,
    options: XmlifyOptions | None = None,
) -> XmlifyContext:
    """对应 TS xmlifyThread。

    Parameters
    ----------
    messages:
        - get_group_msg_history / get_friend_msg_history 的原始返回
          例如 ``{"messages": [ {...}, ... ]}``
        - 或消息 dict 列表
    bot:
        用于 UniMessage.of 解析消息段，建议传入当前 bot
    """
    msg_list = normalize_history_messages(messages)
    if not msg_list:
        raise ValueError("No messages provided for xmlify_thread")

    opts = options or XmlifyOptions()
    resource_index = opts.resource_index or ResourceIndex()
    shared_opts = XmlifyOptions(
        max_forward_depth=opts.max_forward_depth,
        indent=opts.indent,
        resource_index=resource_index,
    )

    first = msg_list[0]
    scene, peer_id = _scene_and_peer(first)
    thread_node = _build_attributed_element(
        "thread",
        {"scene": scene, "peer_id": peer_id},
    )

    resources: dict[str, dict[str, str]] = {}
    files: dict[str, dict[str, Any]] = {}

    for msg in msg_list:
        node, msg_resources, msg_files = xmlify_to_element(
            msg,
            bot,
            shared_opts,
            in_thread=True,
        )
        thread_node.append(node)
        resources.update(msg_resources)
        files.update(msg_files)

    return XmlifyContext(
        xml_content=_format_xml(thread_node, opts.indent),
        resources=resources,
        files=files,
    )


async def xmlify_thread(
    messages: list[dict[str, Any]] | dict[str, Any] | Iterable[Any],
    bot: Bot | None = None,
    options: XmlifyOptions | None = None,
) -> XmlifyContext:
    """对应 TS xmlifyThread（async 包装）。"""
    return xmlify_thread_sync(messages, bot, options)


__all__ = [
    "ResourceIndex",
    "XmlifyContext",
    "XmlifyOptions",
    "normalize_history_messages",
    "xmlify",
    "xmlify_sync",
    "xmlify_thread",
    "xmlify_thread_sync",
    "xmlify_to_element",
]
