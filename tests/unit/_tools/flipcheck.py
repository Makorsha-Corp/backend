"""Flip check: prove a bug fix changed only the tests it was meant to change.

Two steps:

  1. Record every test's outcome on a commit:
       python tests/unit/_tools/flipcheck.py run --out before.json
     (runs `pytest tests -n 4` with a small plugin; pass extra pytest args after `--`)

  2. Compare two recordings:
       python tests/unit/_tools/flipcheck.py compare before.json after.json --bugs BUG-001,BUG-002

Rules (docs/bugfix/pipeline.md §4):
  - A *target* test is one whose BEFORE xfail reason names one of --bugs.
    It must be `passed` AFTER (the tester removed its marker and the fix made it pass).
    A target test that also names a bug NOT in --bugs may stay xfailed (reported as a note).
  - A non-strict xfail test that is not a target may go xfailed <-> xpassed (physical-order ties).
  - Every other test must have exactly the same outcome before and after.
  - A test that disappears is a rejection. A new test is a rejection unless it passed
    (the pipeline does not add tests, so new tests are reported for a human to look at).

Exit code 0 = clean, 1 = rejected, 2 = usage error. `--json` writes the full report.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
BUG_RE = re.compile(r"BUG-\d+")

# ---------------------------------------------------------------------------
# pytest plugin (loaded with -p flipcheck_plugin via PYTHONPATH)
# ---------------------------------------------------------------------------

PLUGIN_SOURCE = r'''
import json, os
import pytest

_OUT = os.environ["FLIPCHECK_OUT"]
_results = {}

def _xfail_info(item):
    m = item.get_closest_marker("xfail")
    if m is None:
        return None
    reason = m.kwargs.get("reason", m.args[0] if m.args and isinstance(m.args[0], str) else "")
    strict = m.kwargs.get("strict", item.config.getini("xfail_strict"))
    return {"reason": str(reason), "strict": bool(strict)}

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if call.when == "setup":
        rep.user_properties.append(("flipcheck_xfail", json.dumps(_xfail_info(item))))

def pytest_runtest_logreport(report):
    # Runs on the controller (xdist) or in-process. One final outcome per nodeid.
    nid = report.nodeid
    props = dict(report.user_properties)
    entry = _results.setdefault(nid, {"outcome": None, "xfail": None})
    if "flipcheck_xfail" in props:
        entry["xfail"] = json.loads(props["flipcheck_xfail"])
    if report.when == "setup" and report.failed:
        entry["outcome"] = "error"
    elif report.when == "setup" and report.skipped:
        entry["outcome"] = "xfailed" if hasattr(report, "wasxfail") else "skipped"
    elif report.when == "call":
        if hasattr(report, "wasxfail"):
            entry["outcome"] = "xfailed" if report.skipped else ("xpassed" if report.passed else "failed")
        else:
            entry["outcome"] = report.outcome  # passed / failed
    elif report.when == "teardown" and report.failed and entry["outcome"] == "passed":
        entry["outcome"] = "error"

def pytest_collectreport(report):
    if report.failed:
        _results[report.nodeid or "<collection>"] = {"outcome": "collect-error", "xfail": None}

def pytest_sessionfinish(session):
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return  # only the controller writes
    with open(_OUT, "w", encoding="utf-8") as f:
        json.dump(_results, f, indent=0, sort_keys=True)
'''


def cmd_run(args: argparse.Namespace) -> int:
    out = Path(args.out).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "flipcheck_plugin.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
        env = {**os.environ, "FLIPCHECK_OUT": str(out),
               "PYTHONPATH": tmp + os.pathsep + os.environ.get("PYTHONPATH", "")}
        # Same dummy values as CI's legacy job: a few tests build signed URLs and only need them set.
        for k in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"):
            env.setdefault(k, "ci")
        cmd = [sys.executable, "-m", "pytest", *args.paths, "-q", "-o", "addopts=",
               "-p", "no:cacheprovider", "-p", "flipcheck_plugin"]
        if args.workers:
            cmd += ["-n", str(args.workers)]
        cmd += args.pytest_args
        print("flipcheck:", " ".join(cmd), flush=True)
        proc = subprocess.run(cmd, cwd=BACKEND_ROOT, env=env)
    if not out.exists():
        print("flipcheck: no results written (pytest crashed?)", file=sys.stderr)
        return 2
    data = json.loads(out.read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=BACKEND_ROOT,
                          capture_output=True, text=True).stdout.strip()
    data = {"_meta": {"commit": head, "pytest_exit": proc.returncode}, "tests": data}
    out.write_text(json.dumps(data, indent=0, sort_keys=True), encoding="utf-8")
    counts: dict[str, int] = {}
    for e in data["tests"].values():
        counts[e["outcome"]] = counts.get(e["outcome"], 0) + 1
    print(f"flipcheck: recorded {len(data['tests'])} tests at {head[:10]}: {counts}")
    return 0


def _bugs_of(entry: dict | None) -> set[str]:
    if not entry or not entry.get("xfail"):
        return set()
    return set(BUG_RE.findall(entry["xfail"].get("reason", "")))


def compare(before: dict, after: dict, bugs: set[str]) -> dict:
    b, a = before["tests"], after["tests"]
    report = {"ok": True, "flipped_as_intended": [], "rejections": [], "notes": []}

    def reject(nid, why):
        report["ok"] = False
        report["rejections"].append({"test": nid, "why": why})

    for nid, eb in sorted(b.items()):
        ea = a.get(nid)
        ob = eb["outcome"]
        if ea is None:
            reject(nid, f"missing after the fix (was {ob})")
            continue
        oa = ea["outcome"]
        named = _bugs_of(eb)
        target = bool(named & bugs)
        if target:
            if oa == "passed":
                report["flipped_as_intended"].append(nid)
            elif named - bugs and oa in ("xfailed",):
                report["notes"].append({"test": nid, "note": f"also needs {sorted(named - bugs)}; still xfailed"})
            else:
                reject(nid, f"target test for {sorted(named & bugs)} is {oa} after (was {ob}); expected passed")
            continue
        nonstrict = eb.get("xfail") is not None and not eb["xfail"].get("strict", True)
        if nonstrict and {ob, oa} <= {"xfailed", "xpassed"}:
            continue
        if ob != oa:
            reject(nid, f"{ob} -> {oa} (not a target of {sorted(bugs)})")

    for nid, ea in sorted(a.items()):
        if nid not in b:
            if ea["outcome"] == "passed":
                report["notes"].append({"test": nid, "note": "new test (passed) - pipeline should not add tests"})
            else:
                reject(nid, f"new test with outcome {ea['outcome']}")

    targets_before = [n for n, e in b.items() if _bugs_of(e) & bugs]
    if not targets_before:
        reject("<none>", f"no test before names any of {sorted(bugs)}: wrong bug ids or wrong base run")
    unmatched = sorted(bugs - set().union(*(_bugs_of(e) for e in b.values())))
    if unmatched:
        report["notes"].append({"test": "<bugs>", "note": f"no test names {unmatched}"})
    return report


def cmd_compare(args: argparse.Namespace) -> int:
    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))
    bugs = {x.strip() for x in args.bugs.split(",") if x.strip()}
    rep = compare(before, after, bugs)
    rep["before_commit"] = before.get("_meta", {}).get("commit")
    rep["after_commit"] = after.get("_meta", {}).get("commit")
    rep["bugs"] = sorted(bugs)
    if args.json:
        Path(args.json).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(f"flipcheck: {'CLEAN' if rep['ok'] else 'REJECTED'} for {', '.join(sorted(bugs))}")
    print(f"  flipped as intended: {len(rep['flipped_as_intended'])}")
    for r in rep["rejections"][:50]:
        print(f"  REJECT {r['test']}: {r['why']}")
    if len(rep["rejections"]) > 50:
        print(f"  ... {len(rep['rejections']) - 50} more")
    for n in rep["notes"]:
        print(f"  note {n['test']}: {n['note']}")
    return 0 if rep["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the suite and record every test's outcome")
    r.add_argument("--out", required=True)
    r.add_argument("--workers", type=int, default=4, help="xdist workers (0 = no xdist)")
    r.add_argument("--paths", nargs="+", default=["tests"])
    r.add_argument("pytest_args", nargs="*", help="extra pytest args (after --)")
    c = sub.add_parser("compare", help="compare two recordings")
    c.add_argument("before")
    c.add_argument("after")
    c.add_argument("--bugs", required=True, help="comma-separated BUG ids this fix targets")
    c.add_argument("--json", help="write the full report here")
    args = p.parse_args(argv)
    return cmd_run(args) if args.cmd == "run" else cmd_compare(args)


if __name__ == "__main__":
    sys.exit(main())
