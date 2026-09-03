#!/usr/bin/env python3
"""Tests for contracts LEDGER.md parsing."""

from __future__ import annotations

import unittest
from pathlib import Path

from ledger import LEDGER, github_repo, parse_ledger, parse_ledger_text

SAMPLE = """# Ledger

| This repo | `module(name)` | `module(version)` |
| --- | --- | --- |
| [fastverk/contracts](https://github.com/fastverk/contracts) | `fastverk_contracts` | `0.0.1` |

## Includes (public proto packages)

| Package | Status | Source repo | Source SHA | Source `module(name)` | Source `module(version)` | Registry (`registry.tbzl.dev`) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `forge.v1` | imported | [fastverk/forge](https://github.com/fastverk/forge) | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `forge` | `0.0.6` | `forge` 0.0.1–0.0.6 | `proto/forge/v1/forge.proto` |
| `tracker.v1` | imported | [fastverk/tracker](https://github.com/fastverk/tracker) | `bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb` | `tracker` | `0.0.4` | `tracker` 0.0.1–0.0.4 | proto only |
| `agent.v1` | imported | [fastverk/agents](https://github.com/fastverk/agents) (private) | `cccccccccccccccccccccccccccccccccccccccc` | `fastverk_agents` | `0.1.0` | *not published* | private source |
| `later.v1` | pending | [fastverk/later](https://github.com/fastverk/later) | — | `later` | `0.0.1` | *not published* | follow-up |

### Source module names — do not silently rename

| Source repo | Published / declared module | What this repo publishes |
| --- | --- | --- |
| `fastverk/forge` | `forge` 0.0.6 | proto only, under `fastverk_contracts` |

## Pending

| Package | Status | Source | Notes |
| --- | --- | --- | --- |
| *(none)* | — | — | placeholder |

## Excludes

| Name | Status | Why excluded |
| --- | --- | --- |
| botnoc leftover protos | excluded | leftover / non-platform contract |
| spec corpus | excluded | separate corpus |

## Import method

Byte-copy of proto/.
"""


class GithubRepoTests(unittest.TestCase):
    def test_markdown_link(self) -> None:
        self.assertEqual(
            github_repo("[fastverk/forge](https://github.com/fastverk/forge)"),
            ("fastverk", "forge"),
        )

    def test_markdown_link_private_suffix(self) -> None:
        self.assertEqual(
            github_repo(
                "[fastverk/agents](https://github.com/fastverk/agents) (private)"
            ),
            ("fastverk", "agents"),
        )

    def test_strips_git_suffix(self) -> None:
        self.assertEqual(
            github_repo("https://github.com/fastverk/wave.git"),
            ("fastverk", "wave"),
        )

    def test_unparseable(self) -> None:
        self.assertIsNone(github_repo(""))
        self.assertIsNone(github_repo("fastverk/forge"))
        self.assertIsNone(github_repo("not a url"))


class ParseLedgerTextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = parse_ledger_text(SAMPLE)
        self.by_name = {r["module"]: r for r in self.rows}

    def test_imported_include_rows(self) -> None:
        imported = [
            r
            for r in self.rows
            if r["section"] == "include" and r["status"] == "imported"
        ]
        self.assertEqual(
            [r["module"] for r in imported],
            ["forge.v1", "tracker.v1", "agent.v1"],
        )
        self.assertEqual(
            self.by_name["forge.v1"]["sha"],
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        self.assertEqual(self.by_name["forge.v1"]["declared_name"], "forge")
        self.assertEqual(self.by_name["forge.v1"]["declared_version"], "0.0.6")
        self.assertIn("github.com/fastverk/agents", self.by_name["agent.v1"]["source"])

    def test_pending_include_with_empty_sha(self) -> None:
        later = self.by_name["later.v1"]
        self.assertEqual(later["status"], "pending")
        self.assertEqual(later["section"], "include")
        self.assertEqual(later["sha"], "")

    def test_skips_identity_source_module_and_placeholder_tables(self) -> None:
        names = {r["module"] for r in self.rows}
        self.assertNotIn("fastverk/contracts", names)
        self.assertNotIn("fastverk_contracts", names)
        self.assertNotIn("fastverk/forge", names)
        self.assertNotIn("*(none)*", names)
        self.assertNotIn("Package", names)

    def test_excludes_with_spaces(self) -> None:
        excluded = [r for r in self.rows if r["status"] == "excluded"]
        self.assertEqual(
            [r["module"] for r in excluded],
            ["botnoc leftover protos", "spec corpus"],
        )
        self.assertTrue(all(r["section"] == "exclude" for r in excluded))


class ParseLiveLedgerTests(unittest.TestCase):
    def test_imported_include_rows_match_vehicle(self) -> None:
        self.assertTrue(LEDGER.is_file(), f"missing {LEDGER}")
        imported = [
            r
            for r in parse_ledger()
            if r.get("section") == "include" and r.get("status") == "imported"
        ]
        self.assertEqual(
            [r["module"] for r in imported],
            [
                "forge.v1",
                "tracker.v1",
                "fastverk.finder.v1",
                "wave.v1",
                "agent.v1",
            ],
        )
        expected = {
            "forge.v1": (
                "fastverk",
                "forge",
                "98591f75f411701cea00bcd0cf54f803cc2a140d",
            ),
            "tracker.v1": (
                "fastverk",
                "tracker",
                "3927db97f7904e5362271187177175b82a39a005",
            ),
            "fastverk.finder.v1": (
                "fastverk",
                "service-finder",
                "abc764147a63ef0c48b84ad102010980ed8d5415",
            ),
            "wave.v1": (
                "fastverk",
                "wave",
                "c689d650fe33e34507c42d3dcb65c56954454a07",
            ),
            "agent.v1": (
                "fastverk",
                "agents",
                "9312188d1b35f5f109fa5340c2845db577552e63",
            ),
        }
        for row in imported:
            owner, repo, sha = expected[row["module"]]
            self.assertEqual(github_repo(row["source"]), (owner, repo))
            self.assertEqual(row["sha"], sha)

    def test_path_override(self) -> None:
        empty = Path(__file__).with_name("test_ledger.py").parent / "ledger.py"
        # The parser module has no tables; override must not fall back to LEDGER.md.
        self.assertEqual(parse_ledger(empty), [])


if __name__ == "__main__":
    unittest.main()
