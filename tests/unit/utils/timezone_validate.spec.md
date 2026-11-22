# Spec — `app/utils/timezone_validate.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. Whether a timezone is "valid" depends on the server's operating system — 🐞 BUG-300
**Background:** The check does not compare the text against the official list of
IANA timezone names. It just tries to load a timezone file with that name. On
Windows the timezone files come from the `tzdata` Python package and are read
from a case-insensitive filesystem that also treats `\` as a folder separator
and ignores trailing spaces; on Linux (typical production) the lookup is exact.
**What happens today:** A few non-canonical spellings are accepted on Windows but
rejected on Linux: `utc` (lowercase), `Asia\Dhaka` (backslash), `Asia/Dhaka `
(trailing space — the schema callers trim first, so this one does not reach the
database). Other wrong-case names such as `asia/dhaka` are rejected on both.
**Example:** A developer on Windows signs up with timezone `utc`; it is accepted
and stored as `utc`. The same request against the Linux server gets 422
"Invalid IANA timezone identifier". A value stored from a Windows host (`Asia\Dhaka`)
would later fail to load on a Linux host.
**Rules affected:** `is_valid_iana_timezone` R6
**Suggested answer:** bug — valid means an exact, case-sensitive match against the canonical IANA name set (`zoneinfo.available_timezones()`), so the result is the same on every OS; `utc` and `Asia\Dhaka` are rejected everywhere.
**Answer:** bug — valid means an exact, case-sensitive match against the canonical IANA name set (`zoneinfo.available_timezones()`), so the result is the same on every OS; `utc` and `Asia\Dhaka` are rejected everywhere. (reviewer accepted suggestion)
**Resolution:** validity is exact, case-sensitive membership in the canonical IANA name set (`zoneinfo.available_timezones()`), identical on every OS. Rules: `is_valid_iana_timezone` R3, R4 (unchanged outcome), R6 (rewritten, tagged BUG-300). Follow-up decided (best-practice default, delegated by reviewer): tests for R6 are expected-to-fail only on hosts where today's lookup is case/separator/space-insensitive (Windows); see Notes for the test designer.

## Overview
Pure helper that decides whether a string is an IANA timezone identifier
(e.g. `Asia/Dhaka`). It is used by Pydantic field validators in
`app/schemas/auth.py` (`RegisterRequest.timezone`), `app/schemas/profile.py`
(`ProfileCreate.timezone`, `ProfileMeUpdate.timezone`) and
`app/schemas/workspace.py` (`settings["timezone"]`). All callers strip
whitespace and skip `None`/blank values before calling it, then turn `False`
into a 422 validation error. It protects the invariant that stored timezones can
be loaded later.

**Callables:** 1 specified · 0 not specified
**Externals to mock:** none (reads the installed `tzdata` package / system tz database; no network)
**Integration-only behavior:** none

**Notes for the test designer:** pure function — call it directly, no DB session
needed. Validity is decided by the timezone database installed on the host
(`tzdata>=2024.1` from requirements.txt; on Windows `zoneinfo.TZPATH` is empty so
only `tzdata` is used). Use long-established names (`Asia/Dhaka`, `UTC`,
`America/New_York`) for positive cases. R6 (BUG-300) inputs `utc`,
`Asia\Dhaka`, `Asia/Dhaka ` return `True` today on Windows (verified on this dev
host) but already return `False` on Linux. Mark those tests
`xfail(condition=sys.platform == "win32", strict=True, reason="BUG-300")` so they
are strict expected-failures on Windows and ordinary passing tests on Linux
(best-practice default, delegated by reviewer). Do not assert on
`posix/…` / `right/…` prefixed names: on Linux `available_timezones()` also lists
the system database's copies under those prefixes, on Windows it does not.
R2's 64-character limit is a defensive guard whose boundary is not observable
through the return value: the longest canonical IANA name is 32 characters
(`America/Argentina/ComodRivadavia`, measured on this host), so every string of
64 or 65+ characters returns `False` either way. Test both sides of the boundary
by return value and "no exception" only; do not spy on or mock the timezone
library to prove the lookup is skipped — the spec lists no externals, and the
BUG-300 fix may replace the lookup entirely (best-practice default, delegated by
reviewer).

## Not specified
_(none)_

---

## `is_valid_iana_timezone(value)`
**Shape:** validator
**Persistence:** pure
**Visibility:** public (used by: `RegisterRequest` in `app/schemas/auth.py`, `ProfileCreate`, `ProfileMeUpdate`, workspace settings validator)

**Purpose:** Say whether a string names a timezone that can be loaded from the IANA timezone database.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `value` | `str` | Candidate timezone name. Not trimmed, not case-folded. Must be at most 64 characters. Annotated `str`; `None` is tolerated (returns `False`); other non-string types are not handled. |

**Returns:** `True` if valid, `False` otherwise. Never raises for string or `None` input.

**Rules:**
- **R1.** Empty string `""` → `False`. `None` → `False`.
- **R2.** A string longer than 64 characters → `False`, even before any lookup. Exactly 64 characters is not rejected by length (it then goes through the lookup; a 64-character non-timezone like `"A"*64` → `False`).
- **R3.** A name in the canonical IANA name set (`zoneinfo.available_timezones()`) → `True`. Examples: `Asia/Dhaka`, `UTC`, `America/New_York`, `Etc/GMT+6`, `GMT`.
- **R4.** Legacy / alias names that are in the canonical IANA name set are accepted → `True`: e.g. `Asia/Calcutta`, `US/Eastern`, `EST`, `EST5EDT`, `Factory`.
- **R5.** Anything that does not load as a timezone → `False`, never an exception. Examples: unknown name `Nowhere/City`; a region folder `Asia` or `Asia/`; path-like input `../etc`, `/etc/UTC`, `Asia/../UTC`, `Asia/./Dhaka`; a name containing a NUL character; database metadata files `zone.tab`, `tzdata.zi`, `leapseconds`; `localtime`, `posixrules`; offsets such as `+06:00`; leading whitespace `" Asia/Dhaka"`; wrong-case region names such as `asia/dhaka`, `ASIA/DHAKA`.
- **R6.** [BUG-300] Validity is an exact, case-sensitive match against the canonical IANA name set, with the same result on every OS: `utc` (lowercase), `Asia\Dhaka` (backslash) and `Asia/Dhaka ` (trailing space) → `False` on every platform. *(Today: on Windows these load from the case-insensitive filesystem via `tzdata` and → `True`; on Linux they → `False`.)* *(Fix: check membership in `available_timezones()` — ideally cached — instead of, or before, loading the zone.)*
- **R7.** A non-string, non-`None` value (e.g. the integer `123`) raises `TypeError` from the length check. No caller passes one (all callers pass `str`).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `value` is a non-string without `len()` (e.g. `int`) | `TypeError` | `object of type 'int' has no len()` |

**Side effects:** none (the timezone library caches loaded zones in memory; not observable to callers).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| L8 | `not value` (empty string / `None`) → `False` | R1 |
| L8 | `len(value) > 64` → `False` (boundary: 64 passes, 65 fails) | R2 |
| L8 | `len()` on non-sized value raises | R7 |
| L10–11 | zone loads → falls through to `return True` (L14) | R3, R4, R6 (today: non-canonical spellings load on Windows — BUG-300) |
| L12–13 | any exception while loading (not found, invalid key/path, NUL) → `False` | R5, R6 |

## Gap log
- G1 (timezone_validate.cases.md gap 1) — Test mechanics — Added a Notes-for-the-test-designer paragraph: the R2 64/65 boundary is unobservable by return value (longest canonical name is 32 characters); test both sides by return value only, no spying on the timezone library (best-practice default, delegated by reviewer). No rule changed.
