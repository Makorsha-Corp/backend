# -*- coding: utf-8 -*-
"""Heuristic unused-callable finder.

Collects every referenced identifier (ast.Name loads, ast.Attribute attrs,
decorator names, __all__ strings) across the whole repo, then flags defined
functions/methods/classes whose name is never referenced anywhere outside its
own definition site.

Heuristic caveats (may produce false 'unused'):
 - dynamic dispatch / getattr / string-keyed registries
 - name collisions can HIDE a real unused (false 'used')
"""
import ast, json, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCAN_DIRS = ["app", "tests", "alembic", "scripts"]
LAYERS = ["app/managers", "app/services", "app/utils", "app/core", "app/integrations", "app/dao"]

used_names = set()          # every identifier referenced anywhere
def_files = {}              # rel path -> source

def iter_py(dirs):
    for d in dirs:
        for dp, _, fs in os.walk(os.path.join(ROOT, d)):
            if "__pycache__" in dp:
                continue
            for f in fs:
                if f.endswith(".py"):
                    yield os.path.join(dp, f)

# ---- pass 1: collect all referenced identifiers repo-wide ----
for path in iter_py(SCAN_DIRS):
    src = open(path, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            used_names.add(node.attr)
        elif isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                used_names.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # covers __all__, getattr("x"), router strings etc.
            s = node.value.strip()
            if s.isidentifier():
                used_names.add(s)

FRAMEWORK_OK = {"dispatch"}  # starlette middleware entrypoint
VALIDATOR_DECOS = {"field_validator", "validator", "model_validator", "root_validator",
                   "field_serializer", "model_serializer", "computed_field"}

# collect methods decorated as pydantic validators/serializers -> framework-invoked
validator_methods = set()  # (file, name)
for path in iter_py(LAYERS):
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                d = dec.func if isinstance(dec, ast.Call) else dec
                dn = d.attr if isinstance(d, ast.Attribute) else getattr(d, "id", "")
                if dn in VALIDATOR_DECOS:
                    validator_methods.add((rel, node.name))

def is_frameworky(name, file=None):
    if name.startswith("__") and name.endswith("__"):
        return True
    if name in FRAMEWORK_OK:
        return True
    if file is not None and (file, name) in validator_methods:
        return True
    return False

# ---- pass 2: for each layer file, find defs never referenced ----
INV = json.load(open(os.path.join(os.path.dirname(__file__), "inventory.json")))
report = []
for e in INV:
    if "error" in e or e.get("layer") not in LAYERS:
        continue
    unused_here = []
    for c in e["classes"]:
        if c["name"] not in used_names:
            unused_here.append(("class", c["name"], c["lineno"]))
        for m in c["methods"]:
            if is_frameworky(m["name"], e["file"]):
                continue
            if m["name"] not in used_names:
                unused_here.append(("method", f'{c["name"]}.{m["name"]}', m["lineno"]))
    for fn in e["functions"]:
        if is_frameworky(fn["name"], e["file"]):
            continue
        if fn["name"] not in used_names:
            unused_here.append(("func", fn["name"], fn["lineno"]))
    if unused_here:
        report.append((e["file"], unused_here))

total = sum(len(u) for _, u in report)
print(f"Potentially-unused callables: {total} in {len(report)} files\n")
for fpath, items in sorted(report):
    print(f"## {fpath}")
    for kind, name, ln in items:
        print(f"  - [{kind}] {name}  (L{ln})")
    print()

json.dump(report, open(os.path.join(os.path.dirname(__file__), "deadcode.json"), "w"), indent=1)
