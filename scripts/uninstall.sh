#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${HICLAW_INSTALL_DIR:-$HOME/.hiclaw/hiclaw-py}"
BIN_DIR="${HICLAW_BIN_DIR:-$HOME/.local/bin}"
KEEP_DATA="${HICLAW_KEEP_DATA:-0}"

info() {
    printf '\033[1;36m==>\033[0m %s\n' "$1"
}

warn() {
    printf '\033[1;33mWarning:\033[0m %s\n' "$1"
}

fail() {
    printf '\033[1;31mError:\033[0m %s\n' "$1" >&2
    exit 1
}

assert_safe_install_dir() {
    local parent
    local resolved
    parent="$(dirname "$INSTALL_DIR")"
    if [ -d "$parent" ]; then
        resolved="$(cd "$parent" && pwd)/$(basename "$INSTALL_DIR")"
    else
        resolved="$INSTALL_DIR"
    fi
    case "$resolved" in
        "/"|"$HOME"|"$HOME/"|"$HOME/.hiclaw"|"$HOME/.local"|"/opt"|"/usr"|"/usr/local"|"/tmp")
            fail "Refusing to remove broad directory: $resolved. Set HICLAW_INSTALL_DIR to the exact HiClaw install path."
            ;;
    esac
}

remove_file() {
    local path="$1"
    if [ -e "$path" ] || [ -L "$path" ]; then
        rm -f "$path"
        echo "Removed $path"
    fi
}

remove_dir() {
    local path="$1"
    if [ -d "$path" ]; then
        rm -rf "$path"
        echo "Removed $path"
    fi
}

main() {
    info "Uninstalling HiClaw"
    if [ "$KEEP_DATA" != "1" ]; then
        assert_safe_install_dir
    fi

    remove_file "$BIN_DIR/hiclaw"
    remove_file "$BIN_DIR/hiclaw-tui"
    remove_file "$BIN_DIR/hiclaw-dashboard"
    remove_file "$BIN_DIR/hiclaw-feishu"

    if [ "$KEEP_DATA" = "1" ]; then
        warn "Keeping install directory because HICLAW_KEEP_DATA=1: $INSTALL_DIR"
    else
        remove_dir "$INSTALL_DIR"
    fi

    parent_dir="$(dirname "$INSTALL_DIR")"
    if [ "$KEEP_DATA" != "1" ] && [ "$parent_dir" != "$HOME" ] && [ -d "$parent_dir" ]; then
        rmdir "$parent_dir" 2>/dev/null || true
    fi

    echo ""
    info "HiClaw uninstall complete"
    echo "If your shell still finds hiclaw, open a new terminal or remove stale PATH entries manually."
}

main "$@"
