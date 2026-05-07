from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
import subprocess
from pathlib import Path
from typing import Any

from tavily import TavilyClient

from hiclaw.config import OPENAI_ALLOWED_TOOLS, TAVILY_API_KEY, TAVILY_MAX_RESULTS, TAVILY_SEARCH_DEPTH, WORKSPACE_DIR
from hiclaw.core.delivery import MessageSender, send_sender_text
from hiclaw.core.types import ConversationRef
from hiclaw.tasks.repository import cancel_scheduled_task_record, list_scheduled_task_records
from hiclaw.tasks.service import create_scheduled_task


@dataclass(slots=True)
class OpenAIToolContext:
    sender: MessageSender
    target_id: str | int
    channel: str | None = None
    session_scope: str | None = None


ALL_OPENAI_TOOLS: list[dict[str, Any]] = [
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
    {
        "type": "function",
        "function": {
            "name": "list_workspace_files",
            "description": "列出工作区中的文件和目录。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_workspace_file",
            "description": "读取工作区中的文本文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "工作区内的相对文件路径"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_workspace_file",
            "description": "在工作区中写入文本文件，不存在则创建。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "工作区内的相对文件路径"},
                    "content": {"type": "string", "description": "要写入的完整文本内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_workspace_file",
            "description": "在工作区文本文件里替换指定字符串。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "工作区内的相对文件路径"},
                    "old_string": {"type": "string", "description": "要替换的原始字符串"},
                    "new_string": {"type": "string", "description": "新的字符串"},
                    "replace_all": {"type": "boolean", "description": "是否替换全部匹配，默认 false"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob_workspace_files",
            "description": "按 glob 模式查找工作区文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "glob 模式，例如 src/**/*.py"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_workspace_content",
            "description": "按正则在工作区文件内容中搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "正则表达式"},
                    "include": {"type": "string", "description": "可选 glob 文件过滤，例如 *.py"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "执行 PowerShell 命令，适合多步骤文件操作和自动化任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的 PowerShell 命令"},
                    "workdir": {"type": "string", "description": "可选工作目录，相对于工作区"},
                    "timeout": {"type": "integer", "description": "超时时间（秒），默认 60"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "列出当前会话下所有待执行的定时任务。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_task",
            "description": "取消当前会话下指定 ID 的定时任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "要取消的任务 ID"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "为当前会话创建一条单次定时任务。run_at 支持 ISO 时间或 YYYY-MM-DD HH:MM:SS。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "任务内容"},
                    "run_at": {"type": "string", "description": "执行时间"},
                },
                "required": ["prompt", "run_at"],
            },
        },
    },
]


def build_openai_tools() -> list[dict[str, Any]]:
    allowed = {item.strip() for item in OPENAI_ALLOWED_TOOLS.split(",") if item.strip()}
    selected = ALL_OPENAI_TOOLS
    if allowed:
        selected = [tool for tool in ALL_OPENAI_TOOLS if tool.get("function", {}).get("name") in allowed]
    return [tool.copy() for tool in selected]


def _resolve_workspace_path(relative_path: str) -> Path:
    candidate = (WORKSPACE_DIR / relative_path).resolve()
    workspace_root = WORKSPACE_DIR.resolve()
    if candidate != workspace_root and workspace_root not in candidate.parents:
        raise ValueError("Path is outside the allowed workspace.")
    return candidate


def _resolve_workdir(relative_path: str | None) -> Path:
    if not relative_path:
        return WORKSPACE_DIR
    return _resolve_workspace_path(relative_path)


def _build_task_display_text(prompt: str) -> str:
    normalized = prompt.strip()
    if "任务内容：" in normalized:
        normalized = normalized.split("任务内容：", maxsplit=1)[-1].strip()
    return normalized or prompt.strip()


def _parse_tool_datetime(value: str) -> datetime:
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed


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

    if name == "list_workspace_files":
        items = sorted(path.name for path in WORKSPACE_DIR.iterdir())
        if not items:
            return "工作区为空。"
        return "工作区文件：\n" + "\n".join(f"- {item}" for item in items)

    if name == "read_workspace_file":
        relative_path = str(arguments.get("path") or "").strip()
        if not relative_path:
            return "错误：path 不能为空。"
        try:
            target = _resolve_workspace_path(relative_path)
        except ValueError as exc:
            return f"错误：{exc}"
        if not target.exists():
            return f"文件不存在：{relative_path}"
        if not target.is_file():
            return f"不是文件：{relative_path}"
        return target.read_text(encoding="utf-8", errors="replace")

    if name == "write_workspace_file":
        relative_path = str(arguments.get("path") or "").strip()
        content = str(arguments.get("content") or "")
        if not relative_path:
            return "错误：path 不能为空。"
        try:
            target = _resolve_workspace_path(relative_path)
        except ValueError as exc:
            return f"错误：{exc}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"文件已写入：{relative_path}"

    if name == "edit_workspace_file":
        relative_path = str(arguments.get("path") or "").strip()
        old_string = str(arguments.get("old_string") or "")
        new_string = str(arguments.get("new_string") or "")
        replace_all = bool(arguments.get("replace_all", False))
        if not relative_path or not old_string:
            return "错误：path 和 old_string 不能为空。"
        try:
            target = _resolve_workspace_path(relative_path)
        except ValueError as exc:
            return f"错误：{exc}"
        if not target.exists() or not target.is_file():
            return f"文件不存在：{relative_path}"
        content = target.read_text(encoding="utf-8", errors="replace")
        if old_string not in content:
            return "错误：未找到要替换的文本。"
        updated = content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1)
        target.write_text(updated, encoding="utf-8")
        return f"文件已更新：{relative_path}"

    if name == "glob_workspace_files":
        pattern = str(arguments.get("pattern") or "").strip()
        if not pattern:
            return "错误：pattern 不能为空。"
        matches = sorted({str(path.relative_to(WORKSPACE_DIR)) for path in WORKSPACE_DIR.glob(pattern)})
        if not matches:
            return "没有匹配文件。"
        return "\n".join(matches[:200])

    if name == "grep_workspace_content":
        pattern = str(arguments.get("pattern") or "").strip()
        include = str(arguments.get("include") or "**/*").strip() or "**/*"
        if not pattern:
            return "错误：pattern 不能为空。"
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return f"错误：无效正则：{exc}"
        matches: list[str] = []
        for path in WORKSPACE_DIR.glob(include):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    matches.append(f"{path.relative_to(WORKSPACE_DIR)}:{line_no}: {line[:300]}")
                    if len(matches) >= 200:
                        return "\n".join(matches)
        return "\n".join(matches) if matches else "没有匹配内容。"

    if name == "bash":
        command = str(arguments.get("command") or "").strip()
        if not command:
            return "错误：command 不能为空。"
        timeout = int(arguments.get("timeout") or 60)
        try:
            workdir = _resolve_workdir(str(arguments.get("workdir") or "").strip() or None)
        except ValueError as exc:
            return f"错误：{exc}"
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            return f"错误：命令执行超时（{timeout} 秒）。"
        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        parts = [f"退出码: {result.returncode}"]
        if output:
            parts.append(f"STDOUT:\n{output[:6000]}")
        if error:
            parts.append(f"STDERR:\n{error[:6000]}")
        return "\n\n".join(parts)

    if name == "list_tasks":
        if not ctx.channel:
            return "错误：当前通道上下文缺失，无法查看任务。"
        tasks = await list_scheduled_task_records(channel=ctx.channel, target_id=str(ctx.target_id))
        if not tasks:
            return "当前没有待执行的定时任务。"
        lines = ["当前定时任务："]
        for index, task in enumerate(tasks, 1):
            task_id = task.get("id", "unknown")
            prompt = _build_task_display_text(task.get("prompt", "unknown"))
            next_run = task.get("next_run", "unknown")
            schedule_type = task.get("schedule_type", "once")
            lines.append(f"{index}. {next_run} | {schedule_type} | {prompt} | ID={task_id}")
        return "\n".join(lines)

    if name == "cancel_task":
        if not ctx.channel:
            return "错误：当前通道上下文缺失，无法取消任务。"
        task_id = str(arguments.get("task_id") or "").strip()
        if not task_id:
            return "错误：task_id 不能为空。"
        success = await cancel_scheduled_task_record(task_id, channel=ctx.channel, target_id=str(ctx.target_id))
        return f"任务 {task_id} 已取消。" if success else f"未找到任务 {task_id}。"

    if name == "create_task":
        if not ctx.channel or not ctx.session_scope:
            return "错误：当前会话上下文缺失，无法创建任务。"
        prompt = str(arguments.get("prompt") or "").strip()
        if not prompt:
            return "错误：prompt 不能为空。"
        try:
            run_at = _parse_tool_datetime(str(arguments.get("run_at") or ""))
        except ValueError as exc:
            return f"错误：run_at 格式无效：{exc}"
        conversation = ConversationRef(channel=ctx.channel, target_id=str(ctx.target_id), session_scope=ctx.session_scope)
        task_id = await create_scheduled_task(conversation=conversation, prompt=prompt, run_at=run_at)
        return f"任务已创建。ID: {task_id}，执行时间: {run_at.astimezone().strftime('%Y-%m-%d %H:%M:%S')}"

    return f"错误：未知工具 {name}。"
