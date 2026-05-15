from __future__ import annotations

from unittest.mock import patch

import pytest

from hiclaw.agents import claude


def test_claude_env_reports_missing_api_key_clearly():
    with patch.object(claude, "ANTHROPIC_API_KEY", None):
        with pytest.raises(claude.ClaudeConfigurationError) as exc_info:
            claude.build_claude_env()

    message = str(exc_info.value)
    assert "Claude Provider 配置不完整" in message
    assert "ANTHROPIC_API_KEY" in message
    assert "AGENT_PROVIDER=openai" in message


def test_claude_env_omits_empty_optional_values():
    with patch.object(claude, "ANTHROPIC_API_KEY", " test-key "):
        with patch.object(claude, "ANTHROPIC_BASE_URL", ""):
            with patch.object(claude, "ANTHROPIC_MODEL", None):
                env = claude.build_claude_env()

    assert env == {"ANTHROPIC_API_KEY": "test-key"}
