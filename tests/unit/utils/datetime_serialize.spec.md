# Spec — `app/utils/datetime_serialize.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. User-typed text that looks like a date-time gets a "Z" appended — 🐞 BUG-160
**Background:** Every API response built on `AppResponseModel` (and every `/api/` JSON response, via `UtcJsonResponseMiddleware`) is passed through `ensure_utc_z_in_json`. It does not know which values are date-time fields: it appends `Z` to **any** string value of the exact shape `YYYY-MM-DDTHH:MM:SS[.fraction]`, including free text the user typed.
**What happens today:** A string field whose whole value is e.g. `2026-01-01T10:00:00` is returned as `2026-01-01T10:00:00Z`, even though it is not a date-time field.
**Example:** A user saves an item note / reference number `2026-01-01T10:00:00`. Reading it back through the API returns `2026-01-01T10:00:00Z` — the value the user sees differs from what they typed. (Also true for impossible values such as `9999-99-99T99:99:99`, which become `9999-99-99T99:99:99Z`.)
**Rules affected:** `ensure_utc_z_in_json` R4, R9
**Suggested answer:** bug — only values that are date-time fields gain the UTC `Z`; free-text strings are returned exactly as stored (fix at the type level, e.g. a UTC-aware datetime serializer, not by string pattern matching)
**Answer:** bug — only values that are date-time fields gain the UTC `Z`; free-text strings are returned exactly as stored (fix at the type level, e.g. a UTC-aware datetime serializer, not by string pattern matching) (reviewer accepted suggestion)
**Resolution:** only values serialized from `datetime` fields gain the UTC `Z`; `str` fields are returned exactly as stored, through both `AppResponseModel` and `UtcJsonResponseMiddleware`. Fix belongs at the type level (a UTC datetime serializer on `AppResponseModel` / a shared annotated datetime type), not in this string walker. Until that fix lands, the walker must at least never rewrite a string that is not a real calendar date-time (best-practice default, delegated by reviewer). Rules: `ensure_utc_z_in_json` R4a, R9.

### Q2. A date-time string followed by a line break gets "Z" after the line break — 🐞 BUG-161
**Background:** The pattern check uses `$`, which in Python also matches just before one trailing newline.
**What happens today:** A string `2026-01-01T10:00:00\n` (date-time plus one trailing newline) is treated as a naive date-time and becomes `2026-01-01T10:00:00\nZ` — the `Z` lands on a new line.
**Example:** A user pastes `2026-01-01T10:00:00` followed by Enter into a text field; the API returns the text with a stray `Z` on a second line.
**Rules affected:** `ensure_utc_z_in_json` R6
**Suggested answer:** bug — only a string that is entirely a naive date-time (no trailing newline) is matched; `2026-01-01T10:00:00\n` is returned unchanged
**Answer:** bug — only a string that is entirely a naive date-time (no trailing newline) is matched; `2026-01-01T10:00:00\n` is returned unchanged (reviewer accepted suggestion)
**Resolution:** a trailing newline prevents a match; the string is returned unchanged. Rules: `ensure_utc_z_in_json` R6.

### Q3. Non-ASCII digits count as date-time digits — 🐞 BUG-162
**Background:** The pattern uses `\d`, which in Python matches any Unicode decimal digit (Arabic-Indic `٢`, Bengali `২`, etc.), not only `0-9`. Pydantic never produces such digits for real date-times, so only user text can hit this.
**What happens today:** `٢٠٢٦-01-01T10:00:00` (Arabic-Indic year) is treated as a naive date-time and gets `Z` appended.
**Example:** A Bengali-locale user types `২০২৬-০১-০১T১০:০০:০০` into a text field; the API returns it with a trailing `Z`.
**Rules affected:** `ensure_utc_z_in_json` R7
**Suggested answer:** bug — only ASCII `0-9` digits match (as HR-8 already requires for digit shortcuts); other digit characters leave the string unchanged
**Answer:** bug — only ASCII `0-9` digits match (as HR-8 already requires for digit shortcuts); other digit characters leave the string unchanged (reviewer accepted suggestion)
**Resolution:** only ASCII `0-9` count as digits; any other digit character anywhere in the pattern leaves the string unchanged. Rules: `ensure_utc_z_in_json` R7.

### Q4. Date-times with a non-UTC offset are passed through unchanged, despite "always UTC with Z" — ✅ intended
**Background:** The module docstring promises "always UTC with Z suffix". But `ensure_utc_z_in_json` only touches strings with **no** offset; a timezone-aware datetime that Pydantic serialized with an offset such as `+06:00` is left as is (only `serialize_utc_datetime` converts to UTC, and nothing in the app calls it — see Q5).
**What happens today:** An aware datetime at 00:00 in UTC+6 is returned as `2026-01-01T00:00:00+06:00`, not `2025-12-31T18:00:00Z`.
**Example:** If a timezone-aware value reaches a response (e.g. a `timestamptz` column read with a non-UTC session time zone), the API returns `...+06:00` for that field and `...Z` for naive ones in the same response.
**Rules affected:** `ensure_utc_z_in_json` R5
**Suggested answer:** intended — an explicit offset is valid ISO-8601 and identifies the same instant; clients parse both forms
**Answer:** intended — an explicit offset is valid ISO-8601 and identifies the same instant; clients parse both forms (reviewer accepted suggestion)

### Q5. `serialize_utc_datetime` is not used by the application — 🗑️ remove
**Background:** No code under `app/` calls `serialize_utc_datetime`; its only caller is the legacy test `tests/test_datetime_serialize.py`. Responses get their `Z` from `ensure_utc_z_in_json` instead.
**What happens today:** The function exists and works (see its rules) but has no effect on any API response.
**Example:** Removing it changes no endpoint output; only the two `serialize_utc_datetime` tests in `tests/test_datetime_serialize.py` would need deleting.
**Rules affected:** `serialize_utc_datetime` R1–R6
**Suggested answer:** remove
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** dead code, to be removed together with its two legacy tests in `tests/test_datetime_serialize.py`. Section and Branch-map rows deleted; listed under Not specified.

## Overview
Makes API JSON express naive (UTC) date-times with a trailing `Z`. The backend stores naive UTC datetimes; Pydantic serializes them without an offset, so `ensure_utc_z_in_json` walks the serialized structure and appends `Z` to naive ISO date-time strings. It is called by `AppResponseModel`'s wrap serializer (`app/schemas/base.py`) and by `UtcJsonResponseMiddleware` (`app/core/utc_json_middleware.py`) on `/api/` JSON bodies. Invariant: applying the walk twice gives the same result as once (a string already ending in `Z` is never changed). Per BUG-160 the intended design moves the `Z` to the type level (datetime fields only); the string rules below stay until that fix replaces the walker.

**Callables:** 1 specified · 1 not specified
**Externals to mock:** none
**Integration-only behavior:** the `UtcJsonResponseMiddleware` half of BUG-160 (free text rewritten in `/api/` HTTP bodies) needs the HTTP stack; the `AppResponseModel` half is unit-testable (R9).

**Notes for the test designer:**
- The function is pure; call it directly. No database, no app, no mocks needed.
- R9 is tested through a throw-away `AppResponseModel` subclass (import from `app.schemas.base`) with one `str` field and one naive `datetime` field, serialized with `model_dump(mode="json")`. No database needed.
- Context only (not this module's rules): through `AppResponseModel`, `model_dump()` (python mode) leaves datetime fields as `datetime` objects and only plain strings are touched; `model_dump_json()` shows naive datetimes as `...Z` and aware ones in Pydantic's offset form.

## Not specified
- `serialize_utc_datetime(dt)` — dead code, to be removed (reviewer). No caller in `app/`; only legacy tests in `tests/test_datetime_serialize.py` (see Q5).

---

## `ensure_utc_z_in_json(value)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (used by: `AppResponseModel._serialize_with_utc_z`, `UtcJsonResponseMiddleware.dispatch`)

**Purpose:** Walk a JSON-like structure and append `Z` to every string that is a naive ISO date-time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `value` | `Any` | Usually a decoded JSON value (dict / list / str / number / bool / None). Anything is accepted. |

**Returns:** A new structure of the same shape (new `dict` / `list` objects; the input is not mutated), with matching strings replaced.

**Rules:**
- **R1.** A `dict` returns a new `dict` with the same keys in the same order; each value is processed recursively. Keys are never changed, even when a key itself looks like a naive date-time.
- **R2.** A `list` returns a new `list` of the same length and order; each element is processed recursively. Nesting depth is unlimited (dict in list in dict …). Empty dict/list returns an empty dict/list.
- **R3.** Any other container (tuple, set) is returned as is, and strings inside it are NOT changed. `("2026-01-01T10:00:00",)` → unchanged.
- **R4.** A string that is exactly `YYYY-MM-DDTHH:MM:SS` (four digits, `-`, two, `-`, two, uppercase `T`, two, `:`, two, `:`, two), optionally followed by `.` and one or more digits, and nothing else, and whose values form a real calendar date-time, is returned with `Z` appended: `"2026-01-01T10:00:00"` → `"2026-01-01T10:00:00Z"`; `"2026-01-01T10:00:00.120000"` → `"2026-01-01T10:00:00.120000Z"`; `"2024-02-29T23:59:59"` → `"2024-02-29T23:59:59Z"`. The fraction is kept exactly as given (any length, e.g. 9 digits).
- **R4a.** [BUG-160] A string of that shape whose values are not a real calendar date-time (month `13`, day `32`, `2026-02-30`, hour `24`, minute or second `60`, `9999-99-99T99:99:99`) is returned unchanged. *(Today: digit values are not range-checked and it gets `Z`.)* (best-practice default, delegated by reviewer)
- **R5.** Strings that do not fully match are returned unchanged, including: already ending in `Z`; with an offset (`+06:00`, `-05:00`); date only (`2026-01-01`); space instead of `T`; lowercase `t`; no seconds (`2026-01-01T10:00`); `.` with no digits after it; leading or trailing spaces; extra text before or after; empty string. ✅ (offset pass-through confirmed intended, Q4)
- **R6.** [BUG-161] A date-time followed by a trailing newline (`"2026-01-01T10:00:00\n"`) is returned unchanged; so is one followed by two newlines or any other trailing character. *(Today: exactly one trailing newline still matches and `Z` is appended after it: `"2026-01-01T10:00:00\nZ"`.)*
- **R7.** [BUG-162] Only ASCII `0-9` count as digits: a string that is otherwise a naive date-time but contains any non-ASCII decimal digit (`"٢٠٢٦-01-01T10:00:00"`, `"২০২৬-০১-০১T১০:০০:০০"`, or a non-ASCII digit only in the fraction) is returned unchanged. *(Today: any Unicode decimal digit matches and `Z` is appended.)*
- **R8.** Non-string scalars (`int`, `float`, `bool`, `None`) and `datetime` objects are returned unchanged (a `datetime` object is not a string and is not formatted).
- **R9.** [BUG-160] Through `AppResponseModel`, only `datetime` fields gain the UTC `Z`: a model with `note: str = "2026-01-01T10:00:00"` and `at: datetime = datetime(2026, 1, 1, 10, 0)` serializes (`model_dump(mode="json")`) to `note == "2026-01-01T10:00:00"` and `at == "2026-01-01T10:00:00Z"`. The same holds for free text in `/api/` JSON bodies through `UtcJsonResponseMiddleware` (integration-only). *(Today: matching depends only on the string's shape, so `note` becomes `"2026-01-01T10:00:00Z"`.)* *(Fix belongs in `app/schemas/base.py` / `app/core/utc_json_middleware.py` at the type level, not in this walker.)*
- **R10.** Idempotent: applying the function to its own output returns an equal result.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| — | none (an invalid calendar value under R4a is returned unchanged, never raises) | — |

**Side effects:** none (input structure not mutated)

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 30–31 | `isinstance(value, dict)` → recurse into values | `ensure_utc_z_in_json` R1, R2 |
| 32–33 | `isinstance(value, list)` → recurse into elements | `ensure_utc_z_in_json` R2 |
| 34–35 | str and pattern matches → append `Z` | `ensure_utc_z_in_json` R4, R4a, R6, R7, R9 |
| 34 | str but no match | `ensure_utc_z_in_json` R5, R10 |
| 36 | not dict/list/str → returned as is | `ensure_utc_z_in_json` R3, R8 |
| 9–11 | regex: `(\.\d+)?` optional fraction; `$` allows one trailing `\n`; `\d` is Unicode | `ensure_utc_z_in_json` R4, R6, R7 |
