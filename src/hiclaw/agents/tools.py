from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from tavily import TavilyClient

from hiclaw.config import TAVILY_API_KEY, TAVILY_MAX_RESULTS, TAVILY_SEARCH_DEPTH, WORKSPACE_DIR
from hiclaw.core.delivery import MessageSender, send_sender_file, send_sender_text
from hiclaw.core.types import ConversationRef
from hiclaw.tasks.service import create_scheduled_task
from hiclaw.tasks.repository import list_scheduled_task_records, cancel_scheduled_task_record


def resolve_workspace_path(relative_path: str) -> Path:
    """把相对路径限制在工作区内，避免工具访问工作区之外的文件。"""

    candidate = (WORKSPACE_DIR / relative_path).resolve()
    workspace_root = WORKSPACE_DIR.resolve()

    if candidate != workspace_root and workspace_root not in candidate.parents:
        raise ValueError("Path is outside the allowed workspace.")

    return candidate


@tool("get_current_time", "获取当前服务器本地时间。", {})
async def get_current_time(_: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "content": [
            {
                "type": "text",
                "text": f"Current local time is: {now}",
            }
        ]
    }


@tool("list_workspace_files", "列出工作区中的文件和目录。", {})
async def list_workspace_files(_: dict[str, Any]) -> dict[str, Any]:
    items = sorted(path.name for path in WORKSPACE_DIR.iterdir())
    text = "\n".join(f"- {name}" for name in items) if items else "(workspace is empty)"
    return {
        "content": [
            {
                "type": "text",
                "text": f"Workspace directory: {WORKSPACE_DIR}\n{text}",
            }
        ]
    }


@tool("read_workspace_file", "读取工作区中的文本文件。", {"path": str})
async def read_workspace_file(args: dict[str, Any]) -> dict[str, Any]:
    relative_path = args["path"]

    try:
        target = resolve_workspace_path(relative_path)
    except ValueError as exc:
        return {
            "content": [{"type": "text", "text": str(exc)}],
            "is_error": True,
        }

    if not target.exists():
        return {
            "content": [{"type": "text", "text": f"File not found: {relative_path}"}],
            "is_error": True,
        }

    if not target.is_file():
        return {
            "content": [{"type": "text", "text": f"Not a file: {relative_path}"}],
            "is_error": True,
        }

    content = target.read_text(encoding="utf-8", errors="replace")
    return {
        "content": [
            {
                "type": "text",
                "text": f"File: {relative_path}\n\n{content}",
            }
        ]
    }


@tool("web_search", "使用 Tavily 搜索引擎搜索互联网，返回结果摘要和 URL。", {"query": str})
async def web_search(args: dict[str, Any]) -> dict[str, Any]:
    if not TAVILY_API_KEY:
        return {
            "content": [{"type": "text", "text": "Tavily API key is not configured. Set TAVILY_API_KEY in .env."}],
            "is_error": True,
        }

    query = args["query"]
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=query,
            search_depth=TAVILY_SEARCH_DEPTH,
            max_results=TAVILY_MAX_RESULTS,
        )
    except Exception as exc:
        return {
            "content": [{"type": "text", "text": f"Search failed: {exc}"}],
            "is_error": True,
        }

    results = response.get("results", [])
    if not results:
        return {
            "content": [{"type": "text", "text": f"No results found for: {query}"}],
        }

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("url", "")
        content = (r.get("content", "") or "")[:300]
        lines.append(f"{i}. {title}\n   {url}\n   {content}")
    text = "\n\n".join(lines)

    return {
        "content": [{"type": "text", "text": f"Search results for '{query}':\n\n{text}"}],
    }


def parse_tool_datetime(value: str) -> datetime:
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed


def build_task_display_text(prompt: str) -> str:
    normalized = prompt.strip()
    if "任务内容：" in normalized:
        normalized = normalized.split("任务内容：", maxsplit=1)[-1].strip()
    return normalized or prompt.strip()


def build_mcp_server(
    sender: MessageSender,
    target_id: str | int,
    uploaded_image: Any | None = None,
    channel: str | None = None,
    session_scope: str | None = None,
):
    """构造当前会话可用的 MCP 工具集合。"""

    @tool("send_message", "向当前会话额外发送一条消息。", {"text": str})
    async def send_message(args: dict[str, Any]) -> dict[str, Any]:
        text = args["text"]
        await send_sender_text(sender, target_id, text)
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Message sent to the current conversation successfully.",
                }
            ]
        }

    from pathlib import Path as _Path

    from hiclaw.skills.store import list_skills as _list_skills, get_skill as _get_skill, get_body as _get_body

    @tool("list_skills", "列出所有可用的 skill，返回名称和描述。", {})
    async def list_skills(_: dict[str, Any]) -> dict[str, Any]:
        skills = _list_skills()
        if not skills:
            return {
                "content": [{"type": "text", "text": "当前没有可用的 skill。"}],
            }
        lines = ["Available skills:"]
        for skill in skills:
            lines.append(f"- {skill.name}: {skill.description}")
        return {
            "content": [{"type": "text", "text": "\n".join(lines)}],
        }

    @tool("read_skill", "读取指定 skill 的完整内容。参数 name 是 skill 的名称。", {"name": str})
    async def read_skill(args: dict[str, Any]) -> dict[str, Any]:
        skill_name = args.get("name", "").strip()
        if not skill_name:
            return {
                "content": [{"type": "text", "text": "错误：name 不能为空。"}],
                "is_error": True,
            }
        skill = _get_skill(skill_name)
        if skill is None:
            return {
                "content": [{"type": "text", "text": f"未找到名为 '{skill_name}' 的 skill。使用 list_skills 查看可用列表。"}],
                "is_error": True,
            }
        body = _get_body(skill)
        return {
            "content": [{"type": "text", "text": f"[Skill: {skill.name} | {skill.title}]\n{body}"}],
        }

    @tool("create_skill", "创建一个新的 skill。参数 name 是 skill 名称（小写字母+下划线），title 是人类可读标题，description 是简短描述，keywords 是逗号分隔的关键词，body 是 skill 的完整指令内容。", {"name": str, "title": str, "description": str, "keywords": str, "body": str})
    async def create_skill(args: dict[str, Any]) -> dict[str, Any]:
        import re as _re
        name = args.get("name", "").strip()
        title = args.get("title", "").strip()
        description = args.get("description", "").strip()
        keywords = args.get("keywords", "").strip()
        body = args.get("body", "").strip()

        if not name:
            return {"content": [{"type": "text", "text": "错误：name 不能为空。"}], "is_error": True}
        if not _re.match(r'^[a-z][a-z0-9_]*$', name):
            return {"content": [{"type": "text", "text": "错误：name 只能包含小写字母、数字和下划线，且以小写字母开头。"}], "is_error": True}
        if not description:
            return {"content": [{"type": "text", "text": "错误：description 不能为空。"}], "is_error": True}
        if not body:
            return {"content": [{"type": "text", "text": "错误：body 不能为空。"}], "is_error": True}

        from hiclaw.config import SKILLS_DIR as _SKILLS_DIR
        target = _SKILLS_DIR / f"{name}_skill.md"
        if target.exists():
            return {"content": [{"type": "text", "text": f"错误：名为 '{name}' 的 skill 已存在（{target.name}）。"}], "is_error": True}

        keywords_line = f"keywords: [{keywords}]" if keywords else "keywords: []"
        frontmatter = f"---\nname: {name}\ntitle: {title or name}\ndescription: {description}\n{keywords_line}\n---\n\n"
        content = frontmatter + body

        try:
            target.write_text(content, encoding="utf-8")
        except Exception as exc:
            return {"content": [{"type": "text", "text": f"错误：写入文件失败：{exc}"}], "is_error": True}

        return {
            "content": [{"type": "text", "text": f"Skill '{name}' 已创建，文件：{target.name}。下次调用时自动生效。"}],
        }

    @tool("update_skill", "更新已有 skill 的内容。参数 name 是 skill 名称，title/description/keywords/body 为可选参数，只更新传入的字段。", {"name": str, "title": str, "description": str, "keywords": str, "body": str})
    async def update_skill(args: dict[str, Any]) -> dict[str, Any]:
        import re as _re
        name = args.get("name", "").strip()
        if not name:
            return {"content": [{"type": "text", "text": "错误：name 不能为空。"}], "is_error": True}
        if not _re.match(r'^[a-z][a-z0-9_]*$', name):
            return {"content": [{"type": "text", "text": "错误：name 只能包含小写字母、数字和下划线。"}], "is_error": True}

        skill = _get_skill(name)
        if skill is None:
            return {"content": [{"type": "text", "text": f"未找到名为 '{name}' 的 skill。使用 list_skills 查看可用列表。"}], "is_error": True}

        target = skill.file_path
        if not target.exists():
            return {"content": [{"type": "text", "text": f"Skill '{name}' 的文件不存在。"}], "is_error": True}

        try:
            raw = target.read_text(encoding="utf-8")
        except Exception as exc:
            return {"content": [{"type": "text", "text": f"错误：读取文件失败：{exc}"}], "is_error": True}

        fm_match = _re.match(r'^---\s*\n(.*?)\n---', raw, _re.DOTALL)
        if not fm_match:
            return {"content": [{"type": "text", "text": f"错误：Skill '{name}' 文件格式无效（缺少 frontmatter）。"}], "is_error": True}

        frontmatter_block = raw[:fm_match.end()]
        body_content = raw[fm_match.end():].strip()

        updated_fields = []
        new_title = args.get("title", "").strip()
        new_description = args.get("description", "").strip()
        new_keywords = args.get("keywords", "").strip()
        new_body = args.get("body", "").strip()

        if new_title:
            frontmatter_block = _re.sub(r'(?m)^title:.*$', f'title: {new_title}', frontmatter_block)
            updated_fields.append("title")
        if new_description:
            frontmatter_block = _re.sub(r'(?m)^description:.*$', f'description: {new_description}', frontmatter_block)
            updated_fields.append("description")
        if new_keywords:
            frontmatter_block = _re.sub(r'(?m)^keywords:.*$', f'keywords: [{new_keywords}]', frontmatter_block)
            updated_fields.append("keywords")
        if new_body:
            body_content = new_body
            updated_fields.append("body")

        if not updated_fields:
            return {"content": [{"type": "text", "text": "错误：没有指定要更新的字段。传入 title/description/keywords/body 中的至少一个。"}], "is_error": True}

        new_content = frontmatter_block + "\n" + body_content + "\n"
        try:
            target.write_text(new_content, encoding="utf-8")
        except Exception as exc:
            return {"content": [{"type": "text", "text": f"错误：写入文件失败：{exc}"}], "is_error": True}

        return {
            "content": [{"type": "text", "text": f"Skill '{name}' 已更新字段：{', '.join(updated_fields)}。下次调用时自动生效。"}],
        }

    @tool("delete_skill", "删除指定 skill。参数 name 是 skill 的名称。", {"name": str})
    async def delete_skill(args: dict[str, Any]) -> dict[str, Any]:
        name = args.get("name", "").strip()
        if not name:
            return {"content": [{"type": "text", "text": "错误：name 不能为空。"}], "is_error": True}

        skill = _get_skill(name)
        if skill is None:
            return {"content": [{"type": "text", "text": f"未找到名为 '{name}' 的 skill。使用 list_skills 查看可用列表。"}], "is_error": True}

        target = skill.file_path
        if not target.exists():
            return {"content": [{"type": "text", "text": f"Skill '{name}' 的文件不存在。"}], "is_error": True}

        try:
            target.unlink()
        except Exception as exc:
            return {"content": [{"type": "text", "text": f"错误：删除文件失败：{exc}"}], "is_error": True}

        return {
            "content": [{"type": "text", "text": f"Skill '{name}' 已删除（{target.name}）。下次调用时自动生效。"}],
        }

    @tool("send_file", "向当前会话发送工作区中的一个文件。参数 path 是文件在工作区中的绝对或相对路径。", {"path": str})
    async def send_file(args: dict[str, Any]) -> dict[str, Any]:
        raw_path = args["path"]
        from hiclaw.config import WORKSPACE_DIR
        file_path = _Path(raw_path)
        if not file_path.is_absolute():
            file_path = WORKSPACE_DIR / file_path
        resolved = file_path.resolve()
        if not str(resolved).startswith(str(WORKSPACE_DIR.resolve())):
            return {
                "content": [{"type": "text", "text": f"Error: Path '{raw_path}' is outside the workspace."}],
                "is_error": True,
            }
        if not resolved.is_file():
            return {
                "content": [{"type": "text", "text": f"Error: File not found: {raw_path}"}],
                "is_error": True,
            }
        try:
            file_data = resolved.read_bytes()
        except Exception as exc:
            return {
                "content": [{"type": "text", "text": f"Error reading file: {exc}"}],
                "is_error": True,
            }
        await send_sender_file(sender, target_id, file_data, resolved.name)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"File '{resolved.name}' has been sent to the current conversation.",
                }
            ]
        }

    @tool("get_uploaded_image", "获取本轮上传的图片内容。", {})
    async def get_uploaded_image(_: dict[str, Any]) -> dict[str, Any]:
        if uploaded_image is None:
            return {
                "content": [{"type": "text", "text": "No image was uploaded in this turn."}],
                "is_error": True,
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": "This is the image uploaded by the user in the current turn.",
                },
                {
                    "type": "image",
                    "data": base64.b64encode(uploaded_image.data).decode("ascii"),
                    "mimeType": uploaded_image.mime_type,
                },
            ]
        }

    @tool("list_tasks", "列出当前会话渠道（channel）下所有待执行的定时任务，优先用序号、时间和内容展示；如需取消可结合内部 ID 使用。", {})
    async def list_tasks(_: dict[str, Any]) -> dict[str, Any]:
        if not channel:
            return {
                "content": [{"type": "text", "text": "Error: Channel context is missing. Cannot list tasks."}],
                "is_error": True,
            }
        try:
            tasks = await list_scheduled_task_records(channel=channel, target_id=str(target_id))
        except Exception as exc:
            return {
                "content": [{"type": "text", "text": f"Failed to list tasks: {exc}"}],
                "is_error": True,
            }

        if not tasks:
            return {
                "content": [{"type": "text", "text": "No scheduled tasks found for this conversation."}],
            }

        lines = [f"Scheduled tasks for this conversation (channel: {channel}):"]
        for index, task in enumerate(tasks, 1):
            task_id = task.get("id", "unknown")
            prompt = build_task_display_text(task.get("prompt", "unknown"))
            next_run = task.get("next_run", "unknown")
            schedule_type = task.get("schedule_type", "once")
            lines.append(f"{index}. {next_run} | {schedule_type} | {prompt}")
            lines.append(f"   Internal ID: {task_id}")
            lines.append("")

        return {
            "content": [{"type": "text", "text": "\n".join(lines)}],
        }

    @tool("cancel_task", "取消当前会话渠道（channel）下指定 ID 的定时任务。", {"task_id": str})
    async def cancel_task(args: dict[str, Any]) -> dict[str, Any]:
        if not channel:
            return {
                "content": [{"type": "text", "text": "Error: Channel context is missing. Cannot cancel task."}],
                "is_error": True,
            }
        task_id = args["task_id"]
        try:
            success = await cancel_scheduled_task_record(task_id, channel=channel, target_id=str(target_id))
        except Exception as exc:
            return {
                "content": [{"type": "text", "text": f"Failed to cancel task: {exc}"}],
                "is_error": True,
            }

        if success:
            return {
                "content": [{"type": "text", "text": f"Task {task_id} has been cancelled successfully."}],
            }
        return {
            "content": [{"type": "text", "text": f"Task {task_id} not found or already cancelled."}],
            "is_error": True,
        }

    @tool(
        "create_task",
        "为当前会话创建一条单次定时任务。run_at 支持 ISO 时间或 'YYYY-MM-DD HH:MM:SS' 本地时间。",
        {"prompt": str, "run_at": str},
    )
    async def create_task(args: dict[str, Any]) -> dict[str, Any]:
        if not channel or not session_scope:
            return {
                "content": [{"type": "text", "text": "Error: Conversation context is missing. Cannot create task."}],
                "is_error": True,
            }
        prompt = args["prompt"].strip()
        if not prompt:
            return {
                "content": [{"type": "text", "text": "Error: prompt cannot be empty."}],
                "is_error": True,
            }
        try:
            run_at = parse_tool_datetime(args["run_at"])
        except ValueError as exc:
            return {
                "content": [{"type": "text", "text": f"Invalid run_at: {exc}"}],
                "is_error": True,
            }

        conversation = ConversationRef(
            channel=channel,
            target_id=str(target_id),
            session_scope=session_scope,
        )
        task_id = await create_scheduled_task(conversation=conversation, prompt=prompt, run_at=run_at)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Task created successfully. ID: {task_id}, run_at: {run_at.astimezone().strftime('%Y-%m-%d %H:%M:%S')}, prompt: {prompt}",
                }
            ]
        }

    tools = [
        get_current_time,
        list_workspace_files,
        read_workspace_file,
        send_message,
        send_file,
        get_uploaded_image,
        web_search,
        list_tasks,
        cancel_task,
        create_task,
        list_skills,
        read_skill,
        create_skill,
        update_skill,
        delete_skill,
    ]
    if uploaded_image is not None:
        tools.append(get_uploaded_image)

    return create_sdk_mcp_server(
        name="hiclaw-tools",
        version="1.0.0",
        tools=tools,
    )
