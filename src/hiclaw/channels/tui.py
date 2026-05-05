from __future__ import annotations

import asyncio
import os
import shutil
import sys
import uuid
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hiclaw.agents.router import AgentServiceError, build_tui_conversation
from hiclaw.agents.runtime import run_agent_for_conversation
from hiclaw.core.response import AgentReply
from hiclaw.config import AGENT_PROVIDER, PROJECT_ROOT, SHOW_TOOL_TRACE, TUI_OUTPUT_DIR, WORKSPACE_DIR
from hiclaw.core.delivery import DeliveryRouter
from hiclaw.memory.intent import build_memory_intent_ack, detect_memory_intent, should_auto_accept_memory_intent
from hiclaw.memory.store import append_memory_candidate, append_structured_long_term_memory
from hiclaw.tasks.runtime import start_background_scheduler, stop_background_scheduler
from hiclaw.tasks.service import handle_task_command
from hiclaw.memory.session import clear_session_id, get_session_file

TUI_SESSION_SCOPE_PREFIX = "tui"
TUI_INSTANCE_ID = os.getenv("HICLAW_TUI_INSTANCE_ID", f"pid{os.getpid()}_{uuid.uuid4().hex[:8]}")
MIN_PANEL_WIDTH = 72
PROMPT = "> "


@dataclass(frozen=True, slots=True)
class CommandInfo:
    name: str
    description: str


COMMANDS = [
    CommandInfo("/help", "查看帮助"),
    CommandInfo("/reset", "清空 TUI 独立连续会话"),
    CommandInfo("/provider", "查看当前 Agent Provider"),
    CommandInfo("/schedule_in", "创建单次定时任务"),
    CommandInfo("/tasks", "查看当前 TUI 定时任务"),
    CommandInfo("/cancel", "取消指定定时任务"),
    CommandInfo("/paste", "进入多行输入，单独一行 . 结束"),
    CommandInfo("/exit", "退出"),
]


@dataclass(slots=True)
class ConsoleBot:
    async def send_text(self, target_id: str, text: str) -> None:
        print_turn_block("Agent message", text, accent="33")

    async def send_message(self, chat_id: str | int, text: str) -> None:
        await self.send_text(str(chat_id), text)


def get_tui_scope() -> str:
    return f"{TUI_SESSION_SCOPE_PREFIX}:{TUI_INSTANCE_ID}"


def configure_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def supports_color() -> bool:
    return sys.stdout.isatty() and os.getenv("NO_COLOR") is None


def color(text: str, code: str) -> str:
    if not supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def terminal_width() -> int:
    width = shutil.get_terminal_size(fallback=(96, 24)).columns
    return max(MIN_PANEL_WIDTH, min(width, 110))


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return path.name


def display_width(text: str) -> int:
    width = 0
    for char in text:
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def trim_right(text: str, max_width: int) -> str:
    result: list[str] = []
    width = 0
    for char in text:
        char_width = 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
        if width + char_width > max_width:
            break
        result.append(char)
        width += char_width
    return "".join(result)


def trim_middle(text: str, max_width: int) -> str:
    if display_width(text) <= max_width:
        return text
    if max_width <= 3:
        return trim_right(text, max_width)
    keep_left = max_width // 2 - 1
    keep_right = max_width - keep_left - 3
    left = trim_right(text, keep_left)
    right = text[-keep_right:] if keep_right > 0 else ""
    return f"{left}...{right}"


def pad_display(text: str, width: int) -> str:
    current_width = display_width(text)
    if current_width > width:
        text = trim_right(text, width)
        current_width = display_width(text)
    return text + " " * max(0, width - current_width)


def box_line(text: str, width: int, color_code: str | None = None) -> str:
    inner_width = width - 4
    line = f"│ {pad_display(text, inner_width)} │"
    return color(line, color_code) if color_code else line


def box_line_center(text: str, width: int, color_code: str | None = None) -> str:
    inner_width = width - 4
    visible_text = text if display_width(text) <= inner_width else trim_middle(text, inner_width)
    left_padding = max(0, (inner_width - display_width(visible_text)) // 2)
    padded = " " * left_padding + visible_text
    line = f"│ {pad_display(padded, inner_width)} │"
    return color(line, color_code) if color_code else line


def panel_line(label: str, value: str, width: int, accent: str, accent_color: str) -> str:
    inner_width = width - 4
    accent_text = color(accent, accent_color)
    label_text = f"{label:<10}"
    value_width = max(8, inner_width - len(label_text) - 3)
    value_text = trim_middle(value, value_width)
    return f"│ {accent_text} {label_text} {pad_display(value_text, value_width)} │"


def build_logo_lines() -> list[str]:
    return [
        "██╗  ██╗██╗ ██████╗██╗      █████╗ ██╗    ██╗",
        "██║  ██║██║██╔════╝██║     ██╔══██╗██║    ██║",
        "███████║██║██║     ██║     ███████║██║ █╗ ██║",
        "██╔══██║██║██║     ██║     ██╔══██║██║███╗██║",
        "██║  ██║██║╚██████╗███████╗██║  ██║╚███╔███╔╝",
        "╚═╝  ╚═╝╚═╝ ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝ ",
    ]


def print_header() -> None:
    width = terminal_width()
    rule = "─" * (width - 2)
    session_file = get_session_file(get_tui_scope())
    print(color(f"╭{rule}╮", "36"))
    print(box_line_center("", width, "36"))
    for line in build_logo_lines():
        print(box_line_center(line, width, "36;1"))
    print(box_line_center("HiClaw TUI", width, "36;1"))
    print(box_line_center("Local Agent Console", width, "96"))
    print(box_line_center(f"{AGENT_PROVIDER.upper()}  |  Workspace rooted in your local project", width, "90"))
    print(box_line_center("", width, "36"))
    print(panel_line("Provider", AGENT_PROVIDER, width, "●", "36;1"))
    print(panel_line("Workspace", display_path(WORKSPACE_DIR), width, "◆", "35;1"))
    print(panel_line("Session", display_path(session_file), width, "◦", "33;1"))
    print(panel_line("Images", display_path(TUI_OUTPUT_DIR), width, "■", "32;1"))
    print(color(f"├{rule}┤", "36"))
    print(box_line("Enter 发送；多行内容请使用 /paste", width, "90"))
    print(box_line("/reset 清空会话；/help 查看命令；/exit 退出", width, "90"))
    print(color(f"╰{rule}╯", "36"))
    print()


def print_turn_block(title: str, text: str, subtitle: str | None = None, accent: str = "36") -> None:
    width = terminal_width()
    lines = text.rstrip().splitlines() if text.strip() else ["(empty)"]
    print()
    print(color("═" * width, accent))
    header = title if not subtitle else f"{title}  |  {subtitle}"
    print(color(header, f"{accent};1" if ";" not in accent else accent))
    print(color("─" * width, accent))
    for line in lines:
        print(line)
    print(color("═" * width, accent))
    print()


def build_meta_subtitle(*parts: str) -> str:
    return "  |  ".join(part.strip() for part in parts if part and part.strip())


def format_command_suggestions(prefix: str, selected_index: int) -> list[str]:
    matched = [command for command in COMMANDS if command.name.startswith(prefix)] if prefix else []
    if prefix == "/":
        matched = COMMANDS
    if not matched:
        return [color("  没有匹配的命令", "90")]
    name_width = max(display_width(command.name) for command in matched)
    selected_index = selected_index % len(matched)
    lines: list[str] = []
    for index, command in enumerate(matched):
        marker = ">" if index == selected_index else " "
        command_name = pad_display(command.name, name_width)
        if index == selected_index:
            lines.append(f"{color(marker, '33;1')} {color(command_name, '36;1')}  {command.description}")
        else:
            lines.append(f"{marker} {command_name}  {command.description}")
    return lines


def _read_prompt_windows() -> str:
    import msvcrt

    buffer: list[str] = []
    selected_index = 0

    def current_text() -> str:
        return "".join(buffer)

    def current_matches() -> list[CommandInfo]:
        text = current_text()
        if not text.startswith("/"):
            return []
        matched = [command for command in COMMANDS if command.name.startswith(text)]
        if text == "/":
            matched = COMMANDS
        return matched

    def render() -> None:
        text = current_text()
        suggestions = format_command_suggestions(text, selected_index) if text.startswith("/") else []
        sys.stdout.write("\r\033[J")
        sys.stdout.write(color(PROMPT, "36;1") + text)
        if suggestions:
            sys.stdout.write("\n" + "\n".join(suggestions))
            sys.stdout.write(f"\033[{len(suggestions)}A")
            sys.stdout.write("\r\033[2K" + color(PROMPT, "36;1") + text)
        sys.stdout.flush()

    sys.stdout.write(color(PROMPT, "36;1"))
    sys.stdout.flush()

    while True:
        ch = msvcrt.getwch()
        if ch in ("\r", "\n"):
            matches = current_matches()
            if matches and current_text().startswith("/"):
                buffer[:] = list(matches[selected_index % len(matches)].name)
            sys.stdout.write("\r\033[J")
            sys.stdout.write(color(PROMPT, "36;1") + current_text() + "\n")
            sys.stdout.flush()
            return current_text()
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\t":
            matches = current_matches()
            if matches:
                buffer[:] = list(matches[selected_index % len(matches)].name)
                selected_index = 0
                render()
            continue
        if ch == "\x08":
            if buffer:
                buffer.pop()
                selected_index = 0
                render()
            continue
        if ch in ("\x00", "\xe0"):
            key = msvcrt.getwch()
            matches = current_matches()
            if matches and key in ("H", "P"):
                if key == "H":
                    selected_index = (selected_index - 1) % len(matches)
                else:
                    selected_index = (selected_index + 1) % len(matches)
                render()
            continue
        if ch.isprintable():
            buffer.append(ch)
            selected_index = 0
            render()


def read_prompt() -> str:
    if os.name == "nt" and sys.stdin.isatty():
        return _read_prompt_windows()
    return input(color(PROMPT, "36;1"))


def read_multiline() -> str:
    print_turn_block("Paste Mode", "进入多行输入模式，单独一行 . 结束。", subtitle=build_meta_subtitle("Legacy mode", datetime.now().strftime("%H:%M:%S")), accent="34")
    lines: list[str] = []
    while True:
        line = input("... ")
        if line == ".":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def print_help() -> None:
    lines = [f"{command.name:<10} {command.description}" for command in COMMANDS]
    print_turn_block("Commands", "\n".join(lines), subtitle=build_meta_subtitle(datetime.now().strftime("%H:%M:%S"), "TUI commands"), accent="34")


def save_reply_images(reply: AgentReply) -> list[Path]:
    saved_paths: list[Path] = []
    if not reply.images:
        return saved_paths
    TUI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    instance_suffix = TUI_INSTANCE_ID.replace(":", "_")
    for index, image in enumerate(reply.images, 1):
        suffix = image.mime_type.removeprefix("image/") or "png"
        target = TUI_OUTPUT_DIR / f"generated_{instance_suffix}_{timestamp}_{index}.{suffix}"
        target.write_bytes(image.data)
        saved_paths.append(target)
    return saved_paths


async def run_thinking_indicator(stop_event: asyncio.Event) -> None:
    frames = ["Thinking   ", "Thinking.  ", "Thinking.. ", "Thinking..."]
    index = 0
    while not stop_event.is_set():
        sys.stdout.write("\r\033[2K" + color(frames[index % len(frames)], "33;1"))
        sys.stdout.flush()
        index += 1
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=0.2)
        except asyncio.TimeoutError:
            continue
    sys.stdout.write("\r\033[2K")
    sys.stdout.flush()


def render_turn(prompt: str, provider: str, reply: AgentReply, saved_images: list[Path]) -> None:
    if saved_images:
        for path in saved_images:
            print(display_path(path))
        if reply.text.strip():
            print()
    if reply.text.strip():
        print(reply.text.rstrip())


async def submit_prompt(prompt: str, bot: ConsoleBot) -> None:
    stop_event = asyncio.Event()
    indicator_task = asyncio.create_task(run_thinking_indicator(stop_event))
    try:
        reply = await run_agent_for_conversation(
            prompt=prompt,
            conversation=build_tui_conversation(get_tui_scope()),
            sender=bot,
            continue_session=True,
            record_text=f"[PowerShell TUI] {prompt}",
        )
    finally:
        stop_event.set()
        await indicator_task
    saved_images = save_reply_images(reply)
    render_turn(prompt, AGENT_PROVIDER.upper(), reply, saved_images)
    print()


async def run_tui() -> None:
    configure_stdio()
    print_header()
    bot = ConsoleBot()
    conversation = build_tui_conversation(get_tui_scope())
    router = DeliveryRouter()
    router.register_conversation(conversation, bot)
    scheduler_runtime = start_background_scheduler(router)
    try:
        while True:
            try:
                prompt = await asyncio.to_thread(read_prompt)
            except EOFError:
                print()
                break
            prompt = prompt.strip()
            if not prompt:
                continue
            command = prompt.lower()
            if command in {"/exit", "/quit", "exit", "quit"}:
                break
            if command == "/help":
                print_help()
                continue
            if command == "/provider":
                print_turn_block("Provider", f"当前 Provider: {AGENT_PROVIDER}", subtitle=build_meta_subtitle(datetime.now().strftime("%H:%M:%S"), "Runtime"), accent="32")
                continue
            if command == "/reset":
                clear_session_id(get_tui_scope())
                print_turn_block("Session", "TUI 连续会话已清空。", subtitle=build_meta_subtitle(datetime.now().strftime("%H:%M:%S"), "Fresh session"), accent="32")
                continue
            if command.startswith("/schedule") or command.startswith("/schedule_in") or command.startswith("/cancel") or command == "/tasks":
                result = await handle_task_command(conversation, prompt)
                if result.handled:
                    print_turn_block("Schedule", result.message, subtitle=build_meta_subtitle(datetime.now().strftime("%H:%M:%S"), "TUI task"), accent="32")
                    continue
                continue
            if command == "/paste":
                prompt = await asyncio.to_thread(read_multiline)
                if not prompt:
                    continue

            result = await handle_task_command(conversation, prompt)
            if result.handled:
                print_turn_block("Schedule", result.message, subtitle=build_meta_subtitle(datetime.now().strftime("%H:%M:%S"), "TUI task"), accent="32")
                continue

            memory_intent = detect_memory_intent(prompt)
            if memory_intent is not None:
                if should_auto_accept_memory_intent(memory_intent):
                    target = append_structured_long_term_memory(memory_intent.content, memory_intent.category, memory_intent.slot)
                    print_turn_block(
                        "Memory",
                        build_memory_intent_ack(memory_intent, True, SHOW_TOOL_TRACE, target.name),
                        subtitle=build_meta_subtitle(datetime.now().strftime("%H:%M:%S"), "Structured memory"),
                        accent="32",
                    )
                else:
                    candidate_file = append_memory_candidate(memory_intent.content, memory_intent.category, memory_intent.reason, memory_intent.slot)
                    print_turn_block(
                        "Memory",
                        build_memory_intent_ack(memory_intent, False, SHOW_TOOL_TRACE, candidate_file.name),
                        subtitle=build_meta_subtitle(datetime.now().strftime("%H:%M:%S"), "Candidate memory"),
                        accent="33",
                    )
                continue
            try:
                await submit_prompt(prompt, bot)
            except AgentServiceError as exc:
                print_turn_block("Error", str(exc), subtitle=build_meta_subtitle(datetime.now().strftime("%H:%M:%S"), AGENT_PROVIDER.upper(), "Failure"), accent="31")
            except KeyboardInterrupt:
                print()
                break
    finally:
        stop_background_scheduler(scheduler_runtime)
    print("TUI 已退出。")


def main() -> None:
    try:
        asyncio.run(run_tui())
    except KeyboardInterrupt:
        print("\nTUI 已退出。")


if __name__ == "__main__":
    main()
