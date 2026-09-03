#!/usr/bin/env python3
"""Tests for the report-only source-drift checker."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import check_drift


def _row(
    package: str,
    source: str = "[fastverk/forge](https://github.com/fastverk/forge)",
    sha: str = "a" * 40,
) -> dict:
    return {
        "module": package,
        "status": "imported",
        "section": "include",
        "source": source,
        "sha": sha,
    }


class _Github:
    """Path-keyed stand-in for check_drift.github_get."""

    def __init__(self, responses: dict[str, tuple[int, object | None, str]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, path: str) -> tuple[int, object | None, str]:
        self.calls.append(path)
        if path in self.responses:
            return self.responses[path]
        for key, value in self.responses.items():
            if path.startswith(key):
                return value
        raise AssertionError(f"unexpected github_get({path!r})")


class AuditRowTests(unittest.TestCase):
    def test_in_sync(self) -> None:
        gh = _Github(
            {
                "/repos/fastverk/forge": (200, {"default_branch": "main"}, ""),
                "/repos/fastverk/forge/commits/main": (200, {"sha": "b" * 40}, ""),
                f"/repos/fastverk/forge/compare/{'a' * 40}...{'b' * 40}": (
                    200,
                    {"ahead_by": 0},
                    "",
                ),
            }
        )
        with unittest.mock.patch.object(check_drift, "github_get", gh):
            result = check_drift.audit_row(_row("forge.v1"))
        self.assertEqual(result["state"], "in sync")
        self.assertEqual(result["ahead"], 0)
        self.assertEqual(result["head_sha"], "b" * 40)

    def test_drift_pluralizes_commits(self) -> None:
        gh = _Github(
            {
                "/repos/fastverk/forge": (200, {"default_branch": "main"}, ""),
                "/repos/fastverk/forge/commits/main": (200, {"sha": "b" * 40}, ""),
                f"/repos/fastverk/forge/compare/{'a' * 40}...{'b' * 40}": (
                    200,
                    {"ahead_by": 3},
                    "",
                ),
            }
        )
        with unittest.mock.patch.object(check_drift, "github_get", gh):
            result = check_drift.audit_row(_row("forge.v1"))
        self.assertEqual(result["state"], "drift")
        self.assertEqual(result["ahead"], 3)
        self.assertEqual(result["detail"], "3 commits ahead")

    def test_drift_one_commit(self) -> None:
        gh = _Github(
            {
                "/repos/fastverk/forge": (200, {"default_branch": "main"}, ""),
                "/repos/fastverk/forge/commits/main": (200, {"sha": "b" * 40}, ""),
                f"/repos/fastverk/forge/compare/{'a' * 40}...{'b' * 40}": (
                    200,
                    {"ahead_by": 1},
                    "",
                ),
            }
        )
        with unittest.mock.patch.object(check_drift, "github_get", gh):
            result = check_drift.audit_row(_row("forge.v1"))
        self.assertEqual(result["detail"], "1 commit ahead")

    def test_private_404_is_unreachable(self) -> None:
        gh = _Github(
            {
                "/repos/fastverk/agents": (
                    404,
                    None,
                    "HTTP 404; Not Found",
                ),
            }
        )
        with unittest.mock.patch.object(check_drift, "github_get", gh):
            result = check_drift.audit_row(
                _row(
                    "agent.v1",
                    source="[fastverk/agents](https://github.com/fastverk/agents) (private)",
                )
            )
        self.assertEqual(result["state"], "unreachable")
        self.assertIn("unreachable/private", result["detail"])
        self.assertEqual(gh.calls, ["/repos/fastverk/agents"])

    def test_unparseable_source(self) -> None:
        result = check_drift.audit_row(_row("odd.v1", source="not-a-url"))
        self.assertEqual(result["state"], "unreachable")
        self.assertEqual(result["detail"], "could not parse source repo URL from ledger")

    def test_empty_ledger_sha(self) -> None:
        gh = _Github(
            {
                "/repos/fastverk/forge": (200, {"default_branch": "main"}, ""),
                "/repos/fastverk/forge/commits/main": (200, {"sha": "b" * 40}, ""),
            }
        )
        with unittest.mock.patch.object(check_drift, "github_get", gh):
            result = check_drift.audit_row(_row("forge.v1", sha=""))
        self.assertEqual(result["state"], "unreachable")
        self.assertEqual(result["detail"], "ledger SHA empty")
        self.assertEqual(result["head_sha"], "b" * 40)

    def test_request_failure_does_not_raise(self) -> None:
        gh = _Github({"/repos/fastverk/forge": (500, None, "HTTP 500")})
        with unittest.mock.patch.object(check_drift, "github_get", gh):
            result = check_drift.audit_row(_row("forge.v1"))
        self.assertEqual(result["state"], "unreachable")
        self.assertIn("HTTP 500", result["detail"])


class MainTests(unittest.TestCase):
    def test_exit_1_on_drift_and_continues_past_unreachable(self) -> None:
        rows = [
            _row("forge.v1"),
            _row(
                "agent.v1",
                source="[fastverk/agents](https://github.com/fastverk/agents)",
            ),
        ]
        seen: list[str] = []

        def fake_get(path: str) -> tuple[int, object | None, str]:
            seen.append(path)
            if path.startswith("/repos/fastverk/agents"):
                return 404, None, "HTTP 404"
            if path == "/repos/fastverk/forge":
                return 200, {"default_branch": "main"}, ""
            if path == "/repos/fastverk/forge/commits/main":
                return 200, {"sha": "b" * 40}, ""
            if "compare" in path:
                return 200, {"ahead_by": 2}, ""
            raise AssertionError(path)

        with (
            unittest.mock.patch.object(check_drift, "parse_ledger", return_value=rows),
            unittest.mock.patch.object(check_drift, "github_get", fake_get),
            unittest.mock.patch("sys.stdout", new=io.StringIO()) as out,
        ):
            code = check_drift.main()
        self.assertEqual(code, 1)
        text = out.getvalue()
        self.assertIn("1 drifted", text)
        self.assertIn("1 unreachable", text)
        self.assertIn("WARNING agent.v1", text)
        self.assertIn("byte-copy", text)
        self.assertTrue(any(c.startswith("/repos/fastverk/agents") for c in seen))
        self.assertTrue(any(c.startswith("/repos/fastverk/forge") for c in seen))

    def test_exit_0_when_only_unreachable(self) -> None:
        rows = [
            _row(
                "agent.v1",
                source="[fastverk/agents](https://github.com/fastverk/agents)",
            )
        ]

        def fake_get(path: str) -> tuple[int, object | None, str]:
            return 404, None, "HTTP 404"

        with (
            unittest.mock.patch.object(check_drift, "parse_ledger", return_value=rows),
            unittest.mock.patch.object(check_drift, "github_get", fake_get),
            unittest.mock.patch("sys.stdout", new=io.StringIO()) as out,
        ):
            code = check_drift.main()
        self.assertEqual(code, 0)
        self.assertIn("drift check OK", out.getvalue())

    def test_exit_1_when_no_imported_rows(self) -> None:
        with (
            unittest.mock.patch.object(check_drift, "parse_ledger", return_value=[]),
            unittest.mock.patch("sys.stdout", new=io.StringIO()) as out,
        ):
            code = check_drift.main()
        self.assertEqual(code, 1)
        self.assertIn("no imported include rows", out.getvalue())

    def test_step_summary(self) -> None:
        results = [
            {
                "module": "forge.v1",
                "ledger_sha": "a" * 40,
                "head_sha": "b" * 40,
                "ahead": 0,
                "state": "in sync",
                "detail": "in sync",
            },
            {
                "module": "agent.v1",
                "ledger_sha": "c" * 40,
                "head_sha": "",
                "ahead": 0,
                "state": "unreachable",
                "detail": "fastverk/agents: HTTP 404 (unreachable/private)",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.md"
            with unittest.mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
                check_drift.write_step_summary(results)
            text = summary.read_text()
        self.assertIn("| Package |", text)
        self.assertIn("`forge.v1`", text)
        self.assertIn("unreachable", text)
        self.assertIn("report-only", text)


class ShortShaTests(unittest.TestCase):
    def test_truncates_and_placeholder(self) -> None:
        self.assertEqual(check_drift.short_sha("abcdefghijklmnop"), "abcdefghijkl")
        self.assertEqual(check_drift.short_sha(""), "—")
        self.assertEqual(check_drift.short_sha("   "), "—")


if __name__ == "__main__":
    unittest.main()
