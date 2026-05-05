from __future__ import annotations

import re

CODE_BLOCK_PATTERN = re.compile(r"```(?:[\w#+.-]+\n)?(.*?)```", re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
ITALIC_PATTERN = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.DOTALL)


def format_feishu_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return ""

    normalized = CODE_BLOCK_PATTERN.sub(lambda m: f"\n[代码]\n{m.group(1).strip()}\n[/代码]\n", normalized)
    normalized = LINK_PATTERN.sub(lambda m: f"{m.group(1)} ({m.group(2)})", normalized)
    normalized = HEADING_PATTERN.sub(lambda m: f"【{m.group(2).strip()}】", normalized)
    normalized = BOLD_PATTERN.sub(lambda m: m.group(1), normalized)
    normalized = ITALIC_PATTERN.sub(lambda m: m.group(1), normalized)
    normalized = INLINE_CODE_PATTERN.sub(lambda m: f"「{m.group(1)}」", normalized)
    normalized = normalized.replace("\n\n\n", "\n\n")
    return normalized[:8000]
