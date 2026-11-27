# Checklist generators

The three checklist files in `docs/testing/` are **generated**. Regenerate them
after any change under `app/managers`, `app/services`, `app/utils`, `app/core`,
`app/integrations`, or `app/dao`.

```bash
# from the repo root, with the project venv active
python docs/testing/_generators/extract.py    # AST-walks the 6 layers -> inventory.json
python docs/testing/_generators/deadcode.py   # repo-wide reference scan -> deadcode.json
python docs/testing/_generators/gen.py        # writes the 3 .md files into docs/testing/
```

`inventory.json` and `deadcode.json` are intermediate artifacts (git-ignored).

| Script | Output |
|---|---|
| `extract.py` | Every class / method / module function in the 6 layers, with line numbers and `private`/`async`/`dunder` tags. |
| `deadcode.py` | Heuristic: names never referenced anywhere in `app/`, `tests/`, `alembic/`, `scripts/`. Skips pydantic-validator methods and framework hooks. |
| `gen.py` | `unit-test-checklist-by-layer.md`, `unit-test-checklist-by-domain.md`, `dead-code-removal-checklist.md`. Domain mapping lives in the `DOMAIN` dict here — add new files there. |
