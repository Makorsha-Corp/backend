"""PreToolUse guard for the bug-fixer agent: the fixer must never see a test.

Wired in .claude/agents/bug-fixer.md (frontmatter hooks), so it runs only while
that agent is active. Reads the hook JSON on stdin; exit 2 blocks the call and
the message on stderr is shown to the agent.

Blocked: any path, glob, search target or shell command that reaches
  - a `tests` directory (tests/, tests\\, /tests, \\tests, `tests` as a path part),
  - test files (test_*.py, *_test.py, conftest.py, factories.py under tests),
  - test plans and reports (*.cases.md, *.notes.md, *.verify.md, *.helpers.md),
  - the pipeline's private files: in docs/bugfix/units/<unit>/ only brief.md,
    feedback-*.md and fix-notes.md may be opened (no listing or globbing the folder);
    flipcheck, wrong-tests.md and questions.md are blocked,
  - git commands that can print other trees or history (show, log -p, diff, grep,
    cat-file, archive, stash, checkout/restore/switch of another ref).
This is best-effort string checking; the fixer also works in a sparse worktree
with tests/ removed, and the tester audits the fixer's diff.
"""
from __future__ import annotations

import json
import re
import sys

PATH_PATTERNS = [
    r"(^|[\\/\s'\"=:(])tests([\\/]|$|[\s'\")])",   # a tests directory
    r"(^|[\\/])test_[\w-]*\.py\b",
    r"\b[\w-]+_test\.py\b",
    r"\bconftest\.py\b",
    r"\.(cases|notes|verify|helpers)\.md\b",
    r"\bflipcheck\b",
    r"\bwrong-tests\.md\b",
    # inside a unit folder the fixer may open only brief.md, feedback-*.md and fix-notes.md
    r"docs[\\/]bugfix[\\/]units([\\/][^\\/\s'\"]*)?([\\/]\*|\*|$|[\s'\"])",
    r"docs[\\/]bugfix[\\/]units[\\/][^\\/\s'\"]+[\\/](?!brief\.md|feedback-[\w-]*\.md|fix-notes\.md)[^\\/\s'\"]+",
    r"docs[\\/]bugfix[\\/](wrong-tests|questions)\.md",
    r"\bxfail\b",
]
GIT_BLOCK = re.compile(
    r"\bgit\b[^|;&]*\b(show|log|diff|grep|cat-file|archive|stash|ls-tree|ls-files|"
    r"checkout|restore|switch|worktree|blame|rev-list|reflog)\b"
)
PATH_RE = re.compile("|".join(PATH_PATTERNS), re.IGNORECASE)

MSG = (
    "Blocked by the bug-fix firewall: the fixer works from the fix brief only and "
    "may not read tests, test plans, test reports or git history. Fix the behaviour "
    "described in your brief; write your own throwaway checks under your scratch "
    "folder if you need to confirm it."
)


def texts_to_check(tool: str, ti: dict) -> list[str]:
    keys = {
        "Read": ["file_path"],
        "Edit": ["file_path"],
        "Write": ["file_path"],
        "NotebookEdit": ["notebook_path"],
        "Glob": ["pattern", "path"],
        "Grep": ["path", "glob", "pattern"],
        "Bash": ["command"],
        "PowerShell": ["command"],
    }.get(tool)
    if keys is None:
        return [json.dumps(ti)]
    return [str(ti.get(k) or "") for k in keys]


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("Bug-fix firewall could not read the tool call, so it is blocked.", file=sys.stderr)
        return 2  # fail closed
    tool = data.get("tool_name", "")
    ti = data.get("tool_input") or {}
    for text in texts_to_check(tool, ti):
        if not text:
            continue
        if PATH_RE.search(text):
            print(MSG, file=sys.stderr)
            return 2
        if tool in ("Bash", "PowerShell") and GIT_BLOCK.search(text):
            print(MSG + " Git commands that can show other files or history are blocked; "
                  "list the files you changed in your fix notes instead.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
