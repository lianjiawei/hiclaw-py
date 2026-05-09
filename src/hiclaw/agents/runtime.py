from __future__ import annotations

from typing import Any

from hiclaw.agents.router import run_agent
from hiclaw.core.agent_activity import mark_agent_run_finished, mark_agent_run_started, mark_agent_waiting, reply_requires_waiting
from hiclaw.core.response import AgentReply
from hiclaw.core.delivery import MessageSender
from hiclaw.core.types import ConversationRef


async def run_agent_for_conversation(
    prompt: str,
    conversation: ConversationRef,
    sender: MessageSender,
    continue_session: bool = True,
    record_text: str | None = None,
    uploaded_image: Any | None = None,
    uploaded_file: Any | None = None,
) -> AgentReply:
    mark_agent_run_started(conversation, record_text or prompt)
    try:
        reply = await run_agent(
            prompt=prompt,
            sender=sender,
            target_id=conversation.target_id,
            continue_session=continue_session,
            record_text=record_text,
            uploaded_image=uploaded_image,
            uploaded_file=uploaded_file,
            session_scope=conversation.session_scope,
            channel=conversation.channel,
        )
    except Exception as exc:
        mark_agent_run_finished(conversation, str(exc) or exc.__class__.__name__)
        raise
    if reply_requires_waiting(reply.text):
        mark_agent_waiting(conversation, reply.text)
        return reply
    mark_agent_run_finished(conversation)
    return reply
