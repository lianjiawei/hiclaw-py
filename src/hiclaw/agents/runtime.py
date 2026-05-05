from __future__ import annotations

from typing import Any

from hiclaw.agents.router import run_agent
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
) -> AgentReply:
    return await run_agent(
        prompt=prompt,
        sender=sender,
        target_id=conversation.target_id,
        continue_session=continue_session,
        record_text=record_text,
        uploaded_image=uploaded_image,
        session_scope=conversation.session_scope,
        channel=conversation.channel,
    )
