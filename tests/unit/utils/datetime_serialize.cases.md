# Test cases — `app/utils/datetime_serialize.py`

> **Spec:** `tests/unit/utils/datetime_serialize.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — re-run on the same APPROVED spec (source commit e48a092, no rule changes). Verifier verdict PASS with no findings and no `case-missing` survivors (all 9 survivors are in the dead `serialize_utc_datetime`), so no cases were added, changed or retired.
> **Counts:** 21 cases · 17 expected-to-pass · 4 expected-to-fail (bugs) · 1 deferred

## Reviewer summary
- **Per callable:** `ensure_utc_z_in_json` 21 cases (4 bug: BUG-160 x2, BUG-161, BUG-162). `serialize_utc_datetime` has no cases: the reviewer marked it dead code to remove (spec "Not specified").
- **Notable design choices:**
  - Case lists of similar strings (invalid calendar values, non-matching shapes, non-ASCII digits) are one case each, **parametrized** over the listed values. For the xfail ones, every value fails today, so strict xfail holds for each one.
  - Each bug rule is split. The parts that already work are pass cases: invalid values never raise (E-05), other trailing characters stay unchanged (E-08), and datetime fields gain `Z` through `AppResponseModel` (E-20). The buggy parts are xfail cases.
  - "Nesting depth is unlimited" is tested at depth 200, well under Python's recursion limit (best-practice default, delegated by reviewer).
  - R3 and R8 say values are "returned as is", so those cases check identity (`is`), not only equality. R1 and R2 say "new dict/list", so those cases check `is not` and that the input was not mutated.
  - R9 is tested through a throw-away `AppResponseModel` subclass (schema-level target). The `UtcJsonResponseMiddleware` half is deferred to integration tests.
- **Needs a decision:** None.

## Conventions for this module
- IDs: `DTS` = datetime_serialize; `E` = `ensure_utc_z_in_json`.
- `f` = `ensure_utc_z_in_json`. It is a pure function: no database, no app, no mocks. The database fixture is not needed.
- `DT` = the string `"2026-01-01T10:00:00"`.
- "Not mutated": before the call, take `copy.deepcopy(input)`. After the call, assert `input == that copy`.
- `M` = a throw-away subclass of `AppResponseModel` (from `app.schemas.base`) with the fields given in the case. Serialize it with `model_dump(mode="json")`.
- Externals mocked: none. Race simulations: none.
- Parametrized cases: the executor writes one test function per case ID, parametrized over the listed values (param ids may be readable labels). For xfail cases, the xfail mark goes on the whole test.

## `ensure_utc_z_in_json`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DTS-E-01 | R4 | happy | `DT` | `f(DT)` | returns `"2026-01-01T10:00:00Z"` (a `str`) | pass |
| DTS-E-02 | R4 | boundary | fraction variants: `"2026-01-01T10:00:00.120000"`, `"2026-01-01T10:00:00.5"` (one digit), `"2026-01-01T10:00:00.123456789"` (nine digits) | `f(s)` for each | returns `s + "Z"` exactly; the fraction is kept character for character (`.120000Z`, `.5Z`, `.123456789Z`) | pass |
| DTS-E-03 | R4 (valid side of R4a) | boundary | real calendar edges: `"2024-02-29T23:59:59"` (leap day), `"2026-02-28T12:00:00"`, `"2026-04-30T10:00:00"`, `"2026-12-31T23:59:59"`, `"2026-01-01T00:00:00"`, `"2026-12-31T23:59:59.999999"` | `f(s)` for each | returns `s + "Z"` | pass |
| DTS-E-04 | R4a [BUG-160] | bug | invalid calendar values of the matching shape: `"2026-13-01T10:00:00"` (month 13), `"2026-00-01T10:00:00"` (month 0), `"2026-01-32T10:00:00"` (day 32), `"2026-01-00T10:00:00"` (day 0), `"2026-02-30T10:00:00"`, `"2025-02-29T10:00:00"` (not a leap year), `"2026-04-31T10:00:00"`, `"2026-01-01T24:00:00"` (hour 24), `"2026-01-01T10:60:00"` (minute 60), `"2026-01-01T10:00:60"` (second 60), `"9999-99-99T99:99:99"`, `"2026-02-30T10:00:00.5"` | `f(s)` for each | returns `s` unchanged (no `Z`) | xfail BUG-160 — fails today on: the result is `s + "Z"` |
| DTS-E-05 | R4a, Errors row "none" | error | `"2026-13-45T25:61:61"` and `"9999-99-99T99:99:99"` | `f(s)` for each | no exception is raised; the result is a `str` that starts with `s` (true today with `Z` and after the fix without it) | pass |
| DTS-E-06 | R5 | boundary | non-matching strings: `"2026-01-01T10:00:00Z"`, `"2026-01-01T10:00:00.120000Z"`, `"2026-01-01T10:00:00+06:00"`, `"2026-01-01T10:00:00-05:00"`, `"2026-01-01T10:00:00.5+06:00"`, `"2026-01-01"`, `"2026-01-01 10:00:00"`, `"2026-01-01t10:00:00"`, `"2026-01-01T10:00"`, `"2026-01-01T10:00:00."`, `" 2026-01-01T10:00:00"`, `"2026-01-01T10:00:00 "`, `"at 2026-01-01T10:00:00"`, `"2026-01-01T10:00:00 UTC"`, `"\n2026-01-01T10:00:00"`, `"20260-01-01T10:00:00"` (5-digit year), `"226-01-01T10:00:00"` (3-digit year), `"2026-1-01T10:00:00"` (1-digit month), `""`, `"hello"` | `f(s)` for each | returns a string equal to `s` (unchanged) | pass |
| DTS-E-07 | R6 [BUG-161] | bug | `"2026-01-01T10:00:00\n"` (one trailing newline) | `f(s)` | returns `"2026-01-01T10:00:00\n"` unchanged | xfail BUG-161 — fails today on: the result is `"2026-01-01T10:00:00\nZ"` |
| DTS-E-08 | R6 | boundary | other trailing characters: `"2026-01-01T10:00:00\n\n"`, `"2026-01-01T10:00:00\r\n"`, `"2026-01-01T10:00:00\t"`, `"2026-01-01T10:00:00x"` | `f(s)` for each | returns `s` unchanged | pass |
| DTS-E-09 | R7 [BUG-162] | bug | non-ASCII decimal digits: `"٢٠٢٦-01-01T10:00:00"` (Arabic-Indic year), `"২০২৬-০১-০১T১০:০০:০০"` (all Bengali), `"2026-01-01T10:00:00.১২"` (Bengali only in the fraction), `"２０２６-01-01T10:00:00"` (fullwidth year) | `f(s)` for each | returns `s` unchanged (no `Z`) | xfail BUG-162 — fails today on: the result is `s + "Z"` |
| DTS-E-10 | R1, Side effects | happy | `d = {"b": DT, "a": 1, "c": "x"}` | `r = f(d)` | `r == {"b": "2026-01-01T10:00:00Z", "a": 1, "c": "x"}`; `list(r.keys()) == ["b", "a", "c"]` (order kept); `r is not d`; `d` not mutated (still `{"b": DT, "a": 1, "c": "x"}`) | pass |
| DTS-E-11 | R1 | boundary | `d = {DT: DT, "k": "v"}` (a key that looks like a date-time) | `r = f(d)` | `r == {"2026-01-01T10:00:00": "2026-01-01T10:00:00Z", "k": "v"}`; the key `"2026-01-01T10:00:00Z"` is not in `r`; `list(r.keys()) == [DT, "k"]` | pass |
| DTS-E-12 | R2, Side effects | happy | `l = [DT, 5, "x", None, "2026-01-01T10:00:00.5"]` | `r = f(l)` | `r == ["2026-01-01T10:00:00Z", 5, "x", None, "2026-01-01T10:00:00.5Z"]`; `type(r) is list`; `len(r) == 5`; `r is not l`; `l` not mutated | pass |
| DTS-E-13 | R1, R2, Side effects | happy | nested `n = {"items": [{"at": DT, "tags": ["2026-01-01T10:00:00.5", {"deep": [[DT]]}]}], "meta": {"created": DT, "count": 2}}` | `r = f(n)` | `r == {"items": [{"at": "2026-01-01T10:00:00Z", "tags": ["2026-01-01T10:00:00.5Z", {"deep": [["2026-01-01T10:00:00Z"]]}]}], "meta": {"created": "2026-01-01T10:00:00Z", "count": 2}}`; `r["items"] is not n["items"]`; `r["meta"] is not n["meta"]`; `n` not mutated | pass |
| DTS-E-14 | R2, R1 | boundary | `{}` and `[]` | `f({})`, `f([])` | returns `{}` (type `dict`) and `[]` (type `list`) | pass |
| DTS-E-15 | R2 | boundary | `DT` wrapped 200 levels deep, alternating `[...]` and `{"k": ...}` (build it in a loop; best-practice default, delegated by reviewer) | `r = f(value)` | no exception; unwrapping `r` along the same 200-level path gives `"2026-01-01T10:00:00Z"` | pass |
| DTS-E-16 | R3 | boundary | `t = (DT,)`, `s = {DT}`, and `l = [DT, t]` | `f(t)`, `f(s)`, `f(l)` | `f(t) is t` and it equals `("2026-01-01T10:00:00",)`; `f(s) is s` and it equals `{"2026-01-01T10:00:00"}`; `f(l) == ["2026-01-01T10:00:00Z", ("2026-01-01T10:00:00",)]` and `f(l)[1] is t` | pass |
| DTS-E-17 | R8 | boundary | scalars: `42`, `0`, `3.5`, `True`, `False`, `None`, `dt = datetime(2026, 1, 1, 10, 0)` | `f(v)` for each | `f(v) is v` for each; for `dt`, the result is still a `datetime` (not a `str`) equal to `datetime(2026, 1, 1, 10, 0)` | pass |
| DTS-E-18 | R8, R1 | boundary | `d = {"n": 0, "f": 0.0, "b": False, "x": None, "d": datetime(2026, 1, 1, 10, 0)}` | `r = f(d)` | `r == d`; `r["d"] is d["d"]` and it is a `datetime`; `r["b"] is False`; `r["x"] is None` | pass |
| DTS-E-19 | R9 [BUG-160] | bug | target `schema`: `M` with `note: str = "2026-01-01T10:00:00"` and `at: datetime = datetime(2026, 1, 1, 10, 0)` | `M().model_dump(mode="json")` | `result["note"] == "2026-01-01T10:00:00"` (unchanged); `result["at"] == "2026-01-01T10:00:00Z"` | xfail BUG-160 — fails today on: `result["note"] == "2026-01-01T10:00:00Z"` |
| DTS-E-20 | R9 | happy | target `schema`: `M` with `note: str = "hello"` and `at: datetime = datetime(2026, 1, 1, 10, 0)` | `M().model_dump(mode="json")` | `result == {"note": "hello", "at": "2026-01-01T10:00:00Z"}` (the datetime field gains `Z`, today and after the fix) | pass |
| DTS-E-21 | R10 | happy | `v = {"a": DT, "b": [DT + ".5", "2026-01-01T10:00:00Z", "2026-01-01T10:00:00+06:00", "9999-99-99T99:99:99", "2026-01-01T10:00:00\n", "٢٠٢٦-01-01T10:00:00", "", 7, None], "c": (DT,)}` | `once = f(v)`; `twice = f(once)` | `twice == once`; `once["a"] == "2026-01-01T10:00:00Z"` (the first pass did change something). This holds both today and after the fixes. | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `ensure_utc_z_in_json` R9 (middleware half) [BUG-160] | `UtcJsonResponseMiddleware` (`app/core/utc_json_middleware.py`), integration test on an `/api/` endpoint | A free-text `str` field whose value is `"2026-01-01T10:00:00"` comes back unchanged in the HTTP JSON body, while a naive datetime field in the same body gains `Z` (xfail BUG-160 until fixed). |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `ensure_utc_z_in_json` | R1 | DTS-E-10, DTS-E-11, DTS-E-13, DTS-E-14, DTS-E-18 |
| `ensure_utc_z_in_json` | R2 | DTS-E-12, DTS-E-13, DTS-E-14, DTS-E-15 |
| `ensure_utc_z_in_json` | R3 | DTS-E-16 |
| `ensure_utc_z_in_json` | R4 | DTS-E-01, DTS-E-02, DTS-E-03 |
| `ensure_utc_z_in_json` | R4a [BUG-160] | DTS-E-04 (xfail), DTS-E-05 |
| `ensure_utc_z_in_json` | R5 | DTS-E-06 |
| `ensure_utc_z_in_json` | R6 [BUG-161] | DTS-E-07 (xfail), DTS-E-08 |
| `ensure_utc_z_in_json` | R7 [BUG-162] | DTS-E-09 (xfail) |
| `ensure_utc_z_in_json` | R8 | DTS-E-17, DTS-E-18 |
| `ensure_utc_z_in_json` | R9 [BUG-160] | DTS-E-19 (xfail), DTS-E-20; middleware half deferred |
| `ensure_utc_z_in_json` | R10 | DTS-E-21 |
| `ensure_utc_z_in_json` | Errors: none / never raises | DTS-E-05 |
| `ensure_utc_z_in_json` | Side effects: input not mutated | DTS-E-10, DTS-E-12, DTS-E-13 |
| `serialize_utc_datetime` | Not specified (dead code, remove) | — |
