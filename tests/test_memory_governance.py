from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hiclaw.memory import frequency, store
from hiclaw.tasks import scheduler


class MemoryGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.memory_dir = self.base / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_dir = self.memory_dir / "conversations"
        self.long_term_dir = self.memory_dir / "long_term"
        self.candidates_dir = self.memory_dir / "candidates"
        self.archive_dir = self.memory_dir / "archive"
        self.reports_dir = self.memory_dir / "reports"
        self.summaries_dir = self.memory_dir / "session_summaries"
        for path in (
            self.conversations_dir,
            self.long_term_dir,
            self.candidates_dir,
            self.archive_dir,
            self.reports_dir,
            self.summaries_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

        self.claude_memory_file = self.memory_dir / "CLAUDE.md"
        self.working_state_file = self.memory_dir / "working_state.json"
        self.conflicts_file = self.memory_dir / "conflicts.jsonl"
        self.frequency_file = self.memory_dir / "frequency.json"
        self.importance_file = self.memory_dir / "importance.json"

        self.profile_file = self.long_term_dir / "profile.md"
        self.preferences_file = self.long_term_dir / "preferences.md"
        self.rules_file = self.long_term_dir / "rules.md"

        self.stack = ExitStack()
        self.stack.enter_context(patch.object(store, "MEMORY_DIR", self.memory_dir))
        self.stack.enter_context(patch.object(store, "CONVERSATIONS_DIR", self.conversations_dir))
        self.stack.enter_context(patch.object(store, "LONG_TERM_MEMORY_DIR", self.long_term_dir))
        self.stack.enter_context(patch.object(store, "MEMORY_CANDIDATES_DIR", self.candidates_dir))
        self.stack.enter_context(patch.object(store, "MEMORY_ARCHIVE_DIR", self.archive_dir))
        self.stack.enter_context(patch.object(store, "MEMORY_REPORTS_DIR", self.reports_dir))
        self.stack.enter_context(patch.object(store, "SESSION_SUMMARIES_DIR", self.summaries_dir))
        self.stack.enter_context(patch.object(store, "CLAUDE_MEMORY_FILE", self.claude_memory_file))
        self.stack.enter_context(patch.object(store, "WORKING_STATE_FILE", self.working_state_file))
        self.stack.enter_context(patch.object(store, "MEMORY_CONFLICTS_FILE", self.conflicts_file))
        self.stack.enter_context(
            patch.object(
                store,
                "LONG_TERM_FILES",
                {
                    "profile": self.profile_file,
                    "preferences": self.preferences_file,
                    "rules": self.rules_file,
                },
            )
        )
        self.stack.enter_context(patch.object(frequency, "MEMORY_FREQUENCY_FILE", self.frequency_file))
        self.stack.enter_context(patch.object(frequency, "MEMORY_IMPORTANCE_FILE", self.importance_file))
        store.ensure_memory_files()

    def tearDown(self) -> None:
        self.stack.close()
        self.temp_dir.cleanup()

    def test_slot_conflict_is_archived_and_logged(self) -> None:
        first = store.create_memory_metadata(category="preferences", slot="style", source="user_explicit", confidence="high")
        second = store.create_memory_metadata(category="preferences", slot="style", source="user_explicit", confidence="high")

        store.append_structured_long_term_memory("以后回答简洁一点", "preferences", "style", first)
        store.append_structured_long_term_memory("以后回答详细一点", "preferences", "style", second)

        content = self.preferences_file.read_text(encoding="utf-8")
        self.assertIn("以后回答详细一点", content)
        self.assertNotIn("以后回答简洁一点", content)

        archive_files = list(self.archive_dir.glob("preferences_superseded_*.md"))
        self.assertTrue(archive_files)
        self.assertIn("以后回答简洁一点", archive_files[0].read_text(encoding="utf-8"))

        conflict_lines = self.conflicts_file.read_text(encoding="utf-8").splitlines()
        self.assertTrue(conflict_lines)
        payload = json.loads(conflict_lines[0])
        self.assertEqual(payload["slot"], "style")
        self.assertEqual(payload["resolution"], "superseded_by_newer_memory")

    def test_context_snapshot_prefers_relevant_entries_and_skips_expired(self) -> None:
        active = store.create_memory_metadata(category="rules", slot="reply_rule", source="user_explicit", confidence="high")
        expired = store.create_memory_metadata(
            category="rules",
            slot="temp_rule",
            source="user_explicit",
            confidence="medium",
            scope="temporary",
            valid_until="2000-01-01T00:00:00",
        )
        store.append_structured_long_term_memory("回答时先给结论再展开", "rules", "reply_rule", active)
        store.append_structured_long_term_memory("今晚临时用很长的寒暄开场", "rules", "temp_rule", expired)

        snapshot = store.build_context_snapshot(None, "先给我结论")
        self.assertIn("回答时先给结论再展开", snapshot)
        self.assertNotIn("今晚临时用很长的寒暄开场", snapshot)

    def test_reflection_applies_rewrite_and_candidate_promotion(self) -> None:
        store.append_structured_long_term_memory(
            "以后回答简洁一点",
            "preferences",
            "style",
            store.create_memory_metadata(category="preferences", slot="style", source="user_explicit", confidence="high"),
        )
        store.append_structured_long_term_memory(
            "这是待归档的旧规则",
            "rules",
            "legacy",
            store.create_memory_metadata(category="rules", slot="legacy", source="user_explicit", confidence="medium"),
        )
        candidate = store.append_memory_candidate(
            "以后默认用中文回答",
            category="preferences",
            reason="language_preference",
            slot="language",
            metadata=store.create_memory_metadata(
                category="preferences",
                slot="language",
                reason="language_preference",
                source="user_candidate",
                confidence="high",
            ),
        )

        @dataclass
        class FakeTextBlock:
            text: str

        @dataclass
        class FakeAssistantMessage:
            content: list[FakeTextBlock]

        @dataclass
        class FakeResultMessage:
            result: str | None = None

        class FakeClaudeAgentOptions:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        async def fake_query(prompt, options):
            payload = {
                "rewrite_memories": [
                    {
                        "category": "preferences",
                        "slot": "style",
                        "content": "回答时先给结论，再按需展开。",
                        "confidence": "high",
                        "reason": "nightly_reflection",
                        "scope": "global",
                        "valid_until": "",
                    }
                ],
                "promote_candidates": [
                    {
                        "name": candidate.name,
                        "category": "preferences",
                        "slot": "language",
                    }
                ],
                "archive_slots": [
                    {
                        "category": "rules",
                        "slot": "legacy",
                        "reason": "obsolete",
                    }
                ],
            }
            yield FakeAssistantMessage([FakeTextBlock(json.dumps(payload, ensure_ascii=False))])

        fake_module = SimpleNamespace(
            AssistantMessage=FakeAssistantMessage,
            ResultMessage=FakeResultMessage,
            TextBlock=FakeTextBlock,
            ClaudeAgentOptions=FakeClaudeAgentOptions,
            query=fake_query,
        )

        with patch.object(store, "AGENT_PROVIDER", "claude"), patch.object(store, "ANTHROPIC_API_KEY", "test-key"), patch.dict(sys.modules, {"claude_agent_sdk": fake_module}):
            report = asyncio.run(store.reflect_and_rewrite_memories())

        self.assertTrue(report["used_model"])
        self.assertEqual(len(report["applied_rewrites"]), 1)
        self.assertEqual(len(report["promoted_candidates"]), 1)
        self.assertEqual(len(report["archived_slots"]), 1)
        self.assertTrue((self.reports_dir / report["report_file"]).exists())

        preferences = self.preferences_file.read_text(encoding="utf-8")
        self.assertIn("回答时先给结论，再按需展开。", preferences)
        self.assertIn("以后默认用中文回答", preferences)
        self.assertFalse(candidate.exists())

    def test_auto_promote_preserves_candidate_metadata(self) -> None:
        candidate = store.append_memory_candidate(
            "以后默认使用中文回答",
            category="preferences",
            reason="explicit_remember",
            slot="language",
            metadata=store.create_memory_metadata(
                category="preferences",
                slot="language",
                reason="explicit_remember",
                source="user_candidate",
                confidence="high",
                scope="global",
            ),
        )

        promoted = store.auto_promote_candidates()
        self.assertEqual(len(promoted), 1)
        self.assertFalse(candidate.exists())

        content = self.preferences_file.read_text(encoding="utf-8")
        self.assertIn("以后默认使用中文回答", content)
        self.assertIn("memory-meta:", content)
        self.assertIn('"confidence": "high"', content)

    def test_archive_old_memories_handles_temporary_scope(self) -> None:
        temporary = store.create_memory_metadata(
            category="rules",
            slot="temporary_rule",
            source="user_explicit",
            confidence="medium",
            scope="temporary",
        )
        store.append_structured_long_term_memory("今晚临时使用正式语气", "rules", "temporary_rule", temporary)

        content = self.rules_file.read_text(encoding="utf-8")
        aged = content.replace("## 自动记忆 ", "## 自动记忆 2000-01-01 00:00:00")
        self.rules_file.write_text(aged, encoding="utf-8")

        archived = store.archive_old_memories()
        self.assertTrue(archived)
        self.assertNotIn("今晚临时使用正式语气", self.rules_file.read_text(encoding="utf-8"))
        archive_text = archived[0].read_text(encoding="utf-8")
        self.assertIn("今晚临时使用正式语气", archive_text)

    def test_reflection_fallback_still_writes_report(self) -> None:
        with patch.object(store, "AGENT_PROVIDER", "openai"), patch.object(store, "ANTHROPIC_API_KEY", ""):
            report = asyncio.run(store.reflect_and_rewrite_memories())
        self.assertFalse(report["used_model"])
        self.assertTrue((self.reports_dir / report["report_file"]).exists())

    def test_scheduler_memory_meditation_runs_reflection_then_cleanup(self) -> None:
        call_order: list[str] = []

        async def fake_reflect():
            call_order.append("reflect")
            return {"used_model": True, "applied_rewrites": [], "promoted_candidates": [], "archived_slots": []}

        def fake_meditate():
            call_order.append("meditate")
            return {"merged_memories": [], "cleaned_memories": []}

        with patch.object(scheduler, "reflect_and_rewrite_memories", fake_reflect), patch.object(scheduler, "meditate_and_organize_memories", fake_meditate):
            asyncio.run(scheduler.run_memory_meditation())

        self.assertEqual(call_order, ["reflect", "meditate"])


if __name__ == "__main__":
    unittest.main()
