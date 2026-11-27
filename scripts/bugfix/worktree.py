"""Per-unit git worktrees for the bug-fix pipeline (docs/bugfix/pipeline.md §2.2).

    python scripts/bugfix/worktree.py create  <unit> [--base origin/main]
    python scripts/bugfix/worktree.py blind   <unit>   # remove tests/ before the fixer runs
    python scripts/bugfix/worktree.py unblind <unit>   # restore tests/ for the tester
    python scripts/bugfix/worktree.py path    <unit>
    python scripts/bugfix/worktree.py remove  <unit>   # after the PR is merged or the unit is dropped

<unit> is a short slug like `dao-department`. The branch is `bugfix/<unit>`, and the
worktree lives in ../bugfix-worktrees/<unit> next to this checkout.

"blind" uses a non-cone sparse checkout that keeps everything except tests/ and the
tester's private notes, so the files are not on disk for the fixer at all. The fixer
agent's own guard hook (.claude/hooks/fixer_guard.py) blocks reaching them by any
other path. Always run `blind` before handing a unit to the fixer, `unblind` before
the tester.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WT_ROOT = ROOT.parent / "bugfix-worktrees"
BLIND_PATTERNS = ["/*", "!/tests/", "!/docs/bugfix/units/*/tester*", "!/docs/bugfix/wrong-tests.md"]


def git(*args: str, cwd: Path = ROOT) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr}")
    return r.stdout.strip()


def wt_path(unit: str) -> Path:
    return WT_ROOT / unit


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, unit = argv[1], argv[2]
    path = wt_path(unit)
    if cmd == "create":
        base = argv[4] if len(argv) > 4 and argv[3] == "--base" else "origin/main"
        git("fetch", "-q", "origin")
        WT_ROOT.mkdir(exist_ok=True)
        git("worktree", "add", "-b", f"bugfix/{unit}", str(path), base)
        print(path)
    elif cmd == "blind":
        git("sparse-checkout", "set", "--no-cone", *BLIND_PATTERNS, cwd=path)
        leftover = [p for p in ("tests", "docs/bugfix/wrong-tests.md") if (path / p).exists()]
        if leftover:
            sys.exit(f"blind failed, still on disk: {leftover}")
        print(f"blind: tests/ removed from {path}")
    elif cmd == "unblind":
        git("sparse-checkout", "disable", cwd=path)
        print(f"unblind: tests/ restored in {path}")
    elif cmd == "path":
        print(path)
    elif cmd == "remove":
        git("worktree", "remove", "--force", str(path))
        print(f"removed {path} (branch bugfix/{unit} kept)")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
