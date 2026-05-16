from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from hiclaw.config import PROJECT_ROOT

ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE_FILE = PROJECT_ROOT / ".env.example"

PLACEHOLDER_MARKERS = (
    "your_",
    "your-",
    "_here",
    "example",
    "changeme",
    "replace_me",
)

DEFAULTS: dict[str, str] = {
    "AGENT_PROVIDER": "openai",
    "OPENAI_MODEL": "gpt-4o-mini",
    "HICLAW_DASHBOARD_HOST": "127.0.0.1",
    "HICLAW_DASHBOARD_PORT": "8765",
    "WORKSPACE_DIR": "./workspace",
    "SCHEDULER_INTERVAL_SECONDS": "5",
    "HICLAW_TUI_COLOR_MODE": "auto",
    "ASR_PROVIDER": "none",
    "SHOW_TOOL_TRACE": "0",
    "SESSION_TIMEOUT_SECONDS": "86400",
    "CAPABILITY_WATCHER_ENABLED": "1",
    "CAPABILITY_WATCHER_INTERVAL_SECONDS": "1.0",
    "AGENT_CLUSTER_ENABLED": "0",
    "AGENT_CLUSTER_REVIEW_ENABLED": "1",
    "AGENT_CLUSTER_ORCHESTRATOR_ENABLED": "0",
    "AGENT_CLUSTER_DYNAMIC_PLANNER_ENABLED": "0",
    "AGENT_CLUSTER_MAX_EVENTS": "40",
    "TAVILY_SEARCH_DEPTH": "basic",
    "TAVILY_MAX_RESULTS": "5",
    "TELEGRAM_CONNECT_TIMEOUT": "30",
    "TELEGRAM_READ_TIMEOUT": "30",
    "TELEGRAM_WRITE_TIMEOUT": "30",
    "TELEGRAM_POOL_TIMEOUT": "30",
    "TELEGRAM_POLLING_TIMEOUT": "30",
    "TELEGRAM_BOOTSTRAP_RETRIES": "5",
    "TELEGRAM_RESTART_DELAY_SECONDS": "10",
    "TELEGRAM_API_RETRIES": "2",
    "TELEGRAM_API_RETRY_DELAY_SECONDS": "1.5",
    "FEISHU_SESSION_SCOPE_PREFIX": "feishu",
    "FEISHU_REPLY_PROCESSING_MESSAGE": "1",
    "FEISHU_RESTART_DELAY_SECONDS": "10",
    "FEISHU_API_RETRIES": "2",
    "FEISHU_API_RETRY_DELAY_SECONDS": "1.5",
}


@dataclass(frozen=True, slots=True)
class ConfigIssue:
    level: str
    code: str
    message: str
    hint: str = ""


def _is_windows() -> bool:
    return os.name == "nt"


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    return key, _unquote(value.strip())


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _quote(value: str) -> str:
    if value == "":
        return ""
    if any(char.isspace() for char in value) or "#" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def load_env_values(path: Path | None = None) -> dict[str, str]:
    path = path or ENV_FILE
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed is not None:
            key, value = parsed
            values[key] = value
    return values


def ensure_env_file(copy_example: bool = True, path: Path | None = None, example_path: Path | None = None) -> bool:
    path = path or ENV_FILE
    example_path = example_path or ENV_EXAMPLE_FILE
    if path.exists():
        return False
    if copy_example and example_path.exists():
        shutil.copyfile(example_path, path)
    else:
        path.write_text("", encoding="utf-8")
    return True


def set_env_values(updates: dict[str, str], path: Path | None = None) -> None:
    path = path or ENV_FILE
    ensure_env_file(path=path)
    lines = path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    updated_lines: list[str] = []

    for line in lines:
        parsed = _parse_env_line(line)
        if parsed is None:
            updated_lines.append(line)
            continue
        key, _value = parsed
        if key in updates:
            updated_lines.append(f"{key}={_quote(updates[key])}")
            seen.add(key)
        else:
            updated_lines.append(line)

    missing = [key for key in updates if key not in seen]
    if missing and updated_lines and updated_lines[-1].strip():
        updated_lines.append("")
    for key in missing:
        updated_lines.append(f"{key}={_quote(updates[key])}")

    path.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")


def _value(values: dict[str, str], key: str) -> str:
    return values.get(key, os.getenv(key, "")).strip()


def _has_value(values: dict[str, str], key: str) -> bool:
    value = _value(values, key)
    if not value:
        return False
    lowered = value.lower()
    return not any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return bool(lowered) and any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _parse_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_env(values: dict[str, str] | None = None, *, require_channel: bool = True) -> list[ConfigIssue]:
    values = values or load_env_values()
    issues: list[ConfigIssue] = []

    if not ENV_FILE.exists():
        issues.append(
            ConfigIssue(
                "error",
                "missing_env",
                f"未找到配置文件：{ENV_FILE}",
                "运行 `python -m hiclaw setup` 生成并填写 .env。",
            )
        )
        return issues

    provider = (_value(values, "AGENT_PROVIDER") or DEFAULTS["AGENT_PROVIDER"]).lower()
    if provider not in {"claude", "openai"}:
        issues.append(ConfigIssue("error", "invalid_provider", "AGENT_PROVIDER 只能是 claude 或 openai。", "运行 `python -m hiclaw config set AGENT_PROVIDER=openai`。"))
    elif provider == "openai" and not _has_value(values, "OPENAI_API_KEY"):
        issues.append(ConfigIssue("error", "missing_openai_key", "当前 Provider 是 openai，但 OPENAI_API_KEY 未配置。", "在 .env 中设置 OPENAI_API_KEY，或运行 `python -m hiclaw setup`。"))
    elif provider == "claude" and not _has_value(values, "ANTHROPIC_API_KEY"):
        issues.append(ConfigIssue("error", "missing_claude_key", "当前 Provider 是 claude，但 ANTHROPIC_API_KEY 未配置。", "在 .env 中设置 ANTHROPIC_API_KEY，或切换 `AGENT_PROVIDER=openai`。"))

    openai_base_url = _value(values, "OPENAI_BASE_URL")
    if openai_base_url and _looks_like_placeholder(openai_base_url):
        issues.append(ConfigIssue("warning", "placeholder_openai_base_url", "OPENAI_BASE_URL 仍是模板占位值。", "不用代理时请留空；使用兼容服务商时填写真实 /v1 地址。"))
    anthropic_base_url = _value(values, "ANTHROPIC_BASE_URL")
    if anthropic_base_url and _looks_like_placeholder(anthropic_base_url):
        issues.append(ConfigIssue("warning", "placeholder_anthropic_base_url", "ANTHROPIC_BASE_URL 仍是模板占位值。", "不用代理时请留空；使用兼容服务商时填写真实地址。"))
    image_base_url = _value(values, "OPENAI_IMAGE_BASE_URL")
    if image_base_url and _looks_like_placeholder(image_base_url):
        issues.append(ConfigIssue("warning", "placeholder_image_base_url", "OPENAI_IMAGE_BASE_URL 仍是模板占位值，图片工具会不可用。", "不用图片工具时请留空；需要图片能力时填写真实地址。"))

    telegram_ready = _has_value(values, "TELEGRAM_BOT_TOKEN") and _has_value(values, "OWNER_ID")
    feishu_ready = _has_value(values, "FEISHU_APP_ID") and _has_value(values, "FEISHU_APP_SECRET")
    if require_channel and not telegram_ready and not feishu_ready:
        issues.append(
            ConfigIssue(
                "error",
                "missing_channel",
                "没有可用消息通道：需要配置 Telegram 或 Feishu。",
                "Telegram 设置 TELEGRAM_BOT_TOKEN 和 OWNER_ID；Feishu 设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET。只想本地调试可运行 `hiclaw-tui`。",
            )
        )

    owner_id = _value(values, "OWNER_ID")
    if owner_id and "your_" not in owner_id.lower() and not owner_id.isdigit():
        level = "error" if _has_value(values, "TELEGRAM_BOT_TOKEN") else "warning"
        issues.append(ConfigIssue(level, "invalid_owner_id", "OWNER_ID 应该是纯数字 Telegram user id。", "可以向 Telegram 的 @userinfobot 查询自己的 user id。"))

    port = _parse_int(_value(values, "HICLAW_DASHBOARD_PORT") or DEFAULTS["HICLAW_DASHBOARD_PORT"])
    if port <= 0 or port > 65535:
        issues.append(ConfigIssue("error", "invalid_dashboard_port", "HICLAW_DASHBOARD_PORT 不是有效端口。", "请设置为 1-65535 之间的端口，例如 8765。"))

    asr_provider = (_value(values, "ASR_PROVIDER") or "none").lower()
    if asr_provider not in {"none", "vosk"}:
        issues.append(ConfigIssue("error", "invalid_asr_provider", "ASR_PROVIDER 只能是 none 或 vosk。", "语音识别暂不用时设置 ASR_PROVIDER=none。"))
    if asr_provider == "vosk":
        model_dir = _value(values, "VOSK_MODEL_DIR")
        if not model_dir:
            issues.append(ConfigIssue("error", "missing_vosk_model", "ASR_PROVIDER=vosk 但 VOSK_MODEL_DIR 未配置。", "设置 VOSK_MODEL_DIR 为本地 Vosk 模型目录，或改为 ASR_PROVIDER=none。"))
        elif not Path(model_dir).expanduser().exists():
            issues.append(ConfigIssue("error", "missing_vosk_path", f"VOSK_MODEL_DIR 不存在：{model_dir}", "请确认模型目录路径。"))

    tavily = _value(values, "TAVILY_API_KEY")
    if not tavily:
        issues.append(
            ConfigIssue(
                "warning",
                "missing_tavily_key",
                "TAVILY_API_KEY 未配置，默认联网搜索工具会不可用。",
                "如果你希望默认可用联网搜索，请在 .env 中设置 TAVILY_API_KEY，或运行 `python -m hiclaw setup`。",
            )
        )
    elif any(marker in tavily.lower() for marker in PLACEHOLDER_MARKERS):
        issues.append(ConfigIssue("warning", "placeholder_tavily", "TAVILY_API_KEY 仍是模板占位值，联网搜索工具会不可用。", "不需要联网搜索可以留空；需要时填写真实 Tavily API Key。"))

    return issues


def print_doctor_report(issues: list[ConfigIssue], *, quiet: bool = False) -> None:
    if quiet:
        return
    print("HiClaw 配置检查")
    print(f"- 项目目录: {PROJECT_ROOT}")
    print(f"- 配置文件: {ENV_FILE}")
    if not issues:
        print("状态: 通过，可以启动。")
        return
    print("状态: 发现配置问题")
    for issue in issues:
        prefix = "ERROR" if issue.level == "error" else "WARN"
        print(f"- [{prefix}] {issue.message}")
        if issue.hint:
            print(f"  修复建议: {issue.hint}")


def _prompt(label: str, default: str = "", *, secret: bool = False) -> str:
    if secret:
        import getpass

        suffix = " [已配置，回车保留]" if default else ""
        value = getpass.getpass(f"{label}{suffix}: ").strip()
    else:
        suffix = f" [{default}]" if default else ""
        value = input(f"{label}{suffix}: ").strip()
    return value or default


def _yes_no(label: str, default: bool = False) -> bool:
    marker = "Y/n" if default else "y/N"
    value = input(f"{label} [{marker}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "1", "true", "是"}


def run_setup(args: argparse.Namespace) -> int:
    _configure_stdio()
    created = ensure_env_file()
    values = load_env_values()
    updates: dict[str, str] = {}

    print("HiClaw 初始化向导")
    print(f"- 配置文件: {ENV_FILE}")
    if created:
        print("- 已根据 .env.example 创建 .env")

    provider_default = args.provider or _value(values, "AGENT_PROVIDER") or DEFAULTS["AGENT_PROVIDER"]
    provider = provider_default.lower()
    if provider not in {"claude", "openai"}:
        provider = DEFAULTS["AGENT_PROVIDER"]
    if not args.non_interactive:
        provider = _prompt("选择模型 Provider (openai/claude)", provider).lower()
    updates["AGENT_PROVIDER"] = provider

    if provider == "openai":
        key = args.openai_api_key or _value(values, "OPENAI_API_KEY")
        if not args.non_interactive:
            key = _prompt("OPENAI_API_KEY", "" if not _has_value(values, "OPENAI_API_KEY") else key, secret=True)
        if key:
            updates["OPENAI_API_KEY"] = key
        base_url = args.openai_base_url if args.openai_base_url is not None else _value(values, "OPENAI_BASE_URL")
        if not args.non_interactive:
            base_url = _prompt("OPENAI_BASE_URL (可选，兼容服务商填写)", base_url if _has_value(values, "OPENAI_BASE_URL") else "")
        updates["OPENAI_BASE_URL"] = base_url
        updates["OPENAI_MODEL"] = args.openai_model or _value(values, "OPENAI_MODEL") or DEFAULTS["OPENAI_MODEL"]
    else:
        key = args.anthropic_api_key or _value(values, "ANTHROPIC_API_KEY")
        if not args.non_interactive:
            key = _prompt("ANTHROPIC_API_KEY", "" if not _has_value(values, "ANTHROPIC_API_KEY") else key, secret=True)
        if key:
            updates["ANTHROPIC_API_KEY"] = key
        base_url = args.anthropic_base_url if args.anthropic_base_url is not None else _value(values, "ANTHROPIC_BASE_URL")
        if not args.non_interactive:
            base_url = _prompt("ANTHROPIC_BASE_URL (可选，代理/兼容端点填写)", base_url if _has_value(values, "ANTHROPIC_BASE_URL") else "")
        updates["ANTHROPIC_BASE_URL"] = base_url
        model = args.anthropic_model or _value(values, "ANTHROPIC_MODEL")
        if not args.non_interactive:
            model = _prompt("ANTHROPIC_MODEL (可选)", model if _has_value(values, "ANTHROPIC_MODEL") else "")
        updates["ANTHROPIC_MODEL"] = model

    channel = args.channel
    if not channel and not args.non_interactive:
        channel = _prompt("选择消息通道 (telegram/feishu/none)", "telegram").lower()
    channel = (channel or "none").lower()
    if channel == "telegram":
        token = args.telegram_bot_token or _value(values, "TELEGRAM_BOT_TOKEN")
        owner = args.owner_id or _value(values, "OWNER_ID")
        if not args.non_interactive:
            token = _prompt("TELEGRAM_BOT_TOKEN", "" if not _has_value(values, "TELEGRAM_BOT_TOKEN") else token, secret=True)
            owner = _prompt("OWNER_ID (Telegram user id)", "" if not _has_value(values, "OWNER_ID") else owner)
        if token:
            updates["TELEGRAM_BOT_TOKEN"] = token
        if owner:
            updates["OWNER_ID"] = owner
    elif channel == "feishu":
        app_id = args.feishu_app_id or _value(values, "FEISHU_APP_ID")
        app_secret = args.feishu_app_secret or _value(values, "FEISHU_APP_SECRET")
        if not args.non_interactive:
            app_id = _prompt("FEISHU_APP_ID", "" if not _has_value(values, "FEISHU_APP_ID") else app_id)
            app_secret = _prompt("FEISHU_APP_SECRET", "" if not _has_value(values, "FEISHU_APP_SECRET") else app_secret, secret=True)
        if app_id:
            updates["FEISHU_APP_ID"] = app_id
        if app_secret:
            updates["FEISHU_APP_SECRET"] = app_secret
    elif channel == "none":
        for key in ("TELEGRAM_BOT_TOKEN", "OWNER_ID", "FEISHU_APP_ID", "FEISHU_APP_SECRET"):
            if not _has_value(values, key):
                updates[key] = ""

    tavily_key = args.tavily_api_key or _value(values, "TAVILY_API_KEY")
    if not args.non_interactive:
        tavily_key = _prompt(
            "TAVILY_API_KEY (可选，默认联网搜索使用)",
            "" if not _has_value(values, "TAVILY_API_KEY") else tavily_key,
            secret=True,
        )
    if tavily_key:
        updates["TAVILY_API_KEY"] = tavily_key

    dashboard_host = args.dashboard_host or _value(values, "HICLAW_DASHBOARD_HOST") or DEFAULTS["HICLAW_DASHBOARD_HOST"]
    if not args.non_interactive:
        default_host = "127.0.0.1" if _is_windows() else dashboard_host
        if _yes_no("Dashboard 是否允许公网/局域网访问", default=False):
            default_host = "0.0.0.0"
        dashboard_host = _prompt("HICLAW_DASHBOARD_HOST", default_host)
    updates["HICLAW_DASHBOARD_HOST"] = dashboard_host
    updates["HICLAW_DASHBOARD_PORT"] = str(args.dashboard_port or _value(values, "HICLAW_DASHBOARD_PORT") or DEFAULTS["HICLAW_DASHBOARD_PORT"])

    for key, value in DEFAULTS.items():
        existing = _value(values, key)
        updates.setdefault(key, existing if existing and _has_value(values, key) else value)

    set_env_values(updates)
    issues = validate_env(load_env_values(), require_channel=channel != "none")
    print("")
    print_doctor_report(issues)
    print("")
    print("常用命令:")
    print("- 前台启动: python -m hiclaw run")
    print("- 后台启动: python -m hiclaw start")
    print("- 停止后台: python -m hiclaw stop")
    print("- 本地 TUI: hiclaw-tui")
    print("- 检查配置: python -m hiclaw doctor")
    return 1 if any(issue.level == "error" for issue in issues) else 0


def run_doctor(args: argparse.Namespace) -> int:
    _configure_stdio()
    issues = validate_env(require_channel=not args.tui_only)
    print_doctor_report(issues, quiet=args.quiet)
    return 1 if any(issue.level == "error" for issue in issues) else 0


def run_config_set(pairs: Iterable[str]) -> int:
    _configure_stdio()
    updates: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            print(f"无效配置项：{pair}，请使用 KEY=VALUE 格式。")
            return 2
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            print(f"无效配置项：{pair}")
            return 2
        updates[key] = value.strip()
    if not updates:
        print("请提供至少一个 KEY=VALUE。")
        return 2
    ensure_env_file()
    set_env_values(updates)
    print("已更新 .env:")
    for key in updates:
        print(f"- {key}")
    return 0


def _is_secret_key(key: str) -> bool:
    upper = key.upper()
    return any(marker in upper for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD"))


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "******"
    return f"{value[:4]}...{value[-4:]}"


def run_config_get(keys: Iterable[str], *, show_secrets: bool = False) -> int:
    _configure_stdio()
    values = load_env_values()
    selected = list(keys) or sorted(values)
    for key in selected:
        value = values.get(key, "")
        if not show_secrets and _is_secret_key(key):
            value = _mask_secret(value)
        print(f"{key}={value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hiclaw", description="HiClaw service and setup tools")
    subparsers = parser.add_subparsers(dest="command")

    setup_parser = subparsers.add_parser("setup", help="交互式生成/更新 .env 配置")
    setup_parser.add_argument("--non-interactive", action="store_true", help="不提问，只根据参数和默认值写入 .env")
    setup_parser.add_argument("--provider", choices=["openai", "claude"])
    setup_parser.add_argument("--channel", choices=["telegram", "feishu", "none"])
    setup_parser.add_argument("--openai-api-key")
    setup_parser.add_argument("--openai-base-url")
    setup_parser.add_argument("--openai-model")
    setup_parser.add_argument("--anthropic-api-key")
    setup_parser.add_argument("--anthropic-base-url")
    setup_parser.add_argument("--anthropic-model")
    setup_parser.add_argument("--telegram-bot-token")
    setup_parser.add_argument("--owner-id")
    setup_parser.add_argument("--feishu-app-id")
    setup_parser.add_argument("--feishu-app-secret")
    setup_parser.add_argument("--tavily-api-key")
    setup_parser.add_argument("--dashboard-host")
    setup_parser.add_argument("--dashboard-port")

    doctor_parser = subparsers.add_parser("doctor", help="检查当前 .env 是否具备启动条件")
    doctor_parser.add_argument("--quiet", action="store_true", help="只返回退出码，不输出报告")
    doctor_parser.add_argument("--tui-only", action="store_true", help="只检查本地 TUI 所需配置，不要求消息通道")

    config_parser = subparsers.add_parser("config", help="命令行读取/更新 .env")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    set_parser = config_subparsers.add_parser("set", help="写入 KEY=VALUE 配置")
    set_parser.add_argument("pairs", nargs="+")
    get_parser = config_subparsers.add_parser("get", help="读取配置")
    get_parser.add_argument("keys", nargs="*")
    get_parser.add_argument("--show-secrets", action="store_true", help="显示完整密钥值；默认会隐藏 KEY/TOKEN/SECRET/PASSWORD")

    subparsers.add_parser("run", help="前台启动 HiClaw 服务，适合本地调试或进程管理器托管")
    subparsers.add_parser("start", help="后台启动 HiClaw 服务，等价于 scripts/start.sh")
    subparsers.add_parser("stop", help="停止后台 HiClaw 服务，等价于 scripts/stop.sh")
    subparsers.add_parser("status", help="查看后台 HiClaw 服务状态、日志位置和 Dashboard 地址")
    logs_parser = subparsers.add_parser("logs", help="查看后台 HiClaw 日志")
    logs_parser.add_argument("-n", "--lines", type=int, default=80, help="显示最近多少行日志，默认 80")
    logs_parser.add_argument("-f", "--follow", action="store_true", help="持续跟随日志输出")
    return parser
