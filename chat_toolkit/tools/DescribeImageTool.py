from typing import ClassVar

from nonebot_plugin_uninfo import Uninfo
from ..config import ChatConfig, ThreadCache
from zhenxun.services.ai.core.messages.models import LLMMessage
from zhenxun.services.ai.core.messages.parts import BaseContentPart
from zhenxun.services.ai.llm import chat
from zhenxun.services.log import logger

from .AbstractTool import AbstractTool


class DescribeImageTool(AbstractTool):
    name = "describe_image"
    description = "描述图片内容，或对图片内容提出特定的问题。"

    parameters: ClassVar = {
        "type": "object",
        "properties": {
            "image_id": {
                "type": "string",
                "description": "图片的 id",
            },
            "question": {
                "type": "string",
                "description": "对图片提出的问题",
            },
        },
        "required": ["image_id"],
    }

    async def func(
        self, session: Uninfo, image_id: str, question: str | None = None
    ) -> str:
        image_info = ThreadCache.get(session.user.id, image_id)
        if not image_info:
            raise ValueError(f"找不到 id 为 {image_id} 的图片资源。")
        try:
            question = question or "请描述这张图片的内容。"
            result = await chat(
                message=LLMMessage.user(
                    content=[
                        BaseContentPart.image_url_part(
                            url=image_info["url"].replace("https://", "http://")
                        ),
                        BaseContentPart.text_part(text=question),
                    ],
                ),
                model=ChatConfig.get("VISION_PROVIDER"),
            )
            return result.text
        except Exception as e:
            logger.error("描述图片失败", e=e)
            return "描述图片失败"
