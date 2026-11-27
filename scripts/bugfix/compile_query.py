"""Print the Postgres SQL a DAO method would send, without a database.

    PYTHONPATH=. python scripts/bugfix/compile_query.py app.dao.order_template:order_template_dao.get_by_workspace workspace_id=1 limit=5

Calls the method with a stub session whose query chain records the final query
instead of executing it, then prints the compiled SQL (Postgres dialect, literal
values inlined where possible). Use it to check joins, subquery correlation,
AND/OR precedence and ORDER BY after changing a query.
Keyword values are parsed as Python literals (1, "x", None, True).
"""
from __future__ import annotations

import ast
import importlib
import sys

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query, Session


class _Captured(Exception):
    def __init__(self, query):
        self.query = query


def _capture(self, *a, **k):
    raise _Captured(self)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    target, *kv = argv[1:]
    mod_name, attr_path = target.split(":")
    obj = importlib.import_module(mod_name)
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    kwargs = {}
    for item in kv:
        k, v = item.split("=", 1)
        try:
            kwargs[k] = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            kwargs[k] = v
    for name in ("all", "first", "one", "one_or_none", "scalar", "count"):
        setattr(Query, name, _capture)
    db = Session()
    try:
        obj(db, **kwargs)
        print("method returned without running a query")
        return 1
    except _Captured as c:
        stmt = c.query.statement
        try:
            sql = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        except Exception:  # noqa: BLE001  (fall back to bound parameters)
            sql = stmt.compile(dialect=postgresql.dialect())
        print(sql)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
