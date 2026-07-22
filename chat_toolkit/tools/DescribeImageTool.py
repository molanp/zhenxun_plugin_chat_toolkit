from typing import ClassVar

from zhenxun.plugins.chat_toolkit.config import ChatConfig
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
            "image_url": {
                "type": "string",
                "description": "图片的 url",
            },
            "question": {
                "type": "string",
                "description": "对图片提出的问题",
            },
        },
        "required": ["image_url"],
    }

    async def func(self, image_url: str, question: str | None = None) -> str:
        try:
            question = question or "请描述这张图片的内容。"
            result = await chat(
                message=LLMMessage.user(
                    content=[
                        BaseContentPart.image_url_part(
                            url=image_url.replace("https://", "http://")
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
