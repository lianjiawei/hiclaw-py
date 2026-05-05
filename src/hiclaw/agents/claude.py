from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    query,
)

from hiclaw.agents.tools import build_mcp_server
from hiclaw.config import (
    ALLOWED_TOOLS,
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    ANTHROPIC_MODEL,
    CLAUDE_TOOLS_PRESET,
    SHOW_TOOL_TRACE,
    WORKSPACE_DIR,
)
from hiclaw.core.delivery import MessageSender, send_sender_text
from hiclaw.memory.store import append_conversation_record, build_context_snapshot
from hiclaw.core.locks import acquire_runtime_lock
from hiclaw.memory.session import load_session_id, save_session_id
from hiclaw.skills.store import build_skill_prompt

if TYPE_CHECKING:
    from telegram import Update

logger = logging.getLogger(__name__)

class ClaudeServiceError(Exception):
    """统一表示模型调用失败。"""


def build_system_prompt(prompt: str, session_scope: str | None = None) -> str:
    """构造当前 Agent 调用使用的 system prompt。"""

    context_snapshot = build_context_snapshot(session_scope)
    selected_skills, skill_prompt = build_skill_prompt(prompt)
    selected_skill_names = ", ".join(skill.name for skill in selected_skills) or "无"

    return f"""
你现在运行在一个多入口个人智能体系统中。
当前工作区目录是：{WORKSPACE_DIR}

下面是当前可用的分层上下文快照：
{context_snapshot}

本轮命中的 skill：{selected_skill_names}

{skill_prompt}

规则：
1. 当用户询问文件、目录或当前时间时，优先使用工具。
2. 如果需要额外主动给当前会话发送一条消息，请使用 send_message 工具。
3. 不要编造文件内容；如果需要文件数据，就调用工具读取。
4. 如果使用 Bash，请优先选择当前环境更稳妥的命令。
5. 当前环境里不要默认使用 `python3`，优先尝试 `python`。
6. 当前环境不保证安装了 `gh` 等额外命令行工具，不要默认依赖它们。
7. **联网搜索**：需要搜索互联网信息时，请使用 web_search 工具。
8. 回答尽量使用自然、清晰的中文。
""".strip()


def build_tool_hooks(sender: MessageSender, target_id: str | int) -> dict[str, list[HookMatcher]]:
    """构造工具执行过程的当前会话状态通知。"""

    async def notify_tool_start(hook_input, tool_use_id, context) -> dict:
        await send_sender_text(sender, target_id, f"[Tool Start] {hook_input['tool_name']}")
        return {}

    async def notify_tool_finish(hook_input, tool_use_id, context) -> dict:
        await send_sender_text(sender, target_id, f"[Tool Done] {hook_input['tool_name']}")
        return {}

    async def notify_tool_failure(hook_input, tool_use_id, context) -> dict:
        await send_sender_text(sender, target_id, f"[Tool Failed] {hook_input['tool_name']}: {hook_input['error']}")
        return {}

    return {
        "PreToolUse": [HookMatcher(hooks=[notify_tool_start])],
        "PostToolUse": [HookMatcher(hooks=[notify_tool_finish])],
        "PostToolUseFailure": [HookMatcher(hooks=[notify_tool_failure])],
    }


async def collect_agent_response(prompt: str, options: ClaudeAgentOptions) -> tuple[str, str | None]:
    final_result = None
    text_parts: list[str] = []
    latest_session_id: str | None = None

    async for message in query(prompt=prompt, options=options):
        if getattr(message, "session_id", None):
            latest_session_id = message.session_id
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
        elif isinstance(message, ResultMessage) and message.result:
            final_result = message.result

    return (final_result or "\n".join(text_parts)).strip(), latest_session_id


async def run_agent(
    prompt: str,
    sender: MessageSender,
    target_id: str | int,
    continue_session: bool,
    record_text: str | None = None,
    uploaded_image: Any | None = None,
    session_scope: str | None = None,
) -> str:
    """运行一次 Claude Agent，并负责 session 与对话记录落盘。"""

    tool_server = build_mcp_server(sender=sender, target_id=target_id, uploaded_image=uploaded_image)
    saved_session_id = load_session_id(session_scope) if continue_session else None
    options = ClaudeAgentOptions(
        permission_mode="acceptEdits",
        env={
            "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
            "ANTHROPIC_BASE_URL": ANTHROPIC_BASE_URL,
            "ANTHROPIC_MODEL": ANTHROPIC_MODEL,
        },
        cwd=str(WORKSPACE_DIR),
        tools=CLAUDE_TOOLS_PRESET,
        system_prompt=build_system_prompt(prompt, session_scope),
        mcp_servers={"hiclaw": tool_server},
        allowed_tools=ALLOWED_TOOLS,
        hooks=build_tool_hooks(sender, target_id) if SHOW_TOOL_TRACE else {},
        continue_conversation=continue_session and bool(saved_session_id),
        resume=saved_session_id,
    )

    try:
        async with acquire_runtime_lock(session_scope, "claude"):
            response, latest_session_id = await collect_agent_response(prompt, options)
            if not response and saved_session_id:
                logger.warning("Claude returned empty response while resuming session %s; retrying without resume.", saved_session_id)
                retry_options = ClaudeAgentOptions(
                    permission_mode="acceptEdits",
                    env={
                        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
                        "ANTHROPIC_BASE_URL": ANTHROPIC_BASE_URL,
                        "ANTHROPIC_MODEL": ANTHROPIC_MODEL,
                    },
                    cwd=str(WORKSPACE_DIR),
                    tools=CLAUDE_TOOLS_PRESET,
                    system_prompt=build_system_prompt(prompt, session_scope),
                    mcp_servers={"hiclaw": tool_server},
                    allowed_tools=ALLOWED_TOOLS,
                    hooks=build_tool_hooks(sender, target_id) if SHOW_TOOL_TRACE else {},
                    continue_conversation=False,
                    resume=None,
                )
                response, latest_session_id = await collect_agent_response(prompt, retry_options)
    except Exception as exc:
        logger.exception("Claude request failed")
        raise ClaudeServiceError("Failed to get response from Claude service.") from exc

    if not response.strip():
        raise ClaudeServiceError("Claude service returned an empty response.")

    if latest_session_id:
        save_session_id(latest_session_id, session_scope)

    append_conversation_record(record_text or prompt, response, latest_session_id if continue_session else None, session_scope)
    return response
