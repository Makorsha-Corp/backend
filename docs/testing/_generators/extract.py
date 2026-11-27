import ast, json, os

# repo root = three levels up from docs/testing/_generators/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
LAYERS = ["app/managers", "app/services", "app/utils", "app/core", "app/integrations", "app/dao"]

out = []
for layer in LAYERS:
    d = os.path.join(ROOT, layer)
    for dirpath, _, files in os.walk(d):
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            src = open(path, encoding="utf-8").read()
            try:
                tree = ast.parse(src)
            except SyntaxError as e:
                out.append({"file": rel, "error": str(e)})
                continue
            entry = {"file": rel, "layer": layer, "classes": [], "functions": []}
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    bases = []
                    for b in node.bases:
                        bases.append(ast.unparse(b))
                    methods = []
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            methods.append({
                                "name": sub.name,
                                "async": isinstance(sub, ast.AsyncFunctionDef),
                                "lineno": sub.lineno,
                                "private": sub.name.startswith("_") and not (sub.name.startswith("__") and sub.name.endswith("__")),
                                "dunder": sub.name.startswith("__") and sub.name.endswith("__"),
                            })
                    entry["classes"].append({
                        "name": node.name,
                        "bases": bases,
                        "lineno": node.lineno,
                        "methods": methods,
                    })
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    entry["functions"].append({
                        "name": node.name,
                        "async": isinstance(node, ast.AsyncFunctionDef),
                        "lineno": node.lineno,
                        "private": node.name.startswith("_"),
                    })
            out.append(entry)

json.dump(out, open(os.path.join(os.path.dirname(__file__), "inventory.json"), "w"), indent=1)

# stats
nc = sum(len(e.get("classes", [])) for e in out)
nm = sum(len(c["methods"]) for e in out for c in e.get("classes", []))
nf = sum(len(e.get("functions", [])) for e in out)
print(f"files={len(out)} classes={nc} methods={nm} module_funcs={nf} total_callables={nm+nf}")
for e in out:
    if "error" in e:
        print("ERROR", e["file"], e["error"])
