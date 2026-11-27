"""Local-coder runner for stage 4 of the unit-test pipeline.

Sends ONE case card at a time to a local OpenAI-compatible server
(llama-server), puts the returned test function into the test file, runs it,
and keeps it only if it ends as designed (pass -> passed, xfail -> xfailed).
A case that still does not end as designed after the retries is taken out of
the file again and listed as "escalated" for the Claude executor.

Usage (from the backend root, with the venv python):

    .venv/Scripts/python.exe tests/unit/_tools/local_coder.py \
        tests/unit/managers/account_manager.cases.md

Derived paths (next to the cases file):
    test_<module>.py            scaffold written by the Claude executor (must exist)
    <module>.helpers.md         helper cheat sheet written by the Claude executor
    <module>.local-run.json     report written by this tool

The tool never edits app/, the cases file, or any existing test. It only
appends tests at the end of the test file.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CARD_RE = re.compile(r"^### +([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+) +[—–-] +(.+?)\s*$")
EXPECT_RE = re.compile(r"^\s*-?\s*\*\*Expect:\*\*\s*(.+?)\s*$", re.MULTILINE)
BUG_RE = re.compile(r"BUG-\d+")
AUTHOR_TAG = "# [local-coder]"
# Failures that mean "the test is broken", never "the bug is present".
SETUP_ERRORS = ("NameError", "ImportError", "ModuleNotFoundError", "SyntaxError",
                "IndentationError", "fixture '", "UnboundLocalError", "called directly",
                "FixtureFunctionDefinition", "got multiple values for keyword argument")
FAILS_RE = re.compile(r"^\s*-?\s*\*\*Fails today on:\*\*\s*(.+?)\s*$", re.MULTILINE)
THEN_MARK_RE = re.compile(r"^\s*# Then (\d+)\b")
FORBIDDEN = ("pytest.skip", "pytest.mark", "xfail(")

SYSTEM = """You write ONE pytest test function for a Python backend (SQLAlchemy + Postgres).
You are given: (1) the helpers and fixtures that already exist in the test file, \
(2) the module conventions, (3) ONE case card.

Rules — follow all of them:
1. Output exactly one Python code block with exactly one function. No other text.
2. Function name: start with the given prefix, then a short snake_case slug.
3. First docstring line: the case ID, an em dash, what the case checks. \
Second line: "Rules: " + the card's Rules line.
4. Use ONLY the fixtures and helpers listed. Do not import, redefine or invent helpers. \
Do not add decorators.
5. Given -> build exactly the rows listed, with exactly the values listed.
6. When -> make exactly the one call described.
7. Then -> one assertion (or more) per numbered line, in the same order, with the exact \
values. Use == for values. Never weaken a check (no `in`, no `is not None`, no `>=`) \
unless the card says so.
8. Never use try/except. For an expected error use `with pytest.raises(Type) as exc:` \
and then assert on `exc.value` as the card says.
9. Re-read from the database with the listed re-read helper before asserting stored values.
10. Do not add checks the card does not list. Do not skip any line of the card.
11. Do not add xfail or skip markers; the harness adds them.
12. Directly before the assertions for Then line N write the comment `# Then N` on its own \
line (N = 1, 2, 3 ... every number once, in order). If Then N starts with `raises:`, the \
comment goes directly before the `with pytest.raises(...)` line.
13. The card describes the CORRECT behaviour. Write exactly what it says, even if you think \
the code behaves differently today. Use `pytest.raises` only when a Then line starts with `raises:`.
14. Every fixture you use must be in the function's argument list. Take a "before" snapshot \
BEFORE the When call, never after it. Do not leave a variable unused.
15. Expected values are always the literals written in the card - never a value read from the row under test or from a "before" variable. A Then line that names several things (two counts, a snapshot AND "in particular" values) needs an assertion for each of them.
16. Build each Given row with exactly the columns the card names. The helper list shows examples; do not copy an example's extra values."""


def http_json(url: str, payload: dict | None = None, timeout: int = 600) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def est_tokens(text: str) -> int:
    return int(len(text) / 3.2) + 1


def parse_cards(text: str) -> tuple[str, list[dict]]:
    """Return (conventions section, cards). A card runs to the next ###/## heading."""
    lines = text.splitlines()
    conv, cards, cur, section = [], [], None, ""
    in_conv = False
    for line in lines:
        if line.startswith("## "):
            if cur:
                cards.append(cur); cur = None
            section = line[3:].strip()
            in_conv = section.lower().startswith("conventions")
            continue
        m = CARD_RE.match(line)
        if m:
            if cur:
                cards.append(cur)
            cur = {"id": m.group(1), "title": m.group(2), "section": section, "lines": [line]}
            in_conv = False
            continue
        if cur:
            cur["lines"].append(line)
        elif in_conv:
            conv.append(line)
    if cur:
        cards.append(cur)
    for c in cards:
        body = "\n".join(c.pop("lines")).rstrip()
        c["card"] = body
        m = EXPECT_RE.search(body)
        exp = m.group(1) if m else ""
        c["expect"] = "xfail" if exp.lower().startswith("xfail") else ("pass" if exp.lower().startswith("pass") else "")
        c["bugs"] = BUG_RE.findall(exp) if c["expect"] == "xfail" else []
    return "\n".join(conv).strip(), cards


def bug_titles() -> dict[str, str]:
    out = {}
    p = ROOT / "docs/testing/bugs.md"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # columns: ID | Pattern | Module | Title | ...
            if len(cells) >= 4 and re.fullmatch(r"BUG-\d+", cells[0]):
                title = cells[3].replace('"', "'").replace("`", "")
                out[cells[0]] = title if len(title) <= 110 else title[:110].rsplit(" ", 1)[0] + "…"
    return out


def extract_function(reply: str, prefix: str, case_id: str) -> tuple[str | None, str]:
    """Return (function source without decorators, error message)."""
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL)
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", reply, flags=re.DOTALL)
    code = (blocks[0] if blocks else reply).strip("\n")
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return None, f"SyntaxError in your code: {e}"
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    others = [n for n in tree.body if not isinstance(n, ast.FunctionDef)]
    if len(funcs) != 1 or others:
        return None, "Return exactly ONE function and nothing else at top level (no imports, no helpers)."
    fn = funcs[0]
    if not fn.name.startswith(prefix):
        return None, f"The function name must start with `{prefix}`."
    doc = ast.get_docstring(fn) or ""
    if not doc.startswith(case_id):
        return None, f'The docstring must start with the case ID `{case_id}`.'
    src = "\n".join(code.splitlines()[fn.lineno - 1:fn.end_lineno])
    if any(isinstance(n, ast.Try) for n in ast.walk(fn)):
        return None, "try/except is not allowed in the test (see the rules)."
    for bad in FORBIDDEN:
        if bad in src:
            return None, f"`{bad.strip()}` is not allowed in the test (see the rules)."
    return src, ""


def fixture_names(test_file: Path) -> set[str]:
    """Fixtures defined in the test file and in every conftest.py above it."""
    files = [test_file] + [d / "conftest.py" for d in test_file.parents if ROOT in (d, *d.parents)]
    out = set()
    for f in files:
        if not f.exists():
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef) and any("fixture" in ast.unparse(d) for d in node.decorator_list):
                out.add(node.name)
    return out


def string_constants(test_file: Path) -> dict[str, str]:
    """Module-level `NAME = "text"` constants of the test file (value -> name)."""
    out = {}
    for node in ast.parse(test_file.read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            out[node.value.value] = node.targets[0].id
    return out


def helper_signatures(test_file: Path) -> dict[str, tuple[list[str], int, int, bool]]:
    """Module-level helper functions of the test file (not fixtures, not tests):
    name -> (positional parameter names, required positional count, max positional count, has *args)."""
    out = {}
    for node in ast.parse(test_file.read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.FunctionDef) and not node.name.startswith("test_")
                and not any("fixture" in ast.unparse(d) for d in node.decorator_list)):
            pos = [p.arg for p in node.args.posonlyargs + node.args.args]
            out[node.name] = (pos, len(pos) - len(node.args.defaults), len(pos), node.args.vararg is not None)
    return out


def helper_arity(src: str, sigs: dict[str, tuple[list[str], int, int, bool]]) -> str:
    """A helper called with too few or too many positional arguments (`links_of(ix)` for `links_of(db, item)`).
    Lines after an xfail's failing line never run, so such a slip would otherwise be accepted."""
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in sigs:
            pos, required, most, varargs = sigs[node.func.id]
            given = len(node.args) + sum(1 for k in node.keywords if k.arg in pos)
            if given < required or (len(node.args) > most and not varargs):
                return (f"`{ast.unparse(node)}` does not match the helper `{node.func.id}({', '.join(pos)})`. "
                        f"Call every helper exactly as the helper sheet shows (most take `db` first).")
    return ""


def then_count(card: str) -> int:
    m = re.search(r"^\*\*Then\*\*\s*$(.*)", card, flags=re.MULTILINE | re.DOTALL)
    return len(re.findall(r"^\d+\. ", m.group(1), flags=re.MULTILINE)) if m else 0


def then_marks(src: str) -> list[tuple[int, int]]:
    """[(Then number, 1-based line in src)] for every `# Then N` comment."""
    return [(int(m.group(1)), i) for i, line in enumerate(src.splitlines(), 1)
            if (m := THEN_MARK_RE.match(line))]


def sheet_keywords(helpers: str, card: str) -> set[str]:
    """Builder keywords implied by a Conventions name the card uses.

    Read from the helper sheet's "Card says | Write" rows. Only definition rows count
    (`| A2 | a2 = mk_account(name="Beta Co") |`); a row whose first cell contains
    "but" is an example of a change and implies nothing.
    """
    out = set()
    for line in helpers.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.lstrip().startswith("|") or len(cells) < 2 or re.search(r"\bbut\b", cells[0]):
            continue
        tokens = re.findall(r"\b[A-Z]+\d+\b", cells[0])
        if tokens and any(re.search(rf"\b{t}\b", card) for t in tokens):
            # Only the code of the row counts, not a remark after it ("write `workspace_id=` only after but").
            code = re.findall(r"`([^`]*)`", cells[1])
            out.update(re.findall(r"\b(\w+)=", code[0] if code else cells[1]))
    return out


def tidy_args(src: str, fixtures: set[str]) -> str:
    """Drop arguments the body never reads, and non-fixture arguments the body assigns itself.

    Both are harmless slips of the model; fixing them here saves a repair round and
    the clean-up in the finishing step. The test is run after this, so a fixture that
    was needed only for its side effect would show up as a failing test.
    """
    fn = ast.parse(src).body[0]
    names = [n for n in ast.walk(fn) if isinstance(n, ast.Name)]
    loaded = {n.id for n in names if isinstance(n.ctx, ast.Load)}
    stored = {n.id for n in names if isinstance(n.ctx, ast.Store)}
    a = fn.args
    if a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs or a.defaults:
        return src
    keep = [x.arg for x in a.args if x.arg in loaded and not (x.arg not in fixtures and x.arg in stored)]
    # A fixture the body reads but the argument list forgot (`w1.id` in a dict) -> add it.
    first_use = sorted((n.lineno, n.col_offset, n.id) for n in names
                       if isinstance(n.ctx, ast.Load) and n.id in fixtures and n.id not in stored)
    for _, _, name in first_use:
        if name not in keep and name not in {x.arg for x in a.args}:
            keep.append(name)
    lines = src.splitlines()
    # `e2 = mk_entry(...)` whose name is never read -> `mk_entry(...)`
    for node in ast.walk(fn):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id not in loaded and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id in fixtures):
            i = node.lineno - 1
            lines[i] = re.sub(rf"^(\s*){re.escape(node.targets[0].id)}\s*=\s*", r"\1", lines[i])
    if len(keep) == len(a.args):
        return "\n".join(lines)
    return "\n".join([f"def {fn.name}({', '.join(keep)}):"] + lines[fn.body[0].lineno - 1:])


def normalize(src: str, card: dict, prefix: str) -> str:
    """Give the test the card's own name, docstring and comments.

    The function name and docstring are built from the card (the model copies an
    exemplar's slug, or drops part of the Rules line), and comment lines other than
    `# Then N` are removed.
    """
    fn = ast.parse(src).body[0]
    doc = fn.body[0] if isinstance(fn.body[0], ast.Expr) and isinstance(getattr(fn.body[0], "value", None), ast.Constant) else None
    title = card["title"].strip().rstrip(".")
    rm = re.search(r"^\s*-?\s*\*\*Rules:\*\*\s*(.+?)\s*$", card["card"], flags=re.MULTILINE)
    if doc is None or len(fn.body) < 2 or '"""' in title or "\\" in title or (rm and ("\\" in rm.group(1) or '"""' in rm.group(1))):
        return src
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    if len(slug) > 70:
        slug = slug[:70].rsplit("_", 1)[0]
    slug = slug.rstrip("_") or "case"
    args = ", ".join(a.arg for a in fn.args.args)
    lines = src.splitlines()
    head = [f"def {prefix}{slug}({args}):", f'    """{card["id"]} — {title}.']
    head += [f'    Rules: {rm.group(1)}"""'] if rm else []
    if not rm:
        head[-1] += '"""'
    body = [l for l in lines[doc.end_lineno:]
            if not (l.lstrip().startswith("#") and not THEN_MARK_RE.match(l))]
    while body and not body[0].strip():  # no blank line right after the docstring
        body.pop(0)
    return "\n".join(head + body)


def static_check(src: str, card: str, fixtures: set[str], conventions: str = "", helpers: str = "",
                 consts: dict[str, str] | None = None) -> str:
    """Mistakes that let a wrong test end as designed. Returns feedback, or ''."""
    fn = ast.parse(src).body[0]
    args = {x.arg for x in fn.args.args}
    names = [n for n in ast.walk(fn) if isinstance(n, ast.Name)]
    loaded = {n.id for n in names if isinstance(n.ctx, ast.Load)}
    stored = {n.id for n in names if isinstance(n.ctx, ast.Store)}
    unknown = sorted(args - fixtures)
    if unknown:
        return (f"{', '.join(unknown)} in the argument list is not a fixture. Only the listed fixtures can be "
                f"arguments; a row the test builds itself is a local variable, not an argument.")
    missing = sorted((loaded & fixtures) - args - stored)
    if missing:
        return f"You use the fixture(s) {', '.join(missing)} but they are not in the function's argument list. Add them."

    # Every standing row the card names (S1 -> fixture s1) must be used: a row swapped for
    # another one can still end as designed. Remarks in brackets outside code are not rows.
    body = card[card.find("**Given**"):] if "**Given**" in card else card
    body = re.sub(r"\s\([^\n]*\)\.?[ \t]*$", "", FAILS_RE.sub("", body), flags=re.MULTILINE)
    body = re.sub(r"\s\([^()\n]*\)", "", body)
    body = "\n".join(ln for ln in body.splitlines() if not re.search(r"\b[Nn]o\b", ln.split("`")[0]))
    body = re.sub(r'"[^"\n]*"', '""', body)  # a value such as abbreviation="U2" is not the row U2
    named = {t.lower() for t in re.findall(r"\b[A-Z]+\d+\b", body)}
    unused = sorted((named & fixtures) - loaded)
    if unused:
        return (f"The card names {', '.join(u.upper() for u in unused)}, but the test never uses "
                f"{', '.join('`' + u + '`' for u in unused)}. Build every Given row with exactly the rows the "
                f"card names, and make the When call with exactly the card's arguments.")

    def helper_call(node) -> str:
        """Name of the module-level helper a node calls ('' for builders/fixtures and non-calls)."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id not in fixtures:
            return node.func.id
        return ""

    assigns: dict[str, list[tuple[int, str]]] = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            assigns.setdefault(name, []).append((node.lineno, helper_call(node.value)))
            is_builder = (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                          and node.value.func.id in fixtures)
            # A Given line written as code (`loaded = M1.x`) is run for its effect, not its value.
            given_code = re.search(rf"`{re.escape(name)}\s*=[^=]", card, flags=re.IGNORECASE)
            if name not in loaded and not name.startswith("_") and not is_builder and not given_code:
                return (f"The variable `{name}` is assigned but never used. Either a check from the card is "
                        f"missing (compare it in an assert), or the line is not needed: remove it.")

    # Given: only the columns the card names (or a Conventions name implies).
    implied = sheet_keywords(helpers, card)
    # A column is named by the Given rows, not by the When call (every When names workspace_id).
    gm = re.search(r"\*\*Given\*\*(.*?)(?:\*\*When\*\*|\Z)", card, flags=re.DOTALL)
    given_text = gm.group(1) if gm else card
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in fixtures:
            extra = [k.arg for k in node.keywords if k.arg and k.arg not in given_text and k.arg not in implied]
            if extra:
                return (f"`{ast.unparse(node)}` sets {', '.join('`' + e + '`' for e in extra)}, which the card's "
                        f"Given does not mention. Build each row with exactly the values the card lists - "
                        f"do not copy extra values from an example.")

    # Values: literals come from the card, and the card's literals are asserted.
    doc = fn.body[0] if isinstance(fn.body[0], ast.Expr) and isinstance(getattr(fn.body[0], "value", None), ast.Constant) else None
    in_fstring = {id(c) for n in ast.walk(fn) if isinstance(n, ast.JoinedStr) for c in ast.walk(n)}
    known = card + "\n" + conventions
    for node in ast.walk(fn):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.strip()
                and id(node) not in in_fstring and (doc is None or node is not doc.value)):
            # A literal with an escape ("\tbolt\n") is compared the way it is written, so that
            # the card's own spelling is accepted and a raw string (r"\tbolt\n") is not.
            seg = ast.get_source_segment(src, node) or ""
            wm = re.match(r"""([A-Za-z]*)(["'])(.*)\2$""", seg, flags=re.DOTALL)
            if chr(92) in seg and wm:
                ok = "r" not in wm.group(1).lower() and wm.group(3) in known
            else:
                ok = node.value in known
            if not ok:
                return (f"The text {seg or repr(node.value)} is not in the card. Use only the values the card "
                        f"gives, written exactly as in the card (a plain string, not a raw string).")
    lines_ = src.splitlines()
    body_text = "\n".join(lines_[:doc.lineno - 1] + lines_[doc.end_lineno:]) if doc else src
    tm = re.search(r"^\*\*Then\*\*\s*$(.*)", card, flags=re.MULTILINE | re.DOTALL)
    for q in re.findall(r'"([^"\n]+)"', tm.group(1) if tm else ""):
        if "{" in q or "`" in q or q in body_text or (consts or {}).get(q, "\0") in body_text:
            continue
        return (f'The Then lines name the value "{q}" but your test never writes it. Assert every value a '
                f"Then line names as a literal (also the ones after \"in particular\"); never replace a "
                f"literal by a value read from the row or from a `before` variable.")

    visible = FAILS_RE.sub("", card)
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "raises" and node.args:
            for t in ast.walk(node.args[0]):
                if isinstance(t, ast.Name) and t.id not in visible:
                    return (f"`pytest.raises({t.id})` is not in the card: no Then line says `raises: {t.id}`. "
                            f"Make the When call exactly as written and assert what the Then lines say.")

    want = then_count(card)
    marks = then_marks(src)
    if want:
        if [n for n, _ in marks] != list(range(1, want + 1)):
            return (f"The card has {want} Then line(s). Write the comment `# Then N` directly before the "
                    f"assertions of each one: " + ", ".join(f"`# Then {i}`" for i in range(1, want + 1))
                    + " - each exactly once, in order.")
        lines = src.splitlines()
        ends = [ln for _, ln in marks[1:]] + [len(lines) + 1]
        tm_ = re.search(r"^\*\*Then\*\*\s*$(.*)", card, flags=re.MULTILINE | re.DOTALL)
        then_text = dict((int(a), b) for a, b in re.findall(r"^(\d+)\. (.*)$", tm_.group(1), flags=re.MULTILINE)) if tm_ else {}
        for (n, start), end in zip(marks, ends):
            block = lines[start:end - 1]
            if not any("assert " in l or "pytest.raises" in l for l in block):
                return f"There is no assertion after `# Then {n}`. Assert what Then line {n} of the card says."
            cm = re.match(r"count:.*\bhas (?:exactly )?(\d+) rows?\b", then_text.get(n, ""))
            if cm and not any(re.search(rf"==\s*{cm.group(1)}\b(?!\.)", l) for l in block):
                return (f"Then {n} says the table has {cm.group(1)} row(s): assert `== {cm.group(1)}` with the count "
                        f"helper - the card's number itself, not a value computed from a `before` variable.")
            # A Then line that lists several checks (`a is None`, `b is None`) needs one assert for each.
            listed = [seg for seg in re.findall(r"`([^`]+)`", re.sub(r"\s\([^()]*\)\.?$", "", then_text.get(n, "")))
                      if re.search(r" is | == | != | in |<=|>=|isinstance", seg)]
            got = sum(1 for l in block if l.strip().startswith("assert ") or "pytest.raises" in l)
            # A `count:` line names one count; its `==` segments are filters, not separate checks.
            if then_text.get(n, "").lstrip().startswith("count:"):
                listed = []
            if len(listed) >= 2 and got < len(listed):
                return (f"Then {n} lists {len(listed)} checks ({', '.join('`' + s + '`' for s in listed)}) but there "
                        f"{'is' if got == 1 else 'are'} only {got} assert(s) after `# Then {n}`. Write one assert for "
                        f"each check the line lists.")

    if marks:
        first = marks[0][1]
        before = [st.lineno for st in fn.body if st.lineno < first]
        after = [st for st in fn.body if st.lineno > first]
        when_line = after[0].lineno if after and isinstance(after[0], ast.With) and "raises" in ast.unparse(
            after[0].items[0].context_expr) else (before[-1] if before else first)

        def origin(node, at: int):
            if helper_call(node):
                return helper_call(node), node.lineno
            if isinstance(node, ast.Name):
                prev = [(ln, h) for ln, h in assigns.get(node.id, []) if ln < at and h]
                if prev:
                    return prev[-1][1], prev[-1][0]
            return None

        for node in ast.walk(fn):
            if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare) and len(node.test.comparators) == 1:
                a_, b_ = origin(node.test.left, node.lineno + 1), origin(node.test.comparators[0], node.lineno + 1)
                if a_ and b_ and a_[0] == b_[0] and a_[1] > when_line and b_[1] > when_line:
                    return (f"Line `{ast.unparse(node)}` compares two `{a_[0]}(...)` results that are both taken "
                            f"AFTER the When call, so it can never fail. Take the first one BEFORE the When call.")
    return ""


def fail_location(raw: str, test_file: Path, name: str, src: str) -> int | None:
    """Then number the test failed in (0 = before `# Then 1`, i.e. Given/When); None if unknown."""
    hits = re.findall(rf"{re.escape(test_file.name)}:(\d+): in {re.escape(name)}\b", raw)
    if not hits:
        return None
    file_lines = test_file.read_text(encoding="utf-8").splitlines()
    starts = [i for i, l in enumerate(file_lines, 1) if l.startswith(f"def {name}(")]
    if not starts:
        return None
    rel = int(hits[-1]) - starts[-1] + 1
    return max([n for n, ln in then_marks(src) if ln <= rel], default=0)


def run_test(test_file: Path, name: str, runxfail: bool = False) -> tuple[str, str]:
    cmd = [sys.executable, "-m", "pytest", f"{test_file}::{name}", "-q", "-p", "no:cacheprovider",
           "--tb=short", "-rfExX", "--no-header"]
    if runxfail:
        cmd.append("--runxfail")
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return "timeout", "pytest timed out after 300 s"
    out = (r.stdout or "") + (r.stderr or "")
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    for key in ("error", "failed", "xpassed", "xfailed", "passed"):
        if re.search(rf"\b\d+ {key}\b", tail):
            return key, out
    return "error", out


def trim(text: str, limit: int = 2500) -> str:
    return text if len(text) <= limit else text[:600] + "\n...\n" + text[-(limit - 600):]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", help="path to <module>.cases.md (card format)")
    ap.add_argument("--url", default="http://127.0.0.1:8080", help="llama-server base URL")
    ap.add_argument("--ids", help="comma-separated case IDs (default: every card not yet in the test file)")
    ap.add_argument("--limit", type=int, help="stop after N cases")
    ap.add_argument("--retries", type=int, default=2, help="repair attempts per case (default 2)")
    ap.add_argument("--max-tokens", type=int, default=1800)
    ap.add_argument("--think", action="store_true", help="let the model think (slower, uses context)")
    ap.add_argument("--dry-run", action="store_true", help="print the first prompt and exit")
    a = ap.parse_args()

    cases_path = (ROOT / a.cases).resolve() if not Path(a.cases).is_absolute() else Path(a.cases)
    module = cases_path.name[: -len(".cases.md")]
    test_file = cases_path.with_name(f"test_{module}.py")
    helpers_path = cases_path.with_name(f"{module}.helpers.md")
    report_path = cases_path.with_name(f"{module}.local-run.json")
    for p in (cases_path, test_file, helpers_path):
        if not p.exists():
            print(f"missing: {p}"); return 2

    conventions, cards = parse_cards(cases_path.read_text(encoding="utf-8"))
    if not cards:
        print("no case cards found (expected '### <ID> — <title>' headings)"); return 2
    helpers = helpers_path.read_text(encoding="utf-8").strip()
    existing = test_file.read_text(encoding="utf-8")
    todo = [c for c in cards if f'"""{c["id"]} ' not in existing and f'id="{c["id"]}"' not in existing]
    # A card with "- **Author:** claude" is left for the Claude executor (mocks, races, non-strict xfail).
    todo = [c for c in todo if not re.search(r"\*\*Author:\*\*\s*claude", c["card"], flags=re.IGNORECASE)]
    if a.ids:
        want = {x.strip() for x in a.ids.split(",")}
        todo = [c for c in todo if c["id"] in want]
    if a.limit:
        todo = todo[: a.limit]

    fixtures = fixture_names(test_file)
    consts = string_constants(test_file)
    sigs = helper_signatures(test_file)

    def build_user(card: dict) -> str:
        prefix = "test_" + card["id"].lower().replace("-", "_") + "__"
        # The "Fails today on" line is for the harness; shown to the model it gets asserted.
        shown = re.sub(r"\n{3,}", "\n\n", FAILS_RE.sub("", card["card"]))
        return (f"# Helpers and fixtures that already exist\n\n{helpers}\n\n"
                f"# Module conventions\n\n{conventions}\n\n"
                f"# Case to implement (callable: {card['section']})\n\n{shown}\n\n"
                f"# Output\n\nFunction name prefix: `{prefix}`\n"
                f"Return one ```python block with that one function.")

    if a.dry_run:
        print(SYSTEM, "\n\n", build_user(todo[0] if todo else cards[0])); return 0

    try:
        props = http_json(a.url + "/props", timeout=10)
    except (urllib.error.URLError, OSError) as e:
        print(f"cannot reach llama-server at {a.url}: {e}"); return 3
    n_ctx = int((props.get("default_generation_settings") or {}).get("n_ctx") or 0) or 8192
    model = Path(str(props.get("model_path") or "?")).name
    print(f"server ok · model {model} · n_ctx per slot {n_ctx} · {len(todo)} of {len(cards)} cards to do")

    titles = bug_titles()
    report = {"model": model, "n_ctx": n_ctx, "cases_file": str(cases_path.relative_to(ROOT)).replace("\\", "/"),
              "think": a.think, "cases": []}
    if report_path.exists():
        try:
            old = json.loads(report_path.read_text(encoding="utf-8"))
            done_ids = {c["id"] for c in todo}
            report["cases"] = [c for c in old.get("cases", []) if c["id"] not in done_ids]
        except (ValueError, KeyError):
            pass

    for n, card in enumerate(todo, 1):
        cid = card["id"]
        prefix = "test_" + cid.lower().replace("-", "_") + "__"
        rec = {"id": cid, "expect": card["expect"], "outcome": "escalated", "attempts": 0, "seconds": 0.0,
               "prompt_tokens": 0, "completion_tokens": 0, "reason": "", "test": ""}
        report["cases"].append(rec)
        t0 = time.time()
        if card["expect"] not in ("pass", "xfail"):
            rec["reason"] = "card has no '**Expect:** pass|xfail BUG-NNN' line"
        user = build_user(card)
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        if not rec["reason"] and est_tokens(SYSTEM + user) + a.max_tokens > n_ctx:
            rec["reason"] = f"prompt too large for n_ctx {n_ctx} (~{est_tokens(SYSTEM + user)} tokens before output)"

        while not rec["reason"] and rec["attempts"] <= a.retries:
            rec["attempts"] += 1
            payload = {"messages": messages, "temperature": 0.2, "max_tokens": a.max_tokens, "stream": False}
            if not a.think:
                payload["chat_template_kwargs"] = {"enable_thinking": False}
            try:
                resp = http_json(a.url + "/v1/chat/completions", payload)
            except (urllib.error.URLError, OSError, ValueError) as e:
                rec["reason"] = f"server error: {e}"; break
            usage = resp.get("usage") or {}
            rec["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            rec["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            reply = (resp["choices"][0]["message"].get("content") or "")
            src, err = extract_function(reply, prefix, cid)
            if src is not None:
                src = normalize(tidy_args(src, fixtures), card, prefix)
                err = (static_check(src, card["card"], fixtures, conventions, helpers, consts)
                       or helper_arity(src, sigs))
                if err:
                    rec["last_code"], src = src, None
            feedback = ""
            if src is None:
                feedback = err
            else:
                name = re.search(r"def (\w+)\(", src).group(1)
                deco = ""
                if card["expect"] == "xfail":
                    reason = "; ".join(f"{b}: {titles.get(b, '')}".rstrip(": ") for b in card["bugs"]) or "bug"
                    deco = f'@pytest.mark.xfail(strict=True, reason="{reason}")\n'
                block = f"\n\n{AUTHOR_TAG} {cid}\n{deco}{src}\n"
                before = test_file.read_text(encoding="utf-8")
                test_file.write_text(before.rstrip("\n") + "\n" + block, encoding="utf-8", newline="")
                outcome, out = run_test(test_file, name)
                ok = outcome == ("passed" if card["expect"] == "pass" else "xfailed")
                if ok and card["expect"] == "xfail":
                    _, raw = run_test(test_file, name, runxfail=True)
                    fail_lines = [l for l in raw.splitlines() if l.startswith("E ")]
                    rec["fails_on"] = " | ".join(fail_lines[:3])[:400]
                    fm = FAILS_RE.search(card["card"])
                    fails_today = fm.group(1) if fm else ""
                    tn = re.match(r"Then (\d+)", fails_today)
                    at = fail_location(raw, test_file, name, src)
                    rec["fails_in_then"] = at
                    if any(s in raw for s in SETUP_ERRORS) or not fail_lines:
                        ok = False
                        out = raw
                        feedback = ("This case documents a known bug, so the test must fail on a check - but it "
                                    "fails on a setup mistake instead (wrong name, fixture, argument or import). "
                                    "Fix the mistake.\n")
                    elif tn and at is not None and at != int(tn.group(1)) and not (at == 0 and "raises" in fails_today):
                        ok = False
                        out = raw
                        where = f"`# Then {at}`" if at else "the Given/When lines, before `# Then 1`"
                        feedback = (f"This case documents a known bug. Today the code is wrong at {fails_today}, so "
                                    f"the test must fail there and nowhere else - yours fails at {where}. "
                                    "Every other line must hold today: fix your setup or that check.\n")
                if ok:
                    rec.update(outcome="accepted", test=name)
                    break
                test_file.write_text(before, encoding="utf-8", newline="")  # take it out again
                rec["last_code"] = src
                rec["last_output"] = trim(out, 1500)
                if card["expect"] == "pass":
                    want = "PASS"
                else:
                    fm = FAILS_RE.search(card["card"])
                    want = ("FAIL, because this case documents a known bug: today the code is wrong at "
                            f"{fm.group(1) if fm else 'one Then line'} (the harness marks the test xfail). "
                            "Write the checks exactly as the card says")
                feedback += (f"The test ran and ended as `{outcome}`. It must {want}.\n"
                             f"pytest output:\n```\n{trim(out)}\n```\n"
                             "The expected values in the card are correct; do not change them. "
                             "Fix your setup, helper usage or re-read.")
            rec.setdefault("rejections", []).append(feedback.split("\n")[0][:300])
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": feedback + "\nReturn the full corrected function in one ```python block."}]
            if est_tokens("".join(m["content"] for m in messages)) + a.max_tokens > n_ctx:
                messages = messages[:2] + messages[-2:]   # keep the task and the last attempt only
        if rec["outcome"] != "accepted" and not rec["reason"]:
            rec["reason"] = f"did not end as designed after {rec['attempts']} attempts"
        rec["seconds"] = round(time.time() - t0, 1)
        print(f"[{n}/{len(todo)}] {cid:<14} {rec['outcome']:<9} attempts {rec['attempts']} · {rec['seconds']}s"
              + (f" · {rec['reason']}" if rec["outcome"] != "accepted" else ""), flush=True)
        report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")

    cs = report["cases"]
    acc = [c for c in cs if c["outcome"] == "accepted"]
    report["totals"] = {
        "cases": len(cs), "accepted": len(acc), "escalated": len(cs) - len(acc),
        "accepted_first_try": sum(1 for c in acc if c["attempts"] == 1),
        "seconds": round(sum(c["seconds"] for c in cs), 1),
        "prompt_tokens": sum(c["prompt_tokens"] for c in cs),
        "completion_tokens": sum(c["completion_tokens"] for c in cs),
    }
    report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report["totals"]))
    print(f"report: {report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
