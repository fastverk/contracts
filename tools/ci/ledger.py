"""Shared LEDGER.md row parsing for contracts CI checks.

This vehicle's Includes table is Package / Status / Source repo / Source SHA
/ Source module(name) / Source module(version) / Registry / Notes. Package
names are backtick-wrapped (`forge.v1`); source cells are markdown links.
Imported by check_drift.py so the checker does not re-implement row reading.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "LEDGER.md"

_STATUSES = frozenset({"imported", "pending", "excluded"})
_SOURCE_URL = re.compile(r"https://github.com/(?P<owner>[^/\s]+)/(?P<repo>[^)/\s]+)")


def github_repo(source: str) -> tuple[str, str] | None:
    """Return (owner, repo) from a ledger Source-repo cell, or None."""
    m = _SOURCE_URL.search(source or "")
    if not m:
        return None
    return m.group("owner"), m.group("repo").removesuffix(".git")


def parse_ledger_text(text: str) -> list[dict]:
    """Parse LEDGER.md table rows from `text`.

    Only rows whose status cell is imported / pending / excluded are kept.
    Placeholder cells (`*(none)*`, `—`) and heading / identity tables are
    skipped. Extra keys (source, sha, …) are present on include rows.
    """
    rows: list[dict] = []
    section = None
    for line in text.splitlines():
        if line.startswith("## Includes"):
            section = "include"
            continue
        if line.startswith("## Pending"):
            section = "pending"
            continue
        if line.startswith("## Excludes"):
            section = "exclude"
            continue
        if line.startswith("### ") or line.startswith("## "):
            continue
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 2:
            continue
        status = cols[1].strip("`")
        if status not in _STATUSES:
            continue
        name = cols[0].strip("`").strip()
        if not name or name in {"Package", "Name", "*(none)*"}:
            continue
        row: dict = {
            "module": name,
            "status": status,
            "section": section,
        }
        if status == "excluded":
            if len(cols) < 3:
                continue
            rows.append(row)
            continue
        if len(cols) < 6:
            continue
        row["source"] = cols[2]
        sha = cols[3].strip().strip("`")
        row["sha"] = "" if sha in {"", "—", "-"} else sha
        row["declared_name"] = cols[4].strip("`")
        row["declared_version"] = cols[5].strip("`")
        rows.append(row)
    return rows


def parse_ledger(path: Path | None = None) -> list[dict]:
    """Parse LEDGER.md from `path` (defaults to the vehicle root file)."""
    return parse_ledger_text((path or LEDGER).read_text())
