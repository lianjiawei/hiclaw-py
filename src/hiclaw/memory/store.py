from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hiclaw.config import (
    CLAUDE_MEMORY_FILE,
    CONVERSATIONS_DIR,
    CONVERSATION_RETENTION_DAYS,
    LONG_TERM_MEMORY_DIR,
    MEMORY_ARCHIVE_DIR,
    MEMORY_ARCHIVE_AFTER_DAYS,
    MEMORY_CANDIDATES_DIR,
    MEMORY_CANDIDATE_AUTO_PROMOTE_SECONDS,
    MEMORY_DIR,
    PROJECT_ROOT,
    SESSION_SUMMARIES_DIR,
    WORKING_STATE_FILE,
    WORKSPACE_DIR,
)
from hiclaw.memory.frequency import (
    calculate_memory_importance,
    get_high_frequency_topics,
    load_frequency_state,
    save_importance_state,
    update_memory_frequency,
)

LONG_TERM_FILES = {
    "profile": LONG_TERM_MEMORY_DIR / "profile.md",
    "preferences": LONG_TERM_MEMORY_DIR / "preferences.md",
    "rules": LONG_TERM_MEMORY_DIR / "rules.md",
}

DEFAULT_WORKING_STATE = {
    "active_goal": "",
    "active_intent_type": "",
    "active_tasks": [],
    "recent_decisions": [],
    "open_questions": [],
    "touched_files": [],
    "updated_at": "",
}
FILE_REFERENCE_PATTERN = re.compile(r"(?:src|workspace|data|assets|skills|scripts)[/\\][^\s'\"`]+")
TASK_INTENT_PATTERN = re.compile(r"(帮我|请你|实现|修改|优化|重构|添加|增加|修复|排查|检查|分析|设计|整理|更新|刷新|生成|创建)")
QUESTION_INTENT_PATTERN = re.compile(r"(吗|么|什么|为何|为什么|如何|咋|怎么|哪|多少|是否|可不可以|能不能|\?|？)")
FILE_WORK_INTENT_PATTERN = re.compile(r"(文件|代码|模块|函数|类|路径|README|SVG|架构图|session|记忆|上下文|prompt)")
SLOT_MARKER_PATTERN = re.compile(r"<!--\s*slot:(?P<slot>[a-zA-Z0-9_-]+)\s*-->")
KEYWORD_EXTRACTOR = re.compile(r"[\u4e00-\u9fa5]{2,10}|[a-zA-Z]{3,20}")


def _sanitize_scope(scope: str | None) -> str:
    if not scope:
        return "default"
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", scope.strip()).strip("_")
    return normalized or "default"


def get_session_summary_file(scope: str | None = None) -> Path:
    return SESSION_SUMMARIES_DIR / f"{_sanitize_scope(scope)}.json"


def get_working_state_file(scope: str | None = None) -> Path:
    safe_scope = _sanitize_scope(scope)
    if safe_scope == "default":
        return WORKING_STATE_FILE
    return WORKING_STATE_FILE.with_name(f"{WORKING_STATE_FILE.stem}_{safe_scope}{WORKING_STATE_FILE.suffix}")


def ensure_memory_files() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    LONG_TERM_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

    if not CLAUDE_MEMORY_FILE.exists():
        CLAUDE_MEMORY_FILE.write_text(
            "# 长期记忆\n\n"
            "## 目录说明\n"
            f"- 项目根目录：`{PROJECT_ROOT}`\n"
            f"- 工作区目录：`{WORKSPACE_DIR}`\n"
            f"- 长期记忆文件：`{CLAUDE_MEMORY_FILE}`\n"
            f"- 对话记录目录：`{CONVERSATIONS_DIR}`\n\n"
            "## 文件使用规则\n"
            "- 长期稳定信息写入 CLAUDE.md 或 long_term 目录。\n"
            "- 每轮对话原始记录追加写入 conversations 目录。\n"
            "- 工作区文件操作尽量限制在工作区目录内。\n\n"
            "## 默认背景\n"
            "- 当前项目是一个支持多入口和双 Provider 的个人 Agent。\n"
            "- 需要长期复用的信息优先结构化沉淀，而不是只追加原始日志。\n",
            encoding="utf-8",
        )

    defaults = {
        "profile": "# 用户画像\n\n- 暂无结构化画像。\n",
        "preferences": "# 用户偏好\n\n- 暂无结构化偏好。\n",
        "rules": "# 长期规则\n\n- 暂无长期规则。\n",
    }
    for key, path in LONG_TERM_FILES.items():
        if not path.exists():
            path.write_text(defaults[key], encoding="utf-8")

    if not WORKING_STATE_FILE.exists():
        WORKING_STATE_FILE.write_text(json.dumps(DEFAULT_WORKING_STATE, ensure_ascii=False, indent=2), encoding="utf-8")

    default_summary_file = get_session_summary_file()
    if not default_summary_file.exists():
        default_summary_file.write_text(
            json.dumps(
                {
                    "session_scope": "default",
                    "updated_at": "",
                    "latest_user_message": "",
                    "latest_assistant_reply_excerpt": "",
                    "recent_topics": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def _read_json_file(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(fallback)
    return data if isinstance(data, dict) else dict(fallback)


def _compact_text(value: str, limit: int) -> str:
    return value.strip().replace("\n", " ")[:limit]


def _append_unique_tail(items: list[str], value: str, max_items: int) -> list[str]:
    normalized = value.strip()
    if not normalized:
        return items[-max_items:]
    result = [item for item in items if item != normalized]
    result.append(normalized)
    return result[-max_items:]


def _extract_touched_files(*texts: str) -> list[str]:
    matches: list[str] = []
    for text in texts:
        for match in FILE_REFERENCE_PATTERN.findall(text):
            normalized = match.replace("\\", "/")
            if normalized not in matches:
                matches.append(normalized)
    return matches


def _extract_open_question(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if any(stripped.endswith(mark) for mark in ("?", "？")):
        return _compact_text(stripped, 200)
    return ""


def _classify_intent(user_message: str) -> str:
    stripped = user_message.strip()
    if not stripped:
        return "empty"
    if stripped.startswith("/"):
        return "command"
    if FILE_WORK_INTENT_PATTERN.search(stripped) and TASK_INTENT_PATTERN.search(stripped):
        return "file_task"
    if TASK_INTENT_PATTERN.search(stripped):
        return "task"
    if QUESTION_INTENT_PATTERN.search(stripped):
        return "question"
    return "note"


def _extract_goal_candidate(user_message: str, intent_type: str) -> str:
    compact = _compact_text(user_message, 200)
    if intent_type in {"task", "file_task"}:
        return compact
    if intent_type == "question":
        return compact
    return ""


def _extract_decision_candidate(assistant_reply: str, intent_type: str) -> str:
    compact = _compact_text(assistant_reply, 240)
    if intent_type in {"task", "file_task", "question"}:
        return compact
    return compact[:160]


def _normalize_memory_note(note: str) -> str:
    return note.strip().replace("\n", " ")


def _split_markdown_sections(content: str) -> tuple[list[str], list[list[str]]]:
    lines = content.splitlines()
    preamble: list[str] = []
    sections: list[list[str]] = []
    current: list[str] | None = None

    for line in lines:
        if line.startswith("## "):
            if current is not None:
                sections.append(current)
            current = [line]
            continue
        if current is None:
            preamble.append(line)
        else:
            current.append(line)

    if current is not None:
        sections.append(current)
    return preamble, sections


def _section_slot(section_lines: list[str]) -> str | None:
    for line in section_lines:
        match = SLOT_MARKER_PATTERN.search(line)
        if match:
            return match.group("slot")
    return None


def _merge_structured_memory(path: Path, category: str, note: str, timestamp: str, slot: str | None = None) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    normalized_note = _normalize_memory_note(note)
    if normalized_note in existing:
        return False

    preamble, sections = _split_markdown_sections(existing)

    filtered_sections: list[list[str]] = []
    for section in sections:
        section_slot = _section_slot(section)
        if slot and section_slot == slot:
            continue
        filtered_sections.append(section)

    new_section = [f"## 自动记忆 {timestamp}"]
    if slot:
        new_section.append(f"<!-- slot:{slot} -->")
    new_section.append(f"- {normalized_note}")
    filtered_sections.append(new_section)

    rebuilt_lines = list(preamble)
    if rebuilt_lines and rebuilt_lines[-1].strip() != "":
        rebuilt_lines.append("")
    for index, section in enumerate(filtered_sections):
        if rebuilt_lines and rebuilt_lines[-1].strip() != "":
            rebuilt_lines.append("")
        rebuilt_lines.extend(section)
    path.write_text("\n".join(rebuilt_lines).rstrip() + "\n", encoding="utf-8")
    return True


def load_long_term_memory() -> str:
    ensure_memory_files()
    return CLAUDE_MEMORY_FILE.read_text(encoding="utf-8")


def append_long_term_memory(note: str) -> None:
    ensure_memory_files()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with CLAUDE_MEMORY_FILE.open("a", encoding="utf-8") as file:
        file.write(f"\n## 追加记忆 {timestamp}\n- {note.strip()}\n")


def append_structured_long_term_memory(note: str, category: str, slot: str | None = None) -> Path:
    ensure_memory_files()
    safe_category = re.sub(r"[^a-zA-Z0-9_-]+", "_", category.strip()).strip("_") or "general"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if safe_category in LONG_TERM_FILES:
        target = LONG_TERM_FILES[safe_category]
        _merge_structured_memory(target, safe_category, note, timestamp, slot)
        return target
    append_long_term_memory(note)
    return CLAUDE_MEMORY_FILE


def append_memory_candidate(note: str, category: str = "general", reason: str | None = None, slot: str | None = None) -> Path:
    ensure_memory_files()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_category = re.sub(r"[^a-zA-Z0-9_-]+", "_", category.strip()).strip("_") or "general"
    target = MEMORY_CANDIDATES_DIR / f"{timestamp}_{safe_category}.md"
    metadata_lines = [
        f"- category: {safe_category}",
        f"- created_at: {datetime.now().isoformat(timespec='seconds')}",
    ]
    if reason:
        metadata_lines.append(f"- reason: {reason}")
    if slot:
        metadata_lines.append(f"- slot: {slot}")
    metadata = "\n".join(metadata_lines)
    target.write_text(f"# Memory Candidate\n\n{metadata}\n\n{note.strip()}\n", encoding="utf-8")
    return target


def list_memory_candidates(limit: int = 20) -> list[Path]:
    ensure_memory_files()
    return sorted(MEMORY_CANDIDATES_DIR.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]


def get_memory_candidate(name: str) -> Path | None:
    ensure_memory_files()
    target = MEMORY_CANDIDATES_DIR / name.strip()
    return target if target.exists() and target.is_file() else None


def accept_memory_candidate(name: str, category: str = "general", slot: str | None = None) -> Path:
    candidate = get_memory_candidate(name)
    if candidate is None:
        raise FileNotFoundError(name)

    content = candidate.read_text(encoding="utf-8").strip()
    body = content.split("\n\n", maxsplit=2)[-1].strip() if content else ""
    safe_category = re.sub(r"[^a-zA-Z0-9_-]+", "_", category.strip()).strip("_") or "general"

    target = append_structured_long_term_memory(body, safe_category, slot)

    candidate.unlink()
    return target


def reject_memory_candidate(name: str) -> None:
    candidate = get_memory_candidate(name)
    if candidate is None:
        raise FileNotFoundError(name)
    candidate.unlink()


def load_working_state(scope: str | None = None) -> dict[str, Any]:
    ensure_memory_files()
    data = _read_json_file(get_working_state_file(scope), DEFAULT_WORKING_STATE)
    merged = dict(DEFAULT_WORKING_STATE)
    merged.update(data)
    return merged


def save_working_state(state: dict[str, Any], scope: str | None = None) -> None:
    ensure_memory_files()
    payload = dict(DEFAULT_WORKING_STATE)
    payload.update(state)
    payload["session_scope"] = _sanitize_scope(scope)
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    get_working_state_file(scope).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _compact_text(text: str, max_length: int) -> str:
    """截断文本到指定长度，避免工作记忆膨胀。"""
    if not text:
        return ""
    cleaned = text.strip().replace("\n", " ")
    if len(cleaned) > max_length:
        return cleaned[:max_length - 3] + "..."
    return cleaned


def update_working_state_from_turn(user_message: str, assistant_reply: str, scope: str | None = None) -> dict[str, Any]:
    ensure_memory_files()
    state = load_working_state(scope)

    intent_type = _classify_intent(user_message)
    active_goal = _extract_goal_candidate(user_message, intent_type)
    recent_decision = _extract_decision_candidate(assistant_reply, intent_type)
    open_question = _extract_open_question(assistant_reply)
    touched_files = _extract_touched_files(user_message, assistant_reply)

    state["active_intent_type"] = intent_type
    if active_goal:
        state["active_goal"] = _compact_text(active_goal, 200)
    state["active_tasks"] = [_compact_text(t, 200) for t in _append_unique_tail(list(state.get("active_tasks") or []), active_goal, 5)]
    state["recent_decisions"] = [_compact_text(d, 300) for d in _append_unique_tail(list(state.get("recent_decisions") or []), recent_decision, 8)]

    existing_questions = list(state.get("open_questions") or [])
    if open_question:
        state["open_questions"] = [_compact_text(q, 200) for q in _append_unique_tail(existing_questions, open_question, 5)]
    else:
        state["open_questions"] = [_compact_text(q, 200) for q in existing_questions[-5:]]

    merged_files = list(state.get("touched_files") or [])
    for touched in touched_files:
        merged_files = _append_unique_tail(merged_files, touched, 12)
    state["touched_files"] = merged_files[-12:]

    save_working_state(state, scope)
    return state


def load_session_summary(scope: str | None = None) -> dict[str, Any]:
    ensure_memory_files()
    return _read_json_file(
        get_session_summary_file(scope),
        {
            "session_scope": _sanitize_scope(scope),
            "updated_at": "",
            "latest_user_message": "",
            "latest_assistant_reply_excerpt": "",
            "recent_topics": [],
        },
    )


def save_session_summary(scope: str | None, user_message: str, assistant_reply: str) -> None:
    ensure_memory_files()
    summary = load_session_summary(scope)
    recent_topics = list(summary.get("recent_topics") or [])
    compact_user_message = user_message.strip().replace("\n", " ")
    if compact_user_message:
        recent_topics.append(compact_user_message[:80])
    recent_topics = recent_topics[-5:]
    payload = {
        "session_scope": _sanitize_scope(scope),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "latest_user_message": compact_user_message[:500],
        "latest_assistant_reply_excerpt": assistant_reply.strip().replace("\n", " ")[:800],
        "recent_topics": recent_topics,
    }
    get_session_summary_file(scope).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_session_context(scope: str | None = None) -> None:
    """清空当前会话级上下文，但保留长期记忆。"""

    ensure_memory_files()

    working_state_file = get_working_state_file(scope)
    if working_state_file.exists():
        working_state_file.write_text(json.dumps(DEFAULT_WORKING_STATE, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_file = get_session_summary_file(scope)
    summary_payload = {
        "session_scope": _sanitize_scope(scope),
        "updated_at": "",
        "latest_user_message": "",
        "latest_assistant_reply_excerpt": "",
        "recent_topics": [],
    }
    summary_file.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_context_snapshot(scope: str | None = None) -> str:
    ensure_memory_files()
    working_state = load_working_state(scope)
    session_summary = load_session_summary(scope)
    sections: list[str] = []

    # 长期记忆按用户全局共享；工作记忆和会话摘要按 session_scope 隔离。
    for key, title in (
        ("profile", "用户画像"),
        ("preferences", "用户偏好"),
        ("rules", "长期规则"),
    ):
        content = LONG_TERM_FILES[key].read_text(encoding="utf-8").strip()
        sections.append(f"## {title}\n{content}")

    sections.append("## 工作记忆\n" + json.dumps(working_state, ensure_ascii=False, indent=2))
    sections.append("## 会话摘要\n" + json.dumps(session_summary, ensure_ascii=False, indent=2))
    sections.append("## 兼容长期记忆\n" + load_long_term_memory().strip())
    return "\n\n".join(sections).strip()


def append_conversation_record(user_message: str, assistant_reply: str, session_id: str | None, session_scope: str | None = None) -> None:
    ensure_memory_files()
    date_key = datetime.now().strftime("%Y-%m-%d")
    file_path = CONVERSATIONS_DIR / f"{date_key}.jsonl"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "session_id": session_id,
        "session_scope": _sanitize_scope(session_scope),
        "user_message": user_message,
        "assistant_reply": assistant_reply,
    }
    with file_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    save_session_summary(session_scope, user_message, assistant_reply)
    update_working_state_from_turn(user_message, assistant_reply, session_scope)
    update_memory_frequency(user_message, assistant_reply)


def _parse_candidate_timestamp(filename: str) -> datetime | None:
    match = re.match(r"^(?P<ts>\d{8}_\d{6})_", filename)
    if not match:
        return None
    try:
        return datetime.strptime(match.group("ts"), "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def _parse_candidate_metadata(content: str) -> tuple[str, str | None, str | None]:
    category_match = re.search(r"category:\s*(\S+)", content)
    category = category_match.group(1) if category_match else "general"
    slot_match = re.search(r"slot:\s*(\S+)", content)
    slot = slot_match.group(1) if slot_match else None
    reason_match = re.search(r"reason:\s*(\S+)", content)
    reason = reason_match.group(1) if reason_match else None
    return category, slot, reason


def _get_promote_delay_seconds(reason: str | None) -> int:
    if reason in {"explicit_remember", "addressing_user", "assistant_name"}:
        return 0
    if reason in {"language_preference", "response_style", "preference_statement"}:
        return 3600
    if reason in {"future_rule", "response_rule"}:
        return 21600
    return MEMORY_CANDIDATE_AUTO_PROMOTE_SECONDS


def auto_promote_candidates() -> list[Path]:
    promoted: list[Path] = []
    now = datetime.now()

    for candidate_path in list_memory_candidates(limit=100):
        content = candidate_path.read_text(encoding="utf-8").strip()
        if not content:
            candidate_path.unlink()
            continue

        body = content.split("\n\n", maxsplit=2)[-1].strip() if content else ""
        if not body:
            candidate_path.unlink()
            continue

        category, slot, reason = _parse_candidate_metadata(content)
        created_at = _parse_candidate_timestamp(candidate_path.name)
        if created_at is None:
            continue

        delay_seconds = _get_promote_delay_seconds(reason)
        age_seconds = (now - created_at).total_seconds()
        if age_seconds < delay_seconds:
            continue

        safe_category = re.sub(r"[^a-zA-Z0-9_-]+", "_", category.strip()).strip("_") or "general"
        target = append_structured_long_term_memory(body, safe_category, slot)
        candidate_path.unlink()
        promoted.append(target)

    return promoted


def archive_old_memories() -> list[Path]:
    archived: list[Path] = []
    now = datetime.now()
    cutoff_days = MEMORY_ARCHIVE_AFTER_DAYS

    for category, path in LONG_TERM_FILES.items():
        if not path.exists():
            continue

        existing = path.read_text(encoding="utf-8")
        preamble, sections = _split_markdown_sections(existing)

        kept_sections: list[list[str]] = []
        archived_sections: list[list[str]] = []

        for section in sections:
            section_date = None
            for line in section:
                date_match = re.search(r"自动记忆\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
                if date_match:
                    try:
                        section_date = datetime.strptime(date_match.group(1), "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass
                    break

            if section_date and (now - section_date).days > cutoff_days:
                archived_sections.append(section)
            else:
                kept_sections.append(section)

        if archived_sections:
            archive_file = MEMORY_ARCHIVE_DIR / f"{category}_{now.strftime('%Y%m%d')}.md"
            archive_lines = list(preamble)
            for section in archived_sections:
                if archive_lines and archive_lines[-1].strip() != "":
                    archive_lines.append("")
                archive_lines.extend(section)
            archive_file.write_text("\n".join(archive_lines).rstrip() + "\n", encoding="utf-8")
            archived.append(archive_file)

            rebuilt_lines = list(preamble)
            for section in kept_sections:
                if rebuilt_lines and rebuilt_lines[-1].strip() != "":
                    rebuilt_lines.append("")
                rebuilt_lines.extend(section)
            path.write_text("\n".join(rebuilt_lines).rstrip() + "\n", encoding="utf-8")

    return archived


def _extract_memory_content(section: list[str]) -> str | None:
    for line in section:
        match = re.search(r"^-\s*(.+)$", line.strip())
        if match:
            return match.group(1).strip()
    return None


def _calculate_section_similarity(section_a: list[str], section_b: list[str]) -> float:
    """计算两个记忆片段的相似度，使用改进的关键词+字符n-gram混合相似度。"""
    content_a = _extract_memory_content(section_a)
    content_b = _extract_memory_content(section_b)
    if not content_a or not content_b:
        return 0.0

    # 提取关键词
    keywords_a = set(KEYWORD_EXTRACTOR.findall(content_a.lower()))
    keywords_b = set(KEYWORD_EXTRACTOR.findall(content_b.lower()))

    if not keywords_a or not keywords_b:
        return 0.0

    # 关键词 Jaccard 相似度
    keyword_intersection = keywords_a & keywords_b
    keyword_union = keywords_a | keywords_b
    keyword_similarity = len(keyword_intersection) / len(keyword_union) if keyword_union else 0.0

    # 字符 2-gram 相似度（对短文本更有效）
    def char_bigrams(text: str) -> set[str]:
        return {text[i:i+2] for i in range(len(text) - 1)}

    bigrams_a = char_bigrams(content_a.lower())
    bigrams_b = char_bigrams(content_b.lower())
    if bigrams_a and bigrams_b:
        bigram_intersection = bigrams_a & bigrams_b
        bigram_union = bigrams_a | bigrams_b
        bigram_similarity = len(bigram_intersection) / len(bigram_union) if bigram_union else 0.0
    else:
        bigram_similarity = 0.0

    # 混合相似度：关键词权重 60%，n-gram 权重 40%
    return 0.6 * keyword_similarity + 0.4 * bigram_similarity


def meditate_and_organize_memories() -> dict[str, Any]:
    frequency_state = load_frequency_state()
    high_freq_topics = get_high_frequency_topics(threshold=3)

    meditation_report = {
        "promoted_by_frequency": [],
        "merged_memories": [],
        "cleaned_memories": [],
        "importance_scores": {},
    }

    for topic, count in high_freq_topics:
        meditation_report["promoted_by_frequency"].append({
            "topic": topic,
            "count": count,
        })

    for category, path in LONG_TERM_FILES.items():
        if not path.exists():
            continue

        existing = path.read_text(encoding="utf-8")
        preamble, sections = _split_markdown_sections(existing)

        if len(sections) <= 1:
            continue

        # 预计算每个section的关键词集合，用于快速过滤
        section_keywords: list[set[str]] = []
        for section in sections:
            content = _extract_memory_content(section)
            if content:
                section_keywords.append(set(KEYWORD_EXTRACTOR.findall(content.lower())))
            else:
                section_keywords.append(set())

        merged_sections: list[list[str]] = []
        used_indices: set[int] = set()

        for i, section_a in enumerate(sections):
            if i in used_indices:
                continue

            similar_sections = [section_a]
            used_indices.add(i)
            keywords_a = section_keywords[i]
            if not keywords_a:
                continue

            for j, section_b in enumerate(sections):
                if j in used_indices:
                    continue
                keywords_b = section_keywords[j]
                if not keywords_b:
                    continue

                # 快速预过滤：关键词交集至少要有 30% 重叠才进行精确计算
                quick_overlap = len(keywords_a & keywords_b) / max(len(keywords_a | keywords_b), 1)
                if quick_overlap < 0.3:
                    continue

                similarity = _calculate_section_similarity(section_a, section_b)
                if similarity > 0.6:
                    similar_sections.append(section_b)
                    used_indices.add(j)

            if len(similar_sections) > 1:
                merged_content = _extract_memory_content(section_a)
                if merged_content:
                    merged_section = [
                        f"## 冥想合并 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        f"- {merged_content} [合并 {len(similar_sections)} 条相似记忆]",
                    ]
                    merged_sections.append(merged_section)
                    meditation_report["merged_memories"].append({
                        "category": category,
                        "merged_count": len(similar_sections),
                        "content_preview": merged_content[:50],
                    })
            else:
                merged_sections.append(section_a)

        kept_sections = []
        cleaned_count = 0
        for section in merged_sections:
            content = _extract_memory_content(section)
            if content:
                importance = calculate_memory_importance(content, frequency_state)
                if importance < 0.5 and len(merged_sections) > 3:
                    cleaned_count += 1
                    continue
                kept_sections.append(section)

        if cleaned_count > 0:
            meditation_report["cleaned_memories"].append({
                "category": category,
                "cleaned_count": cleaned_count,
            })

        if merged_sections != sections:
            rebuilt_lines = list(preamble)
            for section in kept_sections:
                if rebuilt_lines and rebuilt_lines[-1].strip() != "":
                    rebuilt_lines.append("")
                rebuilt_lines.extend(section)
            path.write_text("\n".join(rebuilt_lines).rstrip() + "\n", encoding="utf-8")

    save_importance_state({"memory_scores": meditation_report["importance_scores"]})

    return meditation_report


def clean_old_conversations() -> list[Path]:
    """清理超过保留天数的对话日志文件。"""
    cleaned: list[Path] = []
    now = datetime.now()
    cutoff = now - timedelta(days=CONVERSATION_RETENTION_DAYS)

    for log_file in sorted(CONVERSATIONS_DIR.glob("*.jsonl")):
        try:
            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})\.jsonl$", log_file.name)
            if not date_match:
                continue
            file_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
            if file_date < cutoff:
                log_file.unlink()
                cleaned.append(log_file)
        except (ValueError, OSError):
            continue

    return cleaned
