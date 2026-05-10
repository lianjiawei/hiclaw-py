from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ToolConfirmationRequest:
    tool_name: str
    summary: str
    prompt: str
    risk_level: str
    category: str


@dataclass(slots=True)
class PendingToolConfirmation:
    target_id: str
    request: ToolConfirmationRequest
    future: asyncio.Future[bool]


class ToolConfirmationHandler(Protocol):
    async def confirm_tool_use(self, target_id: str, request: ToolConfirmationRequest) -> bool: ...


_PENDING_CONFIRMATIONS: dict[str, PendingToolConfirmation] = {}


def normalize_confirmation_reply(text: str) -> bool | None:
    normalized = text.strip().lower()
    if normalized in {"y", "yes", "ok", "true", "1", "确认", "同意", "允许", "是", "好的", "继续", "执行"}:
        return True
    if normalized in {"n", "no", "false", "0", "取消", "拒绝", "不", "否", "不用", "停止"}:
        return False
    return None


def get_pending_confirmation(target_id: str | int) -> PendingToolConfirmation | None:
    return _PENDING_CONFIRMATIONS.get(str(target_id))


def register_pending_confirmation(target_id: str | int, request: ToolConfirmationRequest) -> asyncio.Future[bool]:
    key = str(target_id)
    existing = _PENDING_CONFIRMATIONS.get(key)
    if existing is not None and not existing.future.done():
        raise RuntimeError(f"A tool confirmation is already pending for target {key}.")
    future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
    _PENDING_CONFIRMATIONS[key] = PendingToolConfirmation(target_id=key, request=request, future=future)
    return future


def resolve_pending_confirmation(target_id: str | int, approved: bool) -> bool:
    key = str(target_id)
    pending = _PENDING_CONFIRMATIONS.pop(key, None)
    if pending is None:
        return False
    if not pending.future.done():
        pending.future.set_result(bool(approved))
    return True


def cancel_pending_confirmation(target_id: str | int) -> bool:
    key = str(target_id)
    pending = _PENDING_CONFIRMATIONS.pop(key, None)
    if pending is None:
        return False
    if not pending.future.done():
        pending.future.cancel()
    return True


async def wait_for_pending_confirmation(target_id: str | int, timeout_seconds: float = 300.0) -> bool:
    key = str(target_id)
    pending = _PENDING_CONFIRMATIONS.get(key)
    if pending is None:
        raise RuntimeError(f"No pending tool confirmation for target {key}.")
    try:
        return bool(await asyncio.wait_for(pending.future, timeout=timeout_seconds))
    except asyncio.TimeoutError:
        cancel_pending_confirmation(key)
        raise
    finally:
        if pending.future.done() and _PENDING_CONFIRMATIONS.get(key) is pending:
            _PENDING_CONFIRMATIONS.pop(key, None)


async def request_tool_confirmation(handler: object, target_id: str | int, request: ToolConfirmationRequest) -> bool | None:
    confirm = getattr(handler, "confirm_tool_use", None)
    if confirm is None:
        return None
    return bool(await confirm(str(target_id), request))
