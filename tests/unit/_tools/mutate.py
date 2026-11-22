"""Small mutation-testing runner for the unit-test pipeline (Windows-friendly).

Usage:
    .venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/item.py tests/unit/dao/test_item.py
        [--lines 40-90] [--timeout 120] [--json out.json]

For each mutation of the target file it runs the test file against a mutated
COPY of the backend (in a temp dir) — the real app/ is never modified. Only
tests expected to pass are run (`-m "not xfail"`): an xfail test that starts
passing on a mutant would otherwise look like a kill.

A mutant is KILLED if any test fails, SURVIVED if all pass, TIMEOUT if the run
hangs. A run with errors but no failures is repeated once, and only a second
non-clean run counts as a kill. Survivors are the weak spots of the test suite.

Mutation operators (one change per mutant):
  cmp      ==/!=, </<=/>/>=, is/is not, in/not in swapped
  bool     `and` <-> `or`
  not      `not x` -> `x`
  if       `if c:` -> `if not (c):`
  const    True<->False, int n -> n+1, non-empty str -> ""
  return   `return <expr>` -> `return None`
  raise    `raise X` -> `pass`
  arith    + <-> -, * <-> /
"""
import argparse
import ast
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]
PY = sys.executable

CMP_SWAP = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.In: ast.NotIn, ast.NotIn: ast.In,
}
ARITH_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}


def _mutation_sites(tree):
    """Yield (node_index, operator, description, line) for every mutable node."""
    for idx, node in enumerate(ast.walk(tree)):
        line = getattr(node, "lineno", None)
        col = getattr(node, "col_offset", 0)
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                if type(op) in CMP_SWAP:
                    yield idx, ("cmp", i), f"{type(op).__name__} -> {CMP_SWAP[type(op)].__name__}", line, col
        elif isinstance(node, ast.BoolOp):
            yield idx, ("bool",), f"{type(node.op).__name__} -> {'Or' if isinstance(node.op, ast.And) else 'And'}", line, col
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            yield idx, ("not",), "drop `not`", line, col
        elif isinstance(node, ast.If):
            yield idx, ("if",), "negate if-condition", line, col
        elif isinstance(node, ast.Constant) and not isinstance(node.value, bytes):
            v = node.value
            if isinstance(v, bool):
                yield idx, ("const",), f"{v} -> {not v}", line, col
            elif isinstance(v, int):
                yield idx, ("const",), f"{v} -> {v + 1}", line, col
            elif isinstance(v, str) and v and not _is_docstring(tree, node):
                yield idx, ("const",), f"{v[:20]!r} -> ''", line, col
        elif isinstance(node, ast.Return) and node.value is not None:
            if not (isinstance(node.value, ast.Constant) and node.value.value is None):
                yield idx, ("return",), "return None", line, col
        elif isinstance(node, ast.Raise):
            yield idx, ("raise",), "raise -> pass", line, col
        elif isinstance(node, ast.BinOp) and type(node.op) in ARITH_SWAP:
            yield idx, ("arith",), f"{type(node.op).__name__} -> {ARITH_SWAP[type(node.op)].__name__}", line, col


_DOCSTRINGS: set[int] = set()


def _collect_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                _DOCSTRINGS.add(id(body[0].value))


def _is_docstring(_tree, node):
    return id(node) in _DOCSTRINGS


def _apply(tree, node_index, op):
    tree = copy.deepcopy(tree)
    node = list(ast.walk(tree))[node_index]
    kind = op[0]
    if kind == "cmp":
        node.ops[op[1]] = CMP_SWAP[type(node.ops[op[1]])]()
    elif kind == "bool":
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif kind == "not":
        _replace(tree, node, node.operand)
    elif kind == "if":
        node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
    elif kind == "const":
        v = node.value
        node.value = (not v) if isinstance(v, bool) else (v + 1 if isinstance(v, int) else "")
    elif kind == "return":
        node.value = ast.Constant(value=None)
    elif kind == "raise":
        _replace(tree, node, ast.Pass())
    elif kind == "arith":
        node.op = ARITH_SWAP[type(node.op)]()
    return ast.fix_missing_locations(tree)


def _replace(tree, old, new):
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if item is old:
                        value[i] = new
                        return
            elif value is old:
                setattr(parent, field, new)
                return


def _make_copy(dst: Path):
    for name in ("app", "tests", "alembic"):
        shutil.copytree(BACKEND / name, dst / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_tools"))
    for name in ("alembic.ini", "pytest.ini", ".env"):
        if (BACKEND / name).exists():
            shutil.copy2(BACKEND / name, dst / name)


def _run_tests(workdir: Path, test_file: str, timeout: int, retried: bool = False):
    env = {**os.environ, "UNIT_TESTS_SKIP_MIGRATE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    cmd = [PY, "-m", "pytest", test_file, "-q", "-x", "-p", "no:cacheprovider",
           "-m", "not xfail", "--no-header", "-o", "addopts="]
    try:
        r = subprocess.run(cmd, cwd=workdir, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ""
    if r.returncode == 0:
        return "SURVIVED", ""
    tail = r.stdout[-400:]
    # A run that only errored proves nothing yet: a clash with another run looks the same as a real kill.
    if not retried and not re.search(r"\d+ failed", tail):
        return _run_tests(workdir, test_file, timeout, retried=True)
    return "KILLED", tail


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # the report prints arrows; a redirected Windows stream is cp1252
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("test_file")
    ap.add_argument("--lines", help="only mutate lines in this range, e.g. 40-90")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--json", help="write full results to this path")
    a = ap.parse_args()

    src = (BACKEND / a.target).read_text(encoding="utf-8")
    tree = ast.parse(src)
    _collect_docstrings(tree)
    lo, hi = (map(int, a.lines.split("-")) if a.lines else (0, 10**9))
    sites = [s for s in _mutation_sites(tree) if s[3] and lo <= s[3] <= hi]

    # Migrate once, then every mutant run skips it.
    subprocess.run([PY, "-m", "pytest", "tests/unit/test_harness.py", "-q", "-p", "no:cacheprovider"],
                   cwd=BACKEND, capture_output=True)

    work = Path(tempfile.mkdtemp(prefix="mutate-"))
    try:
        _make_copy(work)
        base, _ = _run_tests(work, a.test_file, a.timeout)
        if base != "SURVIVED":
            print("Unmutated test run does not pass cleanly — fix the tests first.", file=sys.stderr)
            sys.exit(2)
        results = []
        target_copy = work / a.target
        for n, (idx, op, desc, line, col) in enumerate(sites, 1):
            mutated = ast.unparse(_apply(tree, idx, op))
            target_copy.write_text(mutated, encoding="utf-8")
            status, tail = _run_tests(work, a.test_file, a.timeout)
            results.append({"id": n, "line": line, "col": col, "operator": op[0], "change": desc,
                            "status": status, "killed_by": tail.strip().splitlines()[-1:] if tail else []})
            print(f"[{n}/{len(sites)}] L{line}:{col} {op[0]:6} {desc:32} {status}", flush=True)
        target_copy.write_text(src, encoding="utf-8")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    killed = sum(r["status"] == "KILLED" for r in results)
    timeouts = sum(r["status"] == "TIMEOUT" for r in results)
    survived = [r for r in results if r["status"] == "SURVIVED"]
    score = (killed + timeouts) / len(results) * 100 if results else 100.0
    print(f"\nMutants: {len(results)} · killed {killed} · timeout {timeouts} · survived {len(survived)}"
          f" · score {score:.0f}%")
    for r in survived:
        print(f"  SURVIVED #{r['id']} L{r['line']}:{r['col']} {r['operator']}: {r['change']}")
    if a.json:
        Path(a.json).write_text(json.dumps({"target": a.target, "tests": a.test_file,
                                            "score": score, "results": results}, indent=2))


if __name__ == "__main__":
    main()
