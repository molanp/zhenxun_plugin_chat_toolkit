from typing import Any, ClassVar

from zhenxun.services.ai.core.messages import ChatRequest, LLMMessage
from zhenxun.services.ai.core.options import GenerationConfig
from zhenxun.services.ai.llm.engine.router import LLMOrchestrator
from zhenxun.services.ai.tools.providers.builtin.native import Native

from ..config import ChatConfig
from .AbstractTool import AbstractTool


class WebSearchTool(AbstractTool):
    name = "external_web_search"
    description = (
        "一次性检索网页并返回可引用的事实和来源。"
        "每轮对话只能调用一次，应将需要查询的内容合并成一个完整问题；"
        "获得结果后必须直接回答用户，不要继续搜索。"
    )
    max_calls_per_run = 1
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "完整、明确的搜索问题，包含必要的时间或地域条件",
            }
        },
        "required": ["query"],
    }

    @staticmethod
    def _format_sources(metadata: Any) -> str:
        attributions = getattr(metadata, "grounding_attributions", None) or []
        sources: list[str] = []
        seen: set[str] = set()
        for item in attributions:
            uri = getattr(item, "uri", None)
            if not uri or uri in seen:
                continue
            seen.add(uri)
            title = getattr(item, "title", None)
            sources.append(f"- {title}: {uri}" if title else f"- {uri}")
        return "\n".join(sources)

    async def func(self, query: str) -> str:
        provider = ChatConfig.get("SEARCH_PROVIDER") or ChatConfig.get("PROVIDER")
        config = GenerationConfig()
        config.common.max_tokens = int(ChatConfig.get("MAX_TOKENS"))
        request = ChatRequest(
            messages=[
                LLMMessage.system(
                    "你是联网检索工具。必须使用网页搜索核验用户的问题，"
                    "优先采用可靠且较新的来源。直接给出可供另一个模型引用的"
                    "简洁事实结论，并附上来源链接；不要进行角色扮演。"
                    "如果没有找到可靠信息，明确说明，不要猜测。"
                ),
                LLMMessage.user(query),
            ],
            tools=[Native.web_search()],
            config=config,
        )
        result = await LLMOrchestrator.invoke(
            request,
            model_name=provider,
            task="chat",
            override_config=config,
        )
        if not result.text:
            search_result = "联网搜索没有返回可用结果"
        else:
            sources = self._format_sources(result.grounding_metadata)
            search_result = (
                f"{result.text}\n\n来源：\n{sources}" if sources else result.text
            )
        return (
            f"{search_result}\n\n"
            "[本轮网页搜索已经完成。请使用以上结果直接回答用户，"
            "不要再次调用网页搜索工具。]"
        )
