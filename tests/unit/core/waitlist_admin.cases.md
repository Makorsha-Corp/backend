# Test cases — `app/core/waitlist_admin.py`

> **Spec:** `tests/unit/core/waitlist_admin.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — re-run; spec unchanged (same source commit, same rules R1–R6, BUG-540/541). Verifier report (PASS) has no `case-missing` findings; its 3 surviving mutants are bug-path only (resolve when BUG-540/541 are fixed), so no cases added, changed or retired.
> **Counts:** 19 cases · 13 expected-to-pass · 6 expected-to-fail (bugs) · 3 deferred

## Reviewer summary
- **Per callable:** `get_waitlist_admin` 19 cases (6 bug: 3 × BUG-541, 3 × BUG-540).
- **Notable design choices:**
  - BUG-541 (refusal message) is split: a passing case per setup asserts only "403 is raised" (true today and after the fix), and an xfail twin asserts the exact detail text. This keeps regression protection on the refusal itself.
  - BUG-540 (allowlist grants access) has no passing twin: today's behavior on those setups is the bug itself (user admitted). The "near miss" allowlist setups (`founder@makorsha.com.evil`, `makorsha.com`) are passing cases, since they must be refused both today and after the fix.
  - The "no `is_platform_admin` attribute" branch of R1 uses a plain object (`types.SimpleNamespace(email=...)`), because a `Profile` always has the attribute (best-practice default, delegated by reviewer).
  - `is_platform_admin = None`, `email = None` and `email = ""`/whitespace use unsaved in-memory `Profile` instances, as the spec's notes allow. All other cases use a saved profile row and re-read it.
  - The settings validator (`config.py`, splitting the env string) is deferred to the config spec and is not tested here (best-practice default, delegated by reviewer).
- **Needs a decision:** None.

## Conventions for this module
- **IDs:** `WLA` = `app/core/waitlist_admin.py`; `G` = `get_waitlist_admin`.
- **Call:** `get_waitlist_admin(current_user=<user>)`, called directly with the argument passed explicitly (no app, no HTTP client). If the callable is `async`, await it; otherwise call it synchronously (the executor follows whichever the import reveals).
- **Allowlist:** every test sets `app.core.config.settings.WAITLIST_ADMIN_EMAILS` explicitly with `monkeypatch.setattr(settings, "WAITLIST_ADMIN_EMAILS", [...], raising=False)` to the list given in Given. No test relies on the environment's value.
- **Saved profile P:** a `Profile` row inserted in the test database (with whatever workspace/other required fields the harness needs), with the `email` and `is_platform_admin` given in the case. "Row unchanged" means: after the call, re-read P's row from the database (fresh query, not the in-memory object) and assert `email` and `is_platform_admin` equal the Given values; also assert the session has no pending changes (`session.new` and `session.dirty` are empty).
- **Unsaved profile:** `Profile(email=..., is_platform_admin=...)` built in memory, never added to the session. "Object unchanged" means its `email` and `is_platform_admin` attributes still equal the Given values after the call.
- **Bare object:** `types.SimpleNamespace(email="member@makorsha.com")` — has no `is_platform_admin` attribute. "Object unchanged" means `email` is unchanged and `hasattr(obj, "is_platform_admin")` is still `False`.
- **Refusal:** `fastapi.HTTPException`; assert `.status_code` and, where stated, `.detail`. The intended detail everywhere is exactly `"Not authorized to view waitlist signups"` (called **D-NA** below).
- **Externals mocked:** none. **Race simulations:** none. **Time:** not relevant.

## `get_waitlist_admin`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WLA-G-01 | R1, R6 | happy | Saved P: email `admin@makorsha.com`, `is_platform_admin=True`; allowlist `[]` | call with P | returns P itself (`result is P`); no exception; P row unchanged | pass |
| WLA-G-02 | R1, R6 | boundary | Saved P: email `admin@makorsha.com`, `is_platform_admin=True`; allowlist `["founder@makorsha.com"]` (P's email not on it) | call with P | returns P itself (`result is P`); P row unchanged | pass |
| WLA-G-03 | R1, R4, R6 | boundary | Saved P: email `admin@makorsha.com`, `is_platform_admin=False`; allowlist `["founder@makorsha.com"]` (other side of G-02: only the flag differs) | call with P | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA; P row unchanged | pass |
| WLA-G-04 | R2, R6 | error | Saved P: email `member@makorsha.com`, `is_platform_admin=False`; allowlist `[]` | call with P | raises `HTTPException` with `status_code == 403` (detail not asserted here); P row unchanged | pass |
| WLA-G-05 | R2 [BUG-541] | bug | Same as G-04 | call with P | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA | xfail BUG-541 — fails today on: `detail == D-NA` (today `"Waitlist admin access requires platform admin or WAITLIST_ADMIN_EMAILS"`) |
| WLA-G-06 | R2, R6 | boundary | Unsaved profile: email `member@makorsha.com`, `is_platform_admin=None`; allowlist `["", "   "]` (empty after normalisation) | call with it | raises `HTTPException` with `status_code == 403` (detail not asserted); object unchanged (`is_platform_admin` still `None`, email unchanged) | pass |
| WLA-G-07 | R2 [BUG-541] | bug | Same as G-06 | call with it | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA | xfail BUG-541 — fails today on: `detail == D-NA` |
| WLA-G-08 | R1, R2, R6 | boundary | Bare object (no `is_platform_admin` attribute), email `member@makorsha.com`; allowlist `[]` | call with it | raises `HTTPException` with `status_code == 403` (no `AttributeError`; detail not asserted); object unchanged (still no `is_platform_admin` attribute) | pass |
| WLA-G-09 | R1, R2 [BUG-541] | bug | Same as G-08 | call with it | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA | xfail BUG-541 — fails today on: `detail == D-NA` |
| WLA-G-10 | R1, R4, R6 | boundary | Bare object (no `is_platform_admin` attribute), email `member@makorsha.com`; allowlist `["founder@makorsha.com"]` | call with it | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA; object unchanged | pass |
| WLA-G-11 | R3 [BUG-540] | bug | Saved P: email `founder@makorsha.com`, `is_platform_admin=False`; allowlist `["founder@makorsha.com"]` (exact match) | call with P | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA; P row unchanged | xfail BUG-540 — fails today on: no exception raised (P is returned) |
| WLA-G-12 | R3 [BUG-540] | bug | Saved P: email `Founder@Makorsha.com`, `is_platform_admin=False`; allowlist `[" founder@makorsha.com "]` (match only after trim + lower-case) | call with P | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA; P row unchanged (email still `Founder@Makorsha.com`) | xfail BUG-540 — fails today on: no exception raised (P is returned) |
| WLA-G-13 | R3 [BUG-540] | bug | Saved P: email `founder@makorsha.com`, `is_platform_admin=False`; allowlist `["ops@makorsha.com", "FOUNDER@makorsha.com"]` (match is the second of several entries) | call with P | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA; P row unchanged | xfail BUG-540 — fails today on: no exception raised (P is returned) |
| WLA-G-14 | R3, R4, R6 | boundary | Saved P: email `founder@makorsha.com.evil`, `is_platform_admin=False`; allowlist `["founder@makorsha.com"]` (allowlist entry is a prefix of the email) | call with P | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA; P row unchanged | pass |
| WLA-G-15 | R3, R4, R6 | boundary | Saved P: email `founder@makorsha.com`, `is_platform_admin=False`; allowlist `["makorsha.com"]` (allowlist entry is a suffix/domain of the email) | call with P | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA; P row unchanged | pass |
| WLA-G-16 | R4, R6 | error | Saved P: email `member@makorsha.com`, `is_platform_admin=False`; allowlist `["founder@makorsha.com", "ops@makorsha.com"]` | call with P | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA; P row unchanged | pass |
| WLA-G-17 | R5, R6 | boundary | Unsaved profile: email `None`, `is_platform_admin=False`; allowlist `["founder@makorsha.com"]` | call with it | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA (no `AttributeError`/`TypeError`); object unchanged (email still `None`) | pass |
| WLA-G-18 | R5, R2, R6 | boundary | Unsaved profile: email `""`, `is_platform_admin=False`; allowlist `["founder@makorsha.com", "", "   "]` (non-empty after normalisation; blank entries must not match the blank email) | call with it | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA; object unchanged (email still `""`) | pass |
| WLA-G-19 | R5, R6 | boundary | Unsaved profile: email `"   "`, `is_platform_admin=False`; allowlist `["founder@makorsha.com", "   "]` | call with it | raises `HTTPException`, `status_code == 403`, `detail ==` D-NA; object unchanged (email still `"   "`) | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview — authentication (integration-only) | `get_current_user` / integration tests of `GET /waitlist` | Missing or invalid JWT → 401 before `get_waitlist_admin` runs. |
| Overview — wiring (integration-only) | Integration tests of `GET /waitlist` and `PATCH /waitlist/{signup_id}/status` | Both endpoints use this dependency: non-admin → 403 D-NA, platform admin → 200. |
| Inputs (setting) — env string split/trim/drop blanks | `app/core/config.py` settings spec | `WAITLIST_ADMIN_EMAILS` from a comma-separated string is split, trimmed, blanks dropped; a list is passed through (or the setting is removed when BUG-540 is fixed). (best-practice default, delegated by reviewer) |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_waitlist_admin` | R1 (admin → returned, any email/allowlist) | WLA-G-01, WLA-G-02 |
| `get_waitlist_admin` | R1 (flag False — other side) | WLA-G-03 |
| `get_waitlist_admin` | R1 (attribute absent → treated as False) | WLA-G-08, WLA-G-09, WLA-G-10 |
| `get_waitlist_admin` | R2 (empty allowlist → 403) | WLA-G-04, WLA-G-06, WLA-G-08 |
| `get_waitlist_admin` | R2 [BUG-541] (detail D-NA) | WLA-G-05, WLA-G-07, WLA-G-09 |
| `get_waitlist_admin` | R2 boundary (blank-only list vs list with a real entry) | WLA-G-06 / WLA-G-18 |
| `get_waitlist_admin` | R3 [BUG-540] (exact, case/whitespace, multi-entry match refused) | WLA-G-11, WLA-G-12, WLA-G-13 |
| `get_waitlist_admin` | R3 (near misses never match) | WLA-G-14, WLA-G-15 |
| `get_waitlist_admin` | R4 | WLA-G-03, WLA-G-10, WLA-G-14, WLA-G-15, WLA-G-16 |
| `get_waitlist_admin` | R5 (`None`, `""`, whitespace email) | WLA-G-17, WLA-G-18, WLA-G-19 |
| `get_waitlist_admin` | R6 (nothing written, user unmodified) | all cases except the xfail-only ones; asserted in WLA-G-01..04, 06, 08, 10, 14..19 |
| `get_waitlist_admin` | Errors row: not platform admin → 403 D-NA | WLA-G-03, WLA-G-10, WLA-G-14..G-19 (pass); WLA-G-05, 07, 09, 11..13 (xfail) |
| `get_waitlist_admin` | BUG-540 | WLA-G-11, WLA-G-12, WLA-G-13 |
| `get_waitlist_admin` | BUG-541 | WLA-G-05, WLA-G-07, WLA-G-09 |
