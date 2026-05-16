from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
CHECK_SUFFIXES = {".py", ".md", ".toml", ".example", ".env", ".sh", ".ps1", ".html", ".css", ".js"}
CHECK_NAMES = {".env", ".env.example", ".editorconfig", ".gitignore"}
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "data",
    "workspace",
    "workspace_course",
    "node_modules",
    "dist",
}

# These patterns usually indicate mojibake caused by reading UTF-8 text through
# a legacy Chinese code page, or replacement characters from a failed decode.
BAD_PATTERNS = [
    "\ufffd",
    "锟",
    "�",
    "鎵",
    "閰",
    "鏃",
    "璇",
    "鍙",
    "涓",
    "鐢",
    "鍚",
    "妫",
    "鐘",
    "淇",
    "寤",
]


def should_check(path: Path) -> bool:
    if path.resolve() == SELF:
        return False
    relative_parts = path.relative_to(ROOT).parts
    if any(part in SKIP_DIRS for part in relative_parts):
        return False
    return path.name in CHECK_NAMES or path.suffix in CHECK_SUFFIXES


def scan_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"{path}: 不是合法 UTF-8：{exc}"]

    findings: list[str] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for pattern in BAD_PATTERNS:
            if pattern in line:
                findings.append(f"{path}:{line_number}: 发现疑似乱码 `{pattern}`：{line.strip()}")
                break
    return findings


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if path.is_file() and should_check(path):
            findings.extend(scan_file(path))

    if findings:
        print("发现疑似编码问题：")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("文本编码检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
