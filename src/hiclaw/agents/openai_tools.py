from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tavily import TavilyClient

from hiclaw.config import TAVILY_API_KEY, TAVILY_MAX_RESULTS, TAVILY_SEARCH_DEPTH
from hiclaw.core.delivery import MessageSender, send_sender_text


@dataclass(slots=True)
class OpenAIToolContext:
    sender: MessageSender
    target_id: str | int
    channel: str | None = None
    session_scope: str | None = None


MINIMAL_OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前服务器本地时间。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "使用 Tavily 搜索互联网信息，返回结果摘要和 URL。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "向当前会话额外发送一条消息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "消息内容"},
                },
                "required": ["text"],
            },
        },
    },
]


def build_openai_tools() -> list[dict[str, Any]]:
    return [tool.copy() for tool in MINIMAL_OPENAI_TOOLS]


async def execute_openai_tool(name: str, arguments: dict[str, Any], ctx: OpenAIToolContext) -> str:
    if name == "get_current_time":
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"当前时间：{now}"

    if name == "web_search":
        query = str(arguments.get("query") or "").strip()
        if not query:
            return "错误：query 不能为空。"
        if not TAVILY_API_KEY:
            return "错误：Tavily API key 未配置。"
        try:
            client = TavilyClient(api_key=TAVILY_API_KEY)
            response = client.search(query=query, search_depth=TAVILY_SEARCH_DEPTH, max_results=TAVILY_MAX_RESULTS)
        except Exception as exc:
            return f"搜索失败：{exc}"

        results = response.get("results", [])
        if not results:
            return f"未找到关于“{query}”的结果。"

        lines: list[str] = []
        for index, result in enumerate(results, 1):
            title = result.get("title", "")
            url = result.get("url", "")
            content = (result.get("content", "") or "")[:300]
            lines.append(f"{index}. {title}\n{url}\n{content}")
        return "\n\n".join(lines)

    if name == "send_message":
        text = str(arguments.get("text") or "").strip()
        if not text:
            return "错误：text 不能为空。"
        await send_sender_text(ctx.sender, ctx.target_id, text)
        return "消息已发送。"

    return f"错误：未知工具 {name}。"
