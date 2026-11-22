# Test cases — `app/utils/work_order_workers.py`

> **Spec:** `tests/unit/utils/work_order_workers.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — spec Gap log G1–G3 closed: `load_active_member_lookups` R5 and the typed-name fallback of `resolve_names_to_members` R8 declared unreachable (no case, per spec); new `resolve_names_to_members` R8a [BUG-382] (whitespace-only member name → email) → new WOW-R-30, WOW-R-31, WOW-R-32; `display_names_for_user_ids` R7 now tagged [BUG-382] → WOW-D-08 regenerated to the intended behavior (now xfail), new WOW-D-12, WOW-D-13. No verify report exists yet.
> **Revision:** 3 — spec unchanged since revision 2 (gap log still G1–G3; verify report PASS, no case-designer findings). Re-inventory found one uncovered detail of `resolve_names_to_members` R7a/R9a [BUG-381]: a repeated unmatched name whose first occurrence precedes a matched member keeps its first position → new WOW-R-33.
> **Counts:** 77 cases · 61 expected-to-pass · 16 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `parse_worker_names` 11 · `join_worker_names` 7 · `resolve_names_to_members` 33 (11 bug) · `resolve_worker_text_to_members` 6 · `load_active_member_lookups` 7 · `display_names_for_user_ids` 13 (5 bug)
- **Notable design choices:**
  - BUG-380 (ambiguous names) is tested with the members in both orders (WOW-R-21, WOW-R-22), so an implementation that merely picks "the last" instead of "the first" still fails. In most BUG-380 cases the display text coincidentally holds today; the id list is the assertion that fails today.
  - "No cap" for `load_active_member_lookups` is checked with 101 active members, just past the common default page size of 100 (best-practice default, delegated by reviewer).
  - A "missing profile" id is always "highest existing profile id + 1000", so it can't collide with rows that other tests running at the same time insert.
  - Order of `load_active_member_lookups` is never asserted (R3). Results are compared as sets of `(user_id, name, email)`.
  - Read-only callables also assert that the session has no new, dirty or deleted objects after the call.
  - `load_active_member_lookups` R5 (membership without profile) and the typed-name fallback of `resolve_names_to_members` R8 have no case: the spec declares both unreachable; their lines are expected to stay uncovered.
  - BUG-382 (whitespace-only stored name): the credited ids already hold today, so they are checked in a passing case (WOW-R-31); the missing display entry is the xfail part. WOW-D-08 used to pin today's "no label" behavior; it now asserts the intended email fallback and is xfail.
  - Profiles with blank / whitespace-only emails (D-04, D-12, D-13) each use a different blank value (`""`, `"   "`, `"	 "`), because email is unique and a unique suffix can't be added to a blank value (best-practice default, delegated by reviewer).
- **Needs a decision:** None.

## Conventions for this module
- **Abbreviations:** `WOW` = work_order_workers. `P` = `parse_worker_names`, `J` = `join_worker_names`, `R` = `resolve_names_to_members`, `T` = `resolve_worker_text_to_members`, `L` = `load_active_member_lookups`, `D` = `display_names_for_user_ids`.
- **Pure callables (P, J, R, T):** no database. Members are built directly as `MemberLookup(user_id, name, email)`:
  - `M7 = MemberLookup(7, "Rahim", "rahim@x.com")`
  - `M9 = MemberLookup(9, "Karim", "karim@x.com")`
  - `M12 = MemberLookup(12, "rahim", "rahim12@x.com")` (a second "Rahim" with a different id)
  - `M31 = MemberLookup(31, "   ", "w@x.com")` (whitespace-only stored name)
  - Other ad-hoc members are defined in the case.
- **Result notation:** `ids=[…], unmatched=[…], display="…"` means the returned `WorkerNameResolution` has exactly these `matched_user_ids` (as a list, in this order), `unmatched_names` (list, in this order) and `display_text`.
- **DB callables (L, D):** real session, rolled back after each test.
  - W1, W2, W3 = three workspaces.
  - Profiles (each `name`, `email` given): P7 "Rahim" / `rahim@x.com`, P9 "Karim" / `karim@x.com`, others defined per case. Profile emails must be unique; if a parallel test could clash, the executor may add a unique suffix to the local part, and the expected strings follow that stored value. Blank / whitespace-only emails are used exactly as written (no suffix): D-04 `""`, D-12 `"   "` (three spaces), D-13 `"	 "` (tab + space) — each distinct so they never clash with each other (best-practice default, delegated by reviewer).
  - "Active member of W1" = a `WorkspaceMember` row (W1, profile, `status='active'`). The same pattern applies to `'suspended'` and `'invited'`.
  - `MISSING` = (highest existing profile id) + 1000, a profile id with no row.
  - "Session clean" = after the call, `session.new`, `session.dirty` and `session.deleted` are all empty.
- **Externals mocked:** none. **Time:** not used.
- **Race simulations:** none.

## `parse_worker_names`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOW-P-01 | R1 | boundary | — | `parse_worker_names(None)` | returns `[]` | pass |
| WOW-P-02 | R1 | boundary | — | `parse_worker_names("")` | returns `[]` | pass |
| WOW-P-03 | R1 | boundary | — | `parse_worker_names("  \t\n ")` | returns `[]` | pass |
| WOW-P-04 | R2 | happy | — | `parse_worker_names("Rahim,Karim;Babu")` | returns `["Rahim", "Karim", "Babu"]` | pass |
| WOW-P-05 | R2 | boundary | — | `parse_worker_names("Rahim,;,Karim;;Babu")` | returns `["Rahim", "Karim", "Babu"]` (a run of separators is one split) | pass |
| WOW-P-06 | R2 | boundary | — | call separately with `"Rahim\nKarim"`, `"Rahim and Karim"`, `"Rahim & Karim"`, `"Rahim/Karim"` | each returns a one-element list containing exactly its input: `["Rahim\nKarim"]`, `["Rahim and Karim"]`, `["Rahim & Karim"]`, `["Rahim/Karim"]` | pass |
| WOW-P-07 | R3 | happy | — | `parse_worker_names("  Abdul  Karim ,  rAHIM ")` | returns `["Abdul  Karim", "rAHIM"]` (outer spaces removed, inner double space and case kept) | pass |
| WOW-P-08 | R4 | boundary | — | `parse_worker_names(",Rahim,, ;Karim,")` | returns `["Rahim", "Karim"]` | pass |
| WOW-P-09 | R4 | boundary | — | `parse_worker_names(",;, ; ")` | returns `[]` (only separators and blanks) | pass |
| WOW-P-10 | R2, R4 | boundary | — | `parse_worker_names("Rahim")` | returns `["Rahim"]` (no separator → one name) | pass |
| WOW-P-11 | R5 | happy | — | `parse_worker_names("A, A")`; `parse_worker_names("B, A, B")` | returns `["A", "A"]`; returns `["B", "A", "B"]` | pass |

## `join_worker_names`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOW-J-01 | R1 | happy | — | `join_worker_names(["Rahim", " Karim "])` | returns `"Rahim, Karim"` | pass |
| WOW-J-02 | R1 | boundary | — | `join_worker_names(["Rahim"])`; `join_worker_names(["Abdul  Karim"])` | returns `"Rahim"` (no separator); returns `"Abdul  Karim"` (inner spaces kept) | pass |
| WOW-J-03 | R2 | boundary | — | `join_worker_names([None, "Rahim", "", "  ", "Karim", None])` | returns `"Rahim, Karim"` (no empty slot, no doubled `", "`) | pass |
| WOW-J-04 | R3 | boundary | — | `join_worker_names([])` | returns `""` | pass |
| WOW-J-05 | R3 | boundary | — | `join_worker_names([None, "", " \t"])` | returns `""` | pass |
| WOW-J-06 | R4 | happy | — | `join_worker_names(["A", "A"])` | returns `"A, A"` | pass |
| WOW-J-07 | R5 | boundary | — | `join_worker_names(["Rahim, Karim", "Babu"])` | returns `"Rahim, Karim, Babu"` (the comma inside is not escaped) | pass |

## `resolve_names_to_members`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOW-R-01 | R4, R6, R8 | happy | members `[M7, M9]` | resolve `["rahim"]` | `ids=[7], unmatched=[], display="Rahim"` | pass |
| WOW-R-02 | R4, R8 | happy | members `[M7, M9]` | resolve `["RAHIM@X.COM "]` | `ids=[7], unmatched=[], display="Rahim"` (email match shows the member's name) | pass |
| WOW-R-03 | R1, R7, R9 | boundary | members `[M7]` | resolve `["Rahim", "", "   ", "Unknown"]` | `ids=[7], unmatched=["Unknown"], display="Rahim, Unknown"` (blank names are skipped completely) | pass |
| WOW-R-04 | R2 | boundary | members `[M7]` | resolve `[]` | `ids=[], unmatched=[], display=""` | pass |
| WOW-R-05 | R1, R2 | boundary | members `[M7]` | resolve `["", "  "]` | `ids=[], unmatched=[], display=""` | pass |
| WOW-R-06 | R3 | boundary | members `[]` | resolve `["Rahim", "Karim"]` | `ids=[], unmatched=["Rahim", "Karim"], display="Rahim, Karim"` | pass |
| WOW-R-07 | R4, R8 | boundary | members `[MemberLookup(21, "straße", "s@x.com")]` | resolve `["STRASSE"]`; separately resolve `["STRASSEX"]` | first: `ids=[21], unmatched=[], display="straße"`; second: `ids=[], unmatched=["STRASSEX"], display="STRASSEX"` | pass |
| WOW-R-08 | R4, R8 | boundary | members `[MemberLookup(22, " Rahim ", "  rahim@x.com ")]` | resolve `["rahim"]`; separately resolve `["rahim@x.com"]` | both: `ids=[22], unmatched=[], display="Rahim"` (member side trimmed for matching and for display) | pass |
| WOW-R-09 | R4 | boundary | members `[MemberLookup(23, "Abdul Karim", "ak@x.com")]` | resolve `["Abdul  Karim"]` (two inner spaces); separately resolve `["abdul karim"]` (one inner space) | first: `ids=[], unmatched=["Abdul  Karim"], display="Abdul  Karim"`; second: `ids=[23], unmatched=[], display="Abdul Karim"` | pass |
| WOW-R-10 | R4 | boundary | members `[M7]` | resolve `["Rah", "Rahim Uddin", "rahim@x", "x.com"]` | `ids=[], unmatched=["Rah", "Rahim Uddin", "rahim@x", "x.com"], display="Rah, Rahim Uddin, rahim@x, x.com"` (no partial / prefix / suffix match) | pass |
| WOW-R-11 | R4 | boundary | members `[MemberLookup(24, None, None), MemberLookup(25, "", "  ")]` | resolve `["None", "x"]` | `ids=[], unmatched=["None", "x"], display="None, x"` (members with no name/email never match) | pass |
| WOW-R-12 | R4, R8 | happy | members `[MemberLookup(26, None, " N@x.com ")]` | resolve `["n@x.com"]` | `ids=[26], unmatched=[], display="N@x.com"` (name `None` → email shown, trimmed, stored case) | pass |
| WOW-R-13 | R8 | boundary | members `[MemberLookup(27, "", "e@x.com")]` | resolve `["E@X.COM"]` | `ids=[27], unmatched=[], display="e@x.com"` (name `""` → email shown) | pass |
| WOW-R-14 | R6, R9 | happy | members `[M7, M9]` | resolve `["Karim", "Rahim"]` | `ids=[9, 7], unmatched=[], display="Karim, Rahim"` (order of the typed names, not the member order) | pass |
| WOW-R-15 | R6 | side-effect | members `[M7]` | resolve `["Rahim", "rahim@x.com", "rahim"]` | `ids=[7]` (once, though reached 3 times via name and email); `unmatched=[]` | pass |
| WOW-R-16 | R7, R9 | happy | members `[M7]` | resolve `["  Zed  Khan ", "Rahim", "unknown"]` | `ids=[7], unmatched=["Zed  Khan", "unknown"], display="Zed  Khan, Rahim, unknown"` (trimmed, inner spaces and case kept, input order) | pass |
| WOW-R-17 | R9a, R6 | boundary | members `[M7, MemberLookup(12, "Rahim", "rahim12@x.com")]` | resolve `["rahim@x.com", "rahim12@x.com"]` | `ids=[7, 12], unmatched=[], display="Rahim, Rahim"` (two different members with the same stored name each keep an entry) | pass |
| WOW-R-18 | R5 | boundary | members `[M7, M7]` (same member listed twice) | resolve `["rahim"]` | `ids=[7], unmatched=[], display="Rahim"` (same `user_id` twice is not ambiguous) | pass |
| WOW-R-19 | R6, R7, R9 (Inputs: iterated once) | boundary | members `[M7]` | resolve a generator yielding `"Rahim"`, `"Unknown"` (not a list) | `ids=[7], unmatched=["Unknown"], display="Rahim, Unknown"` | pass |
| WOW-R-20 | Errors row 1 | error | members `[M7]` | resolve `["Rahim", None]` | raises `AttributeError` (pure function, no state to check) | pass |
| WOW-R-21 | R5 [BUG-380] | bug | members `[M7, M12]` (`"Rahim"` / `"rahim"`, ids 7 and 12) | resolve `["Rahim"]` | `ids=[], unmatched=["Rahim"], display="Rahim"` | xfail BUG-380 — fails today on: `ids == []` (today `[7]`) |
| WOW-R-22 | R5 [BUG-380] | bug | members `[M12, M7]` (reverse order of R-21) | resolve `["Rahim"]` | `ids=[], unmatched=["Rahim"], display="Rahim"` (result does not depend on member order) | xfail BUG-380 — fails today on: `ids == []` (today `[12]`) |
| WOW-R-23 | R5 [BUG-380] | bug | members `[M7, MemberLookup(30, "rahim@x.com", "boss@x.com")]` (member 30's name equals M7's email) | resolve `["rahim@x.com"]` | `ids=[], unmatched=["rahim@x.com"], display="rahim@x.com"` | xfail BUG-380 — fails today on: `ids == []` (today `[7]`) and `unmatched == ["rahim@x.com"]` (today `[]`) |
| WOW-R-24 | R5 [BUG-380], R6 | bug | members `[M7, M12, M9]` | resolve `["Rahim", "Karim"]` | `ids=[9], unmatched=["Rahim"], display="Rahim, Karim"` (the ambiguous name doesn't stop other names from resolving) | xfail BUG-380 — fails today on: `ids == [9]` (today `[7, 9]`) |
| WOW-R-25 | R7a [BUG-381] | bug | members `[M7]` | resolve `["Unknown", "unknown ", "UNKNOWN"]` | `ids=[], unmatched=["Unknown"], display="Unknown"` | xfail BUG-381 — fails today on: `unmatched == ["Unknown"]` (today `["Unknown", "unknown", "UNKNOWN"]`) |
| WOW-R-26 | R7a [BUG-381] | bug | members `[]` | resolve `["STRASSE", "straße"]` | `ids=[], unmatched=["STRASSE"], display="STRASSE"` (dedup uses `casefold`) | xfail BUG-381 — fails today on: `unmatched == ["STRASSE"]` (today 2 entries) |
| WOW-R-27 | R9a [BUG-381] | bug | members `[M7]` | resolve `["Rahim", "rahim@x.com", "rahim"]` | `ids=[7], unmatched=[], display="Rahim"` | xfail BUG-381 — fails today on: `display == "Rahim"` (today `"Rahim, Rahim, Rahim"`) |
| WOW-R-28 | R9a [BUG-381] | bug | members `[M7]` | resolve `["Rahim", "Unknown", "rahim"]` | `ids=[7], unmatched=["Unknown"], display="Rahim, Unknown"` | xfail BUG-381 — fails today on: `display == "Rahim, Unknown"` (today `"Rahim, Unknown, Rahim"`) |
| WOW-R-29 | R6, R7 | happy | members `[M7]` (same setup as R-28) | resolve `["Rahim", "Unknown", "rahim"]` | `ids=[7], unmatched=["Unknown"]` (holds today and after the BUG-381 fix; display not asserted here) | pass |
| WOW-R-30 | R8a [BUG-382] | bug | members `[M31, M7]` | resolve `["W@X.COM", "Rahim"]` | `ids=[31, 7], unmatched=[], display="w@x.com, Rahim"` (whitespace-only name → the member's email is shown) | xfail BUG-382 — fails today on: `display == "w@x.com, Rahim"` (today `"Rahim"`) |
| WOW-R-31 | R4, R6, R8a | happy | members `[M31, M7]` (same setup as R-30) | resolve `["W@X.COM", "Rahim"]` | `ids=[31, 7], unmatched=[]` (the member is credited via email today and after the BUG-382 fix; display not asserted here) | pass |
| WOW-R-32 | R8a [BUG-382] | bug | members `[MemberLookup(32, " 	 ", " W2@x.com ")]` | resolve `["w2@x.com"]` | `ids=[32], unmatched=[], display="W2@x.com"` (email fallback, trimmed, stored case) | xfail BUG-382 — fails today on: `display == "W2@x.com"` (today `""`) |
| WOW-R-33 | R7a, R9a [BUG-381] | bug | members `[M7]` | resolve `["Zed", "Rahim", " zed "]` | `ids=[7], unmatched=["Zed"], display="Zed, Rahim"` (repeated unmatched name kept once, first typed form, at its first position before the member) | xfail BUG-381 — fails today on: `unmatched == ["Zed"]` (today `["Zed", "zed"]`) and `display == "Zed, Rahim"` (today `"Zed, Rahim, zed"`) |

## `resolve_worker_text_to_members`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOW-T-01 | R1 | happy | members `[M7]` | `resolve_worker_text_to_members("rahim; Unknown,", members)` | `ids=[7], unmatched=["Unknown"], display="Rahim, Unknown"` | pass |
| WOW-T-02 | R2 | boundary | members `[M7]` | text `None` | `ids=[], unmatched=[], display=""` | pass |
| WOW-T-03 | R2 | boundary | members `[M7]` | text `""` | `ids=[], unmatched=[], display=""` | pass |
| WOW-T-04 | R2 | boundary | members `[M7]` | text `"  ;, ,; "` | `ids=[], unmatched=[], display=""` | pass |
| WOW-T-05 | R1 | boundary | members `[M7, M9]` | text `"Rahim\nKarim"` | `ids=[], unmatched=["Rahim\nKarim"], display="Rahim\nKarim"` (newline doesn't split, so the whole text is one unmatched name) | pass |
| WOW-T-06 | R1 | happy | members `[M7, M9]` | text `"Karim;;Rahim , Zed"` | `ids=[9, 7], unmatched=["Zed"], display="Karim, Rahim, Zed"` | pass |

## `load_active_member_lookups`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOW-L-01 | R1, R3, R4 | happy | P7 and P9 are active members of W1 | `load_active_member_lookups(session, W1.id)` | returns a list of exactly 2 `MemberLookup`; as a set of `(user_id, name, email)` it equals `{(P7.id, "Rahim", "rahim@x.com"), (P9.id, "Karim", "karim@x.com")}` (order not asserted); session clean; `WorkspaceMember` row count for W1 is unchanged | pass |
| WOW-L-02 | R1 | boundary | P7 active in W1, P8 "Sami" / `sami@x.com` suspended in W1, P10 "Tania" / `tania@x.com` invited in W1 | load W1 | returns exactly 1 entry: `(P7.id, "Rahim", "rahim@x.com")` | pass |
| WOW-L-03 | R1 | isolation | P7 active in W1; P7 and P11 "Nabil" / `nabil@x.com` active in W2 | load W1; separately load W2 | W1 → exactly 1 entry `(P7.id, "Rahim", "rahim@x.com")` (W2 memberships neither added nor duplicated); W2 → set `{(P7.id, "Rahim", "rahim@x.com"), (P11.id, "Nabil", "nabil@x.com")}` | pass |
| WOW-L-04 | R2, R3 | boundary | 101 profiles ("Worker 001" … "Worker 101", distinct emails), all active members of W1 | load W1 | returns 101 entries; the set of `user_id`s equals the 101 profile ids | pass |
| WOW-L-05 | R6 | boundary | W3 has P8 suspended and P10 invited, no active members | load W3 | returns `[]` | pass |
| WOW-L-06 | R6 | boundary | P7 active in W1 | `load_active_member_lookups(session, MAX_WORKSPACE_ID + 1000)` (a workspace id with no row) | returns `[]`; no error | pass |
| WOW-L-07 | R4 | boundary | P13 name `"  Babu "` email `"BABU@x.com"`, active in W1 | load W1 | exactly 1 entry, `name == "  Babu "` and `email == "BABU@x.com"` (raw stored values, not trimmed or lower-cased) | pass |

## `display_names_for_user_ids`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOW-D-01 | R1 | happy | P7 exists | `display_names_for_user_ids(session, [P7.id])` | returns `"Rahim"`; session clean | pass |
| WOW-D-02 | R2 | boundary | P14 name `""`, email `"e@x.com"` | ids `[P14.id]` | returns `"e@x.com"` | pass |
| WOW-D-03 | R3 | boundary | no profile with id `MISSING` | ids `[MISSING]` | returns `"User #<MISSING>"` (e.g. `"User #1042"`) | pass |
| WOW-D-04 | R3 | boundary | P15 name `""`, email `""` | ids `[P15.id]` | returns `"User #<P15.id>"` | pass |
| WOW-D-05 | R1, R3, R4 | happy | P7, P9 exist; `MISSING` has no profile | ids `[P9.id, MISSING, P7.id]` | returns `"Karim, User #<MISSING>, Rahim"` (input order) | pass |
| WOW-D-06 | R4 | boundary | — | ids `[]` | returns `""` | pass |
| WOW-D-07 | R6 | isolation | P20 "Nomad" / `nomad@x.com` is in no workspace; P21 "Sam" / `sam@x.com` is a suspended member of W2 | ids `[P20.id, P21.id]` | returns `"Nomad, Sam"` (no workspace or status check) | pass |
| WOW-D-08 | R7 [BUG-382] | bug | P22 name `"   "`, email `"ws@x.com"`; P7, P9 exist | ids `[P22.id]`; separately ids `[P7.id, P22.id, P9.id]` | first returns `"ws@x.com"`; second returns `"Rahim, ws@x.com, Karim"`; session clean | xfail BUG-382 — fails today on: first `== "ws@x.com"` (today `""`) |
| WOW-D-09 | R1, R4 | boundary | P23 name `" Babu "`, email `"babu@x.com"` | ids `[P23.id]` | returns `"Babu"` (join trims the label) | pass |
| WOW-D-10 | R5 [BUG-381] | bug | P7, P9 exist | ids `[P7.id, P9.id, P7.id]` | returns `"Rahim, Karim"` | xfail BUG-381 — fails today on: result `== "Rahim, Karim"` (today `"Rahim, Karim, Rahim"`) |
| WOW-D-11 | R5 [BUG-381] | bug | `MISSING` has no profile | ids `[MISSING, MISSING]` | returns `"User #<MISSING>"` | xfail BUG-381 — fails today on: result `== "User #<MISSING>"` (today the label repeats) |
| WOW-D-12 | R7 [BUG-382], R3 | bug | P24 name `""`, email `"   "` (three spaces) | ids `[P24.id]` | returns `"User #<P24.id>"` (blank name and whitespace-only email → id label) | xfail BUG-382 — fails today on: result `== "User #<P24.id>"` (today `""`) |
| WOW-D-13 | R7 [BUG-382], R3 | bug | P25 name `" 	 "`, email `"	 "` (tab + space); P7 exists | ids `[P25.id, P7.id]` | returns `"User #<P25.id>, Rahim"` | xfail BUG-382 — fails today on: result `== "User #<P25.id>, Rahim"` (today `"Rahim"`) |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview: `_sync_assignees_from_text` replaces the assignee rows with `matched_user_ids` | `WorkOrderManager._sync_assignees_from_text` (create/update) | After create/update with worker text, the assignee rows equal the resolved ids exactly, and earlier assignees not in the text are removed |
| Overview: the stored `assigned_to` text is kept as typed; only ids are derived | `WorkOrderManager` create/update | The work order's `assigned_to` column re-read from the DB equals the input text byte-for-byte (not the normalised `display_text`) |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `parse_worker_names` | R1 | WOW-P-01, WOW-P-02, WOW-P-03 |
| `parse_worker_names` | R2 | WOW-P-04, WOW-P-05, WOW-P-06, WOW-P-10 |
| `parse_worker_names` | R3 | WOW-P-07 |
| `parse_worker_names` | R4 | WOW-P-08, WOW-P-09, WOW-P-10 |
| `parse_worker_names` | R5 | WOW-P-11 |
| `join_worker_names` | R1 | WOW-J-01, WOW-J-02 |
| `join_worker_names` | R2 | WOW-J-03 |
| `join_worker_names` | R3 | WOW-J-04, WOW-J-05 |
| `join_worker_names` | R4 | WOW-J-06 |
| `join_worker_names` | R5 | WOW-J-07 |
| `resolve_names_to_members` | R1 | WOW-R-03, WOW-R-05 |
| `resolve_names_to_members` | R2 | WOW-R-04, WOW-R-05 |
| `resolve_names_to_members` | R3 | WOW-R-06 |
| `resolve_names_to_members` | R4 | WOW-R-01, WOW-R-02, WOW-R-07, WOW-R-08, WOW-R-09, WOW-R-10, WOW-R-11, WOW-R-12, WOW-R-13 |
| `resolve_names_to_members` | R5 [BUG-380] | WOW-R-18 (same-id pass), WOW-R-21, WOW-R-22, WOW-R-23, WOW-R-24 |
| `resolve_names_to_members` | R6 | WOW-R-01, WOW-R-14, WOW-R-15, WOW-R-17, WOW-R-19, WOW-R-29 |
| `resolve_names_to_members` | R7 | WOW-R-03, WOW-R-06, WOW-R-16, WOW-R-19, WOW-R-29 |
| `resolve_names_to_members` | R7a [BUG-381] | WOW-R-25, WOW-R-26, WOW-R-33 |
| `resolve_names_to_members` | R8 | WOW-R-01, WOW-R-02, WOW-R-07, WOW-R-08, WOW-R-12, WOW-R-13 (3rd fallback: unreachable per spec, no case) |
| `resolve_names_to_members` | R8a [BUG-382] | WOW-R-31 (pass part), WOW-R-30, WOW-R-32 |
| `resolve_names_to_members` | R9 | WOW-R-03, WOW-R-06, WOW-R-14, WOW-R-16, WOW-R-19 |
| `resolve_names_to_members` | R9a [BUG-381] | WOW-R-17 (pass part), WOW-R-27, WOW-R-28, WOW-R-33 |
| `resolve_names_to_members` | Errors: `None` element → `AttributeError` | WOW-R-20 |
| `resolve_worker_text_to_members` | R1 | WOW-T-01, WOW-T-05, WOW-T-06 |
| `resolve_worker_text_to_members` | R2 | WOW-T-02, WOW-T-03, WOW-T-04 |
| `load_active_member_lookups` | R1 | WOW-L-01, WOW-L-02, WOW-L-03 |
| `load_active_member_lookups` | R2 | WOW-L-04 |
| `load_active_member_lookups` | R3 | WOW-L-01, WOW-L-04 (set comparison, order never asserted) |
| `load_active_member_lookups` | R4 | WOW-L-01, WOW-L-07 |
| `load_active_member_lookups` | R5 | — (unreachable per spec: FK with cascade; no case, line expected uncovered) |
| `load_active_member_lookups` | R6 | WOW-L-05, WOW-L-06 |
| `display_names_for_user_ids` | R1 | WOW-D-01, WOW-D-05, WOW-D-09 |
| `display_names_for_user_ids` | R2 | WOW-D-02 |
| `display_names_for_user_ids` | R3 | WOW-D-03, WOW-D-04, WOW-D-05, WOW-D-12, WOW-D-13 |
| `display_names_for_user_ids` | R4 | WOW-D-05, WOW-D-06, WOW-D-09 |
| `display_names_for_user_ids` | R5 [BUG-381] | WOW-D-10, WOW-D-11 |
| `display_names_for_user_ids` | R6 | WOW-D-07 |
| `display_names_for_user_ids` | R7 [BUG-382] | WOW-D-08, WOW-D-12, WOW-D-13 |
| Overview (callers) | assignee sync / stored text | Deferred (2) |
