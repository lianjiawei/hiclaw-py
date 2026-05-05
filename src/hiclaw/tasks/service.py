from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from hiclaw.runtime_types import ConversationRef
from hiclaw.scheduler import (
    format_schedule_description,
    parse_natural_schedule,
)
from hiclaw.task_repository import (
    cancel_scheduled_task_record,
    create_scheduled_task_record,
    list_scheduled_task_records,
)
import uuid


async def create_scheduled_task(
    conversation: ConversationRef,
    prompt: str,
    run_at: datetime,
    schedule_type: str = "once",
    schedule_value: str | None = None,
    continue_session: bool = False,
) -> str:
    task_id = uuid.uuid4().hex[:8]
    await create_scheduled_task_record(
        task_id=task_id,
        conversation=conversation,
        prompt=prompt,
        run_at=run_at,
        schedule_type=schedule_type,
        schedule_value=schedule_value,
        continue_session=continue_session,
    )
    return task_id


async def list_scheduled_tasks(channel: str | None = None, target_id: str | None = None):
    return await list_scheduled_task_records(channel=channel, target_id=target_id)


async def cancel_scheduled_task(task_id: str, channel: str | None = None, target_id: str | None = None) -> bool:
    return await cancel_scheduled_task_record(task_id, channel=channel, target_id=target_id)


@dataclass(frozen=True, slots=True)
class TaskCommandResult:
    handled: bool
    message: str = ""


async def handle_task_command(conversation: ConversationRef, text: str) -> TaskCommandResult:
    stripped = text.strip()
    lowered = stripped.lower()

    if lowered.startswith("/schedule_in"):
        parts = stripped.split(maxsplit=2)
        if len(parts) < 3:
            return TaskCommandResult(True, "用法：/schedule_in 秒数 任务内容")
        try:
            delay_seconds = int(parts[1])
        except ValueError:
            return TaskCommandResult(True, "秒数必须是整数，例如：/schedule_in 60 1分钟后提醒我喝水")
        if delay_seconds <= 0:
            return TaskCommandResult(True, "秒数必须大于 0。")
        prompt = parts[2].strip()
        if not prompt:
            return TaskCommandResult(True, "任务内容不能为空。")
        run_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        task_id = await create_scheduled_task(conversation, prompt, run_at)
        local_time = run_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        return TaskCommandResult(
            True,
            "定时任务已创建。\n"
            f"- 任务ID：{task_id}\n"
            "- 类型：单次任务\n"
            f"- 执行时间：{local_time}\n"
            f"- 内容：{prompt}",
        )

    if lowered.startswith("/schedule"):
        schedule_text = stripped[len("/schedule") :].strip()
        if not schedule_text:
            return TaskCommandResult(True, "用法：/schedule 自然语言时间 + 任务内容，例如：/schedule 每天下午3点提醒我喝水")
        natural_schedule = parse_natural_schedule(schedule_text)
        if natural_schedule is None:
            return TaskCommandResult(True, "没有识别出有效的定时表达。示例：/schedule 每天下午3点提醒我喝水")
        task_id = await create_scheduled_task(
            conversation=conversation,
            prompt=natural_schedule.prompt,
            run_at=natural_schedule.run_at,
            schedule_type=natural_schedule.schedule_type,
            schedule_value=natural_schedule.schedule_value,
        )
        local_time = natural_schedule.run_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        return TaskCommandResult(
            True,
            "定时任务已创建。\n"
            f"- 任务ID：{task_id}\n"
            f"- 类型：{format_schedule_description(natural_schedule.schedule_type, natural_schedule.schedule_value)}\n"
            f"- 执行时间：{local_time}\n"
            f"- 内容：{natural_schedule.prompt}",
        )

    if lowered == "/tasks":
        tasks = await list_scheduled_tasks(conversation.channel, conversation.target_id)
        if not tasks:
            return TaskCommandResult(True, "当前没有待执行的定时任务。")
        lines = ["当前待执行任务："]
        for task in tasks:
            local_time = datetime.fromisoformat(task["next_run"]).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            schedule_desc = format_schedule_description(task.get("schedule_type", "once"), task.get("schedule_value"))
            lines.append(f"- {task['id']} | {schedule_desc} | {local_time} | {task['prompt']}")
        return TaskCommandResult(True, "\n".join(lines))

    if lowered.startswith("/cancel"):
        parts = stripped.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            return TaskCommandResult(True, "用法：/cancel 任务ID")
        task_id = parts[1].strip()
        success = await cancel_scheduled_task(task_id, conversation.channel, conversation.target_id)
        return TaskCommandResult(True, f"任务 {task_id} 已取消。" if success else f"没有找到可取消的任务：{task_id}")

    natural_schedule = parse_natural_schedule(stripped)
    if natural_schedule is None:
        return TaskCommandResult(False)
    task_id = await create_scheduled_task(
        conversation=conversation,
        prompt=natural_schedule.prompt,
        run_at=natural_schedule.run_at,
        schedule_type=natural_schedule.schedule_type,
        schedule_value=natural_schedule.schedule_value,
    )
    local_time = natural_schedule.run_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return TaskCommandResult(
        True,
        "我已按自然语言理解为一条定时任务。\n"
        f"- 任务ID：{task_id}\n"
        f"- 类型：{format_schedule_description(natural_schedule.schedule_type, natural_schedule.schedule_value)}\n"
        f"- 执行时间：{local_time}\n"
        f"- 内容：{natural_schedule.prompt}",
    )
