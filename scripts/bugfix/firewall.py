"""Feedback firewall: check a message before it reaches the bug fixer.

The fixer must never learn how a fix is tested (docs/bugfix/pipeline.md §3).
Every fix brief and every feedback message goes through this check first:

    python scripts/bugfix/firewall.py docs/bugfix/units/<unit>/brief.md
    python scripts/bugfix/firewall.py - < feedback.txt

Rejected (exit 1, findings printed) if the text contains:
  - a path under tests/ or a test/test-plan file name;
  - the words xfail, assert, pytest, fixture, conftest, monkeypatch, parametrize;
  - the id of any test case card (every `### <ID>` heading in tests/**/*.cases.md);
  - the name of any test function (every `def test_...` in tests/**);
  - a line copied from a test file (any line of 30+ characters that also appears
    verbatim in a test file, ignoring surrounding whitespace).
Spec rule ids (R3c, R5g ...), bug ids (BUG-123), house rules (HR-15) and owner
answers (OQ-66) are allowed: they describe the requirement, not the test.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"

WORDS = re.compile(r"\b(xfail|xpass\w*|assert\w*|pytest|fixtures?|conftest|monkeypatch|parametri[sz]e)\b", re.IGNORECASE)
PATHS = re.compile(r"(^|[\s`'\"(\[\\/])tests[\\/]|\btest_[\w-]+\.py\b|\.(cases|notes|verify|helpers)\.md\b", re.IGNORECASE)
CARD_HEADING = re.compile(r"^###\s+([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)\b", re.MULTILINE)
TEST_DEF = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)", re.MULTILINE)
MIN_COPY = 30


def _load_index() -> tuple[set[str], set[str], set[str]]:
    cards: set[str] = set()
    names: set[str] = set()
    lines: set[str] = set()
    for p in TESTS.rglob("*.cases.md"):
        cards.update(CARD_HEADING.findall(p.read_text(encoding="utf-8", errors="replace")))
    for p in TESTS.rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="replace")
        names.update(TEST_DEF.findall(text))
        for ln in text.splitlines():
            s = ln.strip()
            if len(s) >= MIN_COPY and not s.startswith("#"):
                lines.add(s)
    return cards, names, lines


def check(text: str) -> list[str]:
    findings: list[str] = []
    cards, names, test_lines = _load_index()
    for m in WORDS.finditer(text):
        findings.append(f"test word {m.group(0)!r}")
    for m in PATHS.finditer(text):
        findings.append(f"test path {m.group(0).strip()!r}")
    tokens = set(re.findall(r"[A-Za-z0-9_-]+", text))
    for c in sorted(tokens & cards):
        findings.append(f"test case id {c!r}")
    for n in sorted(tokens & names):
        findings.append(f"test function name {n!r}")
    for ln in text.splitlines():
        s = ln.strip()
        if len(s) >= MIN_COPY and s in test_lines:
            findings.append(f"line copied from a test file: {s[:80]!r}")
    return sorted(set(findings))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    text = sys.stdin.read() if argv[1] == "-" else Path(argv[1]).read_text(encoding="utf-8")
    findings = check(text)
    if findings:
        print(f"FIREWALL: REJECTED ({len(findings)} finding(s)) - rewrite as behaviour + spec rule:")
        for f in findings:
            print("  -", f)
        return 1
    print("FIREWALL: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
