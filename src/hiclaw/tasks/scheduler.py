import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from hiclaw.agent_runtime import run_agent_for_conversation
from hiclaw.config import SCHEDULER_INTERVAL_SECONDS
from hiclaw.delivery import DeliveryRouter
from hiclaw.memory_store import archive_old_memories, auto_promote_candidates, clean_old_conversations, meditate_and_organize_memories
from hiclaw.runtime_types import ConversationRef
from hiclaw.task_repository import claim_scheduled_task_record, list_due_task_record_ids, release_claimed_task_record, update_task_record_after_run

logger = logging.getLogger(__name__)

WEEKDAY_NAME_TO_INDEX = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}

WEEKDAY_INDEX_TO_LABEL = {
    "0": "每周一",
    "1": "每周二",
    "2": "每周三",
    "3": "每周四",
    "4": "每周五",
    "5": "每周六",
    "6": "每周日",
}


@dataclass(slots=True)
class ParsedSchedule:
    # 自然语言解析后的统一任务结构。
    run_at: datetime
    prompt: str
    schedule_type: str
    schedule_value: str | None


def get_local_now() -> datetime:
    return datetime.now().astimezone()


def normalize_hour(period: str | None, hour: int) -> int:
    if period in {"下午", "晚上"} and 1 <= hour <= 11:
        return hour + 12
    if period == "中午" and 1 <= hour <= 10:
        return hour + 12
    if period in {"早上", "上午"} and hour == 12:
        return 0
    return hour


def compute_next_weekday_run(now: datetime, weekday: int, hour: int, minute: int) -> datetime:
    days_ahead = weekday - now.weekday()
    if days_ahead < 0:
        days_ahead += 7

    target_date = (now + timedelta(days=days_ahead)).date()
    run_at = datetime(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
        hour=hour,
        minute=minute,
        tzinfo=now.tzinfo,
    )

    if run_at <= now:
        run_at = run_at + timedelta(days=7)

    return run_at


def format_schedule_description(schedule_type: str, schedule_value: str | None) -> str:
    if schedule_type == "once":
        return "单次任务"
    if schedule_type == "daily":
        return f"每天 {schedule_value}"
    if schedule_type == "weekly":
        if not schedule_value:
            return "每周任务"
        weekday, time_part = schedule_value.split("|", maxsplit=1)
        return f"{WEEKDAY_INDEX_TO_LABEL.get(weekday, '每周')} {time_part}"
    return schedule_type


def parse_relative_schedule(text: str, now: datetime) -> ParsedSchedule | None:
    patterns = [
        r"^(?P<num>\d+)\s*秒后(?P<task>.+)$",
        r"^(?P<num>\d+)\s*分钟后(?P<task>.+)$",
        r"^(?P<num>\d+)\s*小时后(?P<task>.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, text)
        if not match:
            continue

        amount = int(match.group("num"))
        task = match.group("task").strip(" ，。,:：")
        if not task:
            return None

        if "秒后" in pattern:
            run_at = now + timedelta(seconds=amount)
        elif "分钟后" in pattern:
            run_at = now + timedelta(minutes=amount)
        else:
            run_at = now + timedelta(hours=amount)

        return ParsedSchedule(run_at=run_at, prompt=task, schedule_type="once", schedule_value=None)

    return None


def parse_daily_schedule(text: str, now: datetime) -> ParsedSchedule | None:
    match = re.match(
        r"^每天(?P<period>早上|上午|中午|下午|晚上)?(?P<hour>\d{1,2})点(?:(?P<minute>\d{1,2})分?)?(?P<task>.+)$",
        text,
    )
    if not match:
        return None

    period = match.group("period")
    hour = normalize_hour(period, int(match.group("hour")))
    minute = int(match.group("minute") or "0")
    task = match.group("task").strip(" ，。,:：")
    if not task or not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    run_at = datetime(
        year=now.year,
        month=now.month,
        day=now.day,
        hour=hour,
        minute=minute,
        tzinfo=now.tzinfo,
    )
    if run_at <= now:
        run_at = run_at + timedelta(days=1)

    return ParsedSchedule(
        run_at=run_at,
        prompt=task,
        schedule_type="daily",
        schedule_value=f"{hour:02d}:{minute:02d}",
    )


def parse_weekly_schedule(text: str, now: datetime) -> ParsedSchedule | None:
    match = re.match(
        r"^每周(?P<weekday>[一二三四五六日天])(?P<period>早上|上午|中午|下午|晚上)?"
        r"(?P<hour>\d{1,2})点(?:(?P<minute>\d{1,2})分?)?(?P<task>.+)$",
        text,
    )
    if not match:
        return None

    weekday_text = match.group("weekday")
    period = match.group("period")
    hour = normalize_hour(period, int(match.group("hour")))
    minute = int(match.group("minute") or "0")
    task = match.group("task").strip(" ，。,:：")
    if not task or not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    weekday = WEEKDAY_NAME_TO_INDEX[weekday_text]
    run_at = compute_next_weekday_run(now, weekday, hour, minute)

    return ParsedSchedule(
        run_at=run_at,
        prompt=task,
        schedule_type="weekly",
        schedule_value=f"{weekday}|{hour:02d}:{minute:02d}",
    )


def parse_absolute_schedule(text: str, now: datetime) -> ParsedSchedule | None:
    match = re.match(
        r"^(?P<day>今天|今晚|明天)(?P<period>早上|上午|中午|下午|晚上)?"
        r"(?P<hour>\d{1,2})点(?:(?P<minute>\d{1,2})分?)?(?P<task>.+)$",
        text,
    )
    if not match:
        return None

    day_word = match.group("day")
    period = match.group("period")
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or "0")
    task = match.group("task").strip(" ，。,:：")
    if not task:
        return None

    if day_word == "今晚" and period is None:
        period = "晚上"

    hour = normalize_hour(period, hour)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    day_offset = 1 if day_word == "明天" else 0
    target_date = (now + timedelta(days=day_offset)).date()
    run_at = datetime(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
        hour=hour,
        minute=minute,
        tzinfo=now.tzinfo,
    )

    if day_word in {"今天", "今晚"} and run_at <= now:
        run_at = run_at + timedelta(days=1)

    return ParsedSchedule(run_at=run_at, prompt=task, schedule_type="once", schedule_value=None)


def parse_natural_schedule(text: str) -> ParsedSchedule | None:
    normalized = text.strip()
    now = get_local_now()

    parsers = [
        parse_relative_schedule,
        parse_daily_schedule,
        parse_weekly_schedule,
        parse_absolute_schedule,
    ]

    for parser in parsers:
        result = parser(normalized, now)
        if result is not None:
            return result

    return None


def compute_next_run_after_execution(task: dict[str, Any]) -> tuple[datetime | None, str]:
    schedule_type = task.get("schedule_type", "once")
    schedule_value = task.get("schedule_value")

    if schedule_type == "daily" and schedule_value:
        hour_text, minute_text = schedule_value.split(":", maxsplit=1)
        now = get_local_now()
        next_run = datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=int(hour_text),
            minute=int(minute_text),
            tzinfo=now.tzinfo,
        ) + timedelta(days=1)
        return next_run, "active"

    if schedule_type == "weekly" and schedule_value:
        weekday_text, time_part = schedule_value.split("|", maxsplit=1)
        hour_text, minute_text = time_part.split(":", maxsplit=1)
        next_run = compute_next_weekday_run(
            get_local_now(),
            int(weekday_text),
            int(hour_text),
            int(minute_text),
        )
        return next_run, "active"

    return None, "completed"


def build_task_conversation(task: dict[str, Any]) -> ConversationRef:
    channel = str(task.get("channel") or "telegram")
    target_id = str(task.get("target_id") or task.get("chat_id") or "")
    session_scope = str(task.get("session_scope") or f"{channel}:scheduled:{target_id}")
    return ConversationRef(channel=channel, target_id=target_id, session_scope=session_scope)


async def send_task_text(router: DeliveryRouter, conversation: ConversationRef, text: str) -> None:
    await router.send_text(conversation, text)


async def execute_scheduled_task(task: dict[str, Any], router: DeliveryRouter) -> None:
    task_id = task["id"]
    prompt = task["prompt"]
    continue_session = bool(task.get("continue_session", False))
    conversation = build_task_conversation(task)

    wrapped_prompt = (
        "你正在执行一条定时任务。"
        "请根据任务要求完成回答；如果需要额外主动通知当前会话，请使用 send_message 工具。\n\n"
        f"任务内容：{prompt}"
    )

    try:
        sender = router.get(conversation)
        result = await run_agent_for_conversation(
            prompt=wrapped_prompt,
            conversation=conversation,
            sender=sender,
            continue_session=continue_session,
        )
        await send_task_text(router, conversation, f"⏰ 定时任务执行结果：\n{result.text}")
        next_run, next_status = compute_next_run_after_execution(task)
        await update_task_record_after_run(task_id, result.text, next_run, next_status)
    except RuntimeError as exc:
        logger.exception("Scheduled task sender unavailable: %s", task_id)
        error_text = f"定时任务未执行：通道 `{conversation.channel}` 当前不可用或未注册 sender。错误：{exc}"
        await update_task_record_after_run(task_id, error_text, None, "completed")
    except Exception as exc:
        logger.exception("Scheduled task failed: %s", task_id)
        error_text = f"定时任务执行失败：{exc}"
        try:
            await send_task_text(router, conversation, error_text)
        except Exception:
            logger.exception("Scheduled task error delivery failed: %s", task_id)
        await update_task_record_after_run(task_id, error_text, None, "completed")


async def check_due_tasks(router: DeliveryRouter) -> None:
    due_task_ids = await list_due_task_record_ids()
    for task_id in due_task_ids:
        task = await claim_scheduled_task_record(task_id)
        if task is None:
            logger.info("Skipped scheduled task claim because it was already claimed: %s", task_id)
            continue
        conversation = build_task_conversation(task)
        if not router.owns(conversation):
            logger.debug(
                "Releasing claimed scheduled task %s because current runtime does not own route: key=%s",
                task.get("id"),
                conversation.conversation_key,
            )
            await release_claimed_task_record(str(task.get("id")))
            continue
        if not router.has(conversation):
            logger.warning(
                "Skipping scheduled task %s because sender is unavailable: key=%s",
                task.get("id"),
                conversation.conversation_key,
            )
            await release_claimed_task_record(str(task.get("id")))
            continue
        await execute_scheduled_task(task, router)


async def run_memory_maintenance() -> None:
    try:
        promoted = auto_promote_candidates()
        if promoted:
            logger.info("Auto-promoted %d memory candidate(s)", len(promoted))

        archived = archive_old_memories()
        if archived:
            logger.info("Archived %d old memory file(s)", len(archived))
    except Exception:
        logger.exception("Memory maintenance failed")


async def run_memory_meditation() -> None:
    try:
        report = meditate_and_organize_memories()
        logger.info(
            "Memory meditation completed: %d merged, %d cleaned",
            len(report.get("merged_memories", [])),
            len(report.get("cleaned_memories", [])),
        )
    except Exception:
        logger.exception("Memory meditation failed")


async def run_conversation_cleanup() -> None:
    try:
        cleaned = clean_old_conversations()
        if cleaned:
            logger.info("Cleaned %d old conversation log file(s)", len(cleaned))
    except Exception:
        logger.exception("Conversation cleanup failed")


def setup_scheduler(router: DeliveryRouter, event_loop=None) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(event_loop=event_loop)
    scheduler.add_job(
        check_due_tasks,
        "interval",
        seconds=SCHEDULER_INTERVAL_SECONDS,
        args=[router],
        id="hiclaw_check_tasks",
        replace_existing=True,
    )
    scheduler.add_job(
        run_memory_maintenance,
        "interval",
        hours=6,
        id="hiclaw_memory_maintenance",
        replace_existing=True,
    )
    scheduler.add_job(
        run_memory_meditation,
        "cron",
        hour=2,
        minute=0,
        id="hiclaw_memory_meditation",
        replace_existing=True,
    )
    scheduler.add_job(
        run_conversation_cleanup,
        "cron",
        hour=3,
        minute=0,
        id="hiclaw_conversation_cleanup",
        replace_existing=True,
    )
    return scheduler
