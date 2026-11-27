# Test cases — `app/utils/item_name_normalize.py`

> **Spec:** `tests/unit/utils/item_name_normalize.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 4 — batch re-run (spec still APPROVED at e48a092, Gap log unchanged at G1/G2). Every rule R1–R8a, every example, the R6b/R5 best-practice defaults and all four bug tags re-checked against the cases; verify report (round 2, PASS) has no findings and no surviving mutants, so no `case-missing` item to address. No case added, removed or renumbered.
> **Revision (earlier):** 3 — re-run on the updated spec: Gap log still holds only G1/G2, already folded in by revision 2; every rule, example and bug tag re-checked against the cases; no case added, removed or renumbered.
> **Revision (previous):** 2 — spec Gap log G1 (R5 now labels "5 kgs" as 3 letters and gives the 4/5 boundary examples "5 pack" / "5 packs") and G2 (R6a now tags "5 kq́" `BUG-180; BUG-182`) closed both earlier gaps; INN-N-24/25/26 and INN-N-58 now cite the spec's own examples/tags; no case added, removed or renumbered.
> **Counts:** 73 cases · 51 expected-to-pass · 22 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** `normalize_item_name` 72 cases (22 bug) · module constants 1 case (0 bug).
- **Notable design choices:**
  - Pure function: no database, no session, no mocks (spec: "Externals to mock: none"). Every
    case calls the function directly and asserts the exact returned string.
  - Every non-ASCII input and expected value is written with explicit `\u` escapes (spec Notes).
  - The 4-vs-5-letter glue boundary uses the spec's "5 pack" (4 letters, glued) / "5 packs"
    (5 letters, not glued); "5 kgs" (3 letters) is tested too.
  - Regression cases that pass today are kept next to each bug where a bug-independent part
    exists (Bengali letters/digits kept, Bengali unit not glued to a number, idempotence on
    inputs no bug touches). Idempotence pass cases use only inputs whose result stays stable
    through every partial fix order (best-practice default, delegated by reviewer).
  - "5 kq́" (R6a) needs both BUG-180 and BUG-182 fixed (spec); its xfail reason is
    "BUG-180; BUG-182" and it stays strict-xfail until both ship.
- **Needs a decision:** None.

## Conventions for this module
- **IDs:** `INN` = `app/utils/item_name_normalize.py`; `N` = `normalize_item_name`; `K` = module
  constants.
- `f(x)` below means `normalize_item_name(x)`, imported from `app.utils.item_name_normalize`.
- **No DB, no externals mocked, no race simulations.** The Postgres fixture is not needed.
- "returns exactly S" = `result == S` and `type(result) is str`.
- Code points (all from the spec Notes):
  - `CHAL` = `"চাল"` (চাল, U+09BE Mc); `CHUL` = `"চুল"` (চুল, U+09C1 Mn);
    `CHIL` = `"চিল"` (চিল, U+09BF Mc); `CHOL` = `"চল"` (চল, letters only).
  - `RAB_ZWJ` = `"র‍্যাব"` (র‍্যাব with ZWJ); `RAB` = `"র্যাব"`.
  - `PHRASE` = `"মিনিকেট চাল ৫ কেজি"` (মিনিকেট চাল ৫ কেজি).
  - `KEJI_5` = `"৫ কেজি"` (৫ কেজি).
  - `CAFE_PRE` = `"café"`; `CAFE_DEC` = `"café"`.
  - `FW_BOLT` = `"Ｂｏｌｔ"`; `FW_10MM` = `"１０ ｍｍ"`.
  - `"x²"` (x²), `"ﬁle"` (ﬁle), NBSP `" "`, soft hyphen `"­"`, ZWNJ `"‌"`,
    ZWSP `"​"`, enclosing circle `"⃝"` (Me), `"q́"`.

## `normalize_item_name`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| INN-N-01 | R1 | happy | — | `f("")` | returns exactly `""` | pass |
| INN-N-02 | R1 | happy | — | `f(None)` | returns exactly `""`; no exception | pass |
| INN-N-03 | R1 | boundary | non-empty side of R1 | `f("a")` | returns exactly `"a"` | pass |
| INN-N-04 | R2 | happy | — | `f("SCREW")` | returns exactly `"screw"` | pass |
| INN-N-05 | R2 | boundary | lower, not casefold | `f("Straße")` | returns exactly `"straße"` (ß kept, NOT `"strasse"`) | pass |
| INN-N-06 | R2 | happy | precomposed accent | `f("Café")` | returns exactly `"café"` (length 4, é kept) | pass |
| INN-N-07 | R2a [BUG-181] | bug | decomposed accent | `f(CAFE_DEC)`; also `f(CAFE_PRE)` | `f(CAFE_DEC) == "café"`; `f(CAFE_DEC) == f(CAFE_PRE)` | xfail BUG-181 — fails today on: `f(CAFE_DEC)` is `"cafe"` |
| INN-N-08 | R2a [BUG-181] | bug | full-width | `f(FW_BOLT)` | returns exactly `"bolt"` | xfail BUG-181 — fails today on: result is `"ｂｏｌｔ"` |
| INN-N-09 | R2a [BUG-181] | bug | superscript | `f("x²")` | returns exactly `"x2"` | xfail BUG-181 — fails today on: result is `"x²"` |
| INN-N-10 | R2a [BUG-181] | bug | ligature | `f("ﬁle")` | returns exactly `"file"` | xfail BUG-181 — fails today on: result is `"ﬁle"` |
| INN-N-11 | R2a, R5 [BUG-181] | bug | full-width number + unit | `f(FW_10MM)` | returns exactly `"10mm"` | xfail BUG-181 — fails today on: result is `"１０ ｍｍ"` |
| INN-N-12 | R3 | happy | — | `f("  Screw   Driver  ")` | returns exactly `"screw driver"` | pass |
| INN-N-13 | R3 | happy | tab + newline | `f("x\tY\nz")` | returns exactly `"x y z"` | pass |
| INN-N-14 | R3 | happy | NBSP inside | `f("a b")` | returns exactly `"a b"` (U+0020); `" " not in result` | pass |
| INN-N-15 | R3 | boundary | single space (other side of "run") | `f("a b")` | returns exactly `"a b"` (space kept, not removed) | pass |
| INN-N-16 | R3, Returns | happy | mixed whitespace kinds | `f(" \tA　　B\r\n")` | returns exactly `"a b"`; result has no leading/trailing whitespace, no `"  "`, and every whitespace char in it is `" "` | pass |
| INN-N-17 | R4 | happy | — | `f("  ")` | returns exactly `""` | pass |
| INN-N-18 | R4 | happy | whitespace-only, mixed | `f(" \t\n  ")` | returns exactly `""` | pass |
| INN-N-19 | R4 | boundary | not whitespace-only | `f(" a ")` | returns exactly `"a"` | pass |
| INN-N-20 | R5 | happy | 1-letter unit at end | `f("Screw Driver 22 m")` | returns exactly `"screw driver 22m"` | pass |
| INN-N-21 | R5 | happy | unit followed by space | `f("10 mm Bolt")` | returns exactly `"10mm bolt"` | pass |
| INN-N-22 | R5 | happy | upper-case unit | `f("22 M")` | returns exactly `"22m"` | pass |
| INN-N-23 | R5 | happy | upper-case unit | `f("10 KG")` | returns exactly `"10kg"` | pass |
| INN-N-24 | R5 | happy | 3-letter word | `f("5 kgs")` | returns exactly `"5kgs"` | pass |
| INN-N-25 | R5 | boundary | word of exactly 4 letters | `f("5 pack")` | returns exactly `"5pack"` | pass |
| INN-N-26 | R5 | boundary | word of exactly 5 letters | `f("5 packs")` | returns exactly `"5 packs"` (not glued) | pass |
| INN-N-27 | R5 | boundary | 6-letter word | `f("22 metres")` | returns exactly `"22 metres"` | pass |
| INN-N-28 | R5 | happy | short word ended by punctuation | `f("5 kg-pack")` | returns exactly `"5kg pack"` | pass |
| INN-N-29 | R5 | boundary | short word followed by digit | `f("5 kg2")` | returns exactly `"5 kg2"` (not glued) | pass |
| INN-N-30 | R5 | boundary | same word ending at end of text | `f("5 kg")` | returns exactly `"5kg"` | pass |
| INN-N-31 | R5 | happy | every occurrence | `f("10 mm, 20 mm")` | returns exactly `"10mm 20mm"` | pass |
| INN-N-32 | R5 | happy | chained numbers | `f("2 x 3 m")` | returns exactly `"2x 3m"` | pass |
| INN-N-33 | R5 | happy | non-unit word (intended per Q4) | `f("iPhone 15 pro max")` | returns exactly `"iphone 15pro max"` | pass |
| INN-N-34 | R5 | happy | non-unit word (intended per Q4) | `f("Size 10 and up")` | returns exactly `"size 10and up"` | pass |
| INN-N-35 | R5 | happy | number ends an alphanumeric token | `f("Model X5 pro")` | returns exactly `"model x5pro"` | pass |
| INN-N-36 | R5 | boundary | no number before the short word | `f("Model X pro")` | returns exactly `"model x pro"` (not glued) | pass |
| INN-N-37 | R5, R6 | happy | decimal number | `f("1.5 mm")` | returns exactly `"1 5mm"` | pass |
| INN-N-38 | R5 | happy | Arabic-Indic digit | `f("٢ kg")` | returns exactly `"٢kg"` | pass |
| INN-N-39 | R5 | happy | Bengali digit | `f("৫ kg")` | returns exactly `"৫kg"` | pass |
| INN-N-40 | R5 | boundary | Bengali (non-ASCII) unit — bug-independent part | `f(KEJI_5)` | result starts with `"৫ ক"`; `"৫ক" not in result` (number not glued to a non-ASCII word) | pass |
| INN-N-41 | R5, R6a [BUG-180] | bug | Bengali unit, marks kept | `f(KEJI_5)` | returns exactly `"৫ কেজি"` | xfail BUG-180 — fails today on: result is `"৫ ক জ"` |
| INN-N-42 | R5a [BUG-182] | bug | hyphen separator | `f("Bolt 10-mm")` | returns exactly `"bolt 10mm"` | xfail BUG-182 — fails today on: result is `"bolt 10 mm"` |
| INN-N-43 | R5a [BUG-182] | bug | dot separator | `f("Bolt 10.mm")` | returns exactly `"bolt 10mm"` | xfail BUG-182 — fails today on: result is `"bolt 10 mm"` |
| INN-N-44 | R5a [BUG-182] | bug | spaced slash separator | `f("Bolt 10 / mm")` | returns exactly `"bolt 10mm"` | xfail BUG-182 — fails today on: result is not `"bolt 10mm"` (not glued) |
| INN-N-45 | R5a, R5 | happy | bug-independent variants | `f("Bolt 10mm")`; `f("Bolt 10 mm")` | both return exactly `"bolt 10mm"` | pass |
| INN-N-46 | R5a [BUG-182] | bug | parentheses | `f("Size 5 (pack)")` | returns exactly `"size 5pack"` | xfail BUG-182 — fails today on: result is `"size 5 pack"` |
| INN-N-47 | R5a, R6c [BUG-182, BUG-183] | bug | underscore separator | `f("Bolt 10_mm")` | returns exactly `"bolt 10mm"` | xfail reason "BUG-182; BUG-183" — fails today on: result keeps `"_"` (not `"bolt 10mm"`) |
| INN-N-48 | R6 | happy | hyphen | `f("Screw-Driver")` | returns exactly `"screw driver"` | pass |
| INN-N-49 | R6 | happy | dot | `f("Screw.Driver")` | returns exactly `"screw driver"` | pass |
| INN-N-50 | R6 | happy | parentheses | `f("Bolt (M8)")` | returns exactly `"bolt m8"` | pass |
| INN-N-51 | R6 | happy | symbols | `f("A&B+C@D#E")` | returns exactly `"a b c d e"` | pass |
| INN-N-52 | R6 | boundary | enclosing mark (Me) is NOT kept | `f("a⃝b")` | returns exactly `"a b"` | pass |
| INN-N-53 | R6, R6b | boundary | zero width space is NOT a deleted joiner | `f("a​b")` | returns exactly `"a b"` (space, not `"ab"`) | pass |
| INN-N-54 | R6, R6a | happy | Bengali letters only — bug-independent part | `f(CHOL)` | returns exactly `"চল"` | pass |
| INN-N-55 | R6a [BUG-180] | bug | vowel sign Mc | `f(CHAL)` | returns exactly `"চাল"` | xfail BUG-180 — fails today on: result is `"চ ল"` |
| INN-N-56 | R6a [BUG-180] | bug | three words differing only in a vowel sign | `f(CHAL)`, `f(CHUL)`, `f(CHIL)` | `f(CHUL) == "চুল"`; `f(CHIL) == "চিল"`; the three results are pairwise different | xfail BUG-180 — fails today on: all three are `"চ ল"` |
| INN-N-57 | R6a [BUG-180] | bug | multi-word Bengali phrase | `f(PHRASE)` | returns exactly `PHRASE` (unchanged) | xfail BUG-180 — fails today on: result is `"ম ন ক ট চ ল ৫ ক জ"` |
| INN-N-58 | R6a, R5 [BUG-180; BUG-182] | bug | short ASCII word followed by a combining mark | `f("5 kq́")` | returns exactly `"5 kq́"` (mark kept, not glued) | xfail reason "BUG-180; BUG-182" — fails today on: result is `"5kq"` (and would still fail with only one of the two fixes: `"5kq́"` / `"5kq"`) |
| INN-N-59 | R6a [BUG-180] | bug | Mn mark on an ASCII letter (no precomposed form) | `f("q́")` | returns exactly `"q́"` | xfail BUG-180 — fails today on: result is `"q"` |
| INN-N-60 | R6b [BUG-180] | bug | ZWJ inside a conjunct | `f(RAB_ZWJ)`; `f(RAB)` | `f(RAB_ZWJ) == "র্যাব"`; `f(RAB_ZWJ) == f(RAB)` | xfail BUG-180 — fails today on: `f(RAB_ZWJ)` is `"র য ব"` |
| INN-N-61 | R6b [BUG-180] | bug | soft hyphen | `f("Screw­driver")` | returns exactly `"screwdriver"` | xfail BUG-180 — fails today on: result is `"screw driver"` |
| INN-N-62 | R6b [BUG-180] | bug | ZWNJ | `f("a‌b")` | returns exactly `"ab"` | xfail BUG-180 — fails today on: result is `"a b"` |
| INN-N-63 | R6c [BUG-183] | bug | underscore between words | `f("Screw_Driver")` | returns exactly `"screw driver"` | xfail BUG-183 — fails today on: result is `"screw_driver"` |
| INN-N-64 | R6c, R7 [BUG-183] | bug | only underscores | `f("__")` | returns exactly `""` | xfail BUG-183 — fails today on: result is `"__"` |
| INN-N-65 | R7 | happy | punctuation only | `f("--")` | returns exactly `""` | pass |
| INN-N-66 | R7 | happy | punctuation only | `f("!!!")` | returns exactly `""` | pass |
| INN-N-67 | R7 | happy | spaces around punctuation collapse | `f("a - b")` | returns exactly `"a b"` | pass |
| INN-N-68 | R8 | happy | four variants | `f("Screw Driver 22m")`, `f("Screw Driver 22 m")`, `f("  screw   driver  22  M  ")`, `f("Screw-Driver 22m")` | each returns exactly `"screw driver 22m"` | pass |
| INN-N-69 | R8a | happy | bug-free inputs | for each x in `"Screw Driver 22 m"`, `"  screw   driver  22  M  "`, `"2 x 3 m"`, `"10 mm, 20 mm"`, `"1.5 mm"`, `"Size 10 and up"`, `"Model X5 pro"`, `"5 kg-pack"`, `"5 kg2"`, `"22 metres"`, `"Screw-Driver"`, `"a​b"`, `"a⃝b"`, `"--"`, `""`, `"bolt 10 mm"` | `f(f(x)) == f(x)` for every x (the subtest/param id names x) | pass |
| INN-N-70 | R8a | happy | Unicode inputs whose result is stable today and after every fix | for each x in `CAFE_PRE`, `CAFE_DEC`, `FW_BOLT`, `FW_10MM`, `"x²"`, `"ﬁle"`, `CHAL`, `RAB_ZWJ`, `PHRASE` | `f(f(x)) == f(x)` for every x | pass |
| INN-N-71 | R8a [BUG-182] | bug | inputs where gluing only becomes possible after punctuation | for each x in `"Bolt 10-mm"`, `"Bolt 10.mm"`, `"Size 5 (pack)"` | `f(f(x)) == f(x)` for every x; `f("Bolt 10-mm") == "bolt 10mm"` | xfail BUG-182 — fails today on: `f("Bolt 10-mm")` is `"bolt 10 mm"` but `f("bolt 10 mm")` is `"bolt 10mm"` |
| INN-N-72 | Inputs, Errors | boundary | no length validation | `f("A" * 10000)` | returns exactly `"a" * 10000`; no exception | pass |

## Module constants

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| INN-K-01 | Overview (constants) | happy | — | import `MIN_SIMILAR_NAME_LENGTH`, `SIMILARITY_THRESHOLD` from the module | `MIN_SIMILAR_NAME_LENGTH == 3`; `SIMILARITY_THRESHOLD == 0.35` | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview — key stored on create/update | `ItemManager.create_item`, `ItemManager.update_item` | `items.name_normalized` equals `normalize_item_name(name)` after create, and after update only when `name` is supplied |
| Overview — exact-duplicate detection | `ItemManager.find_similar_items` / `ItemService` (`GET /items/similar/`) | `match_type = "exact_normalized"` when normalized names match; `normalized_query` echoed |
| Overview — constants' effect | `ItemDAO.find_similar_by_name_in_workspace` (`tests/unit/dao/item.spec.md`) | names shorter than 3 get no suggestions; threshold 0.35 applied |
| Q1/Q2/Q3/Q5 resolutions — backfill | data migration shipping the BUG-180..183 fix | stored `items.name_normalized` recomputed with the fixed function |

## Spec gaps
None. (Earlier gaps 1 and 2 closed by spec Gap log G1, G2.)

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `normalize_item_name` | R1 | INN-N-01, 02, 03 |
| `normalize_item_name` | R2 | INN-N-04, 05, 06 |
| `normalize_item_name` | R2a [BUG-181] | INN-N-07, 08, 09, 10, 11; idempotence INN-N-70 |
| `normalize_item_name` | R3 | INN-N-12, 13, 14, 15, 16 |
| `normalize_item_name` | R4 | INN-N-17, 18, 19 |
| `normalize_item_name` | R5 | INN-N-20 … 40, 45, 58 |
| `normalize_item_name` | R5a [BUG-182] | INN-N-42, 43, 44, 46, 47; pass part INN-N-45 |
| `normalize_item_name` | R6 | INN-N-37, 48, 49, 50, 51, 52, 53, 54 |
| `normalize_item_name` | R6a [BUG-180] | INN-N-41, 55, 56, 57, 58, 59; pass parts INN-N-40, 54 |
| `normalize_item_name` | R6b [BUG-180] | INN-N-60, 61, 62; other side (ZWSP not deleted) INN-N-53 |
| `normalize_item_name` | R6c [BUG-183] | INN-N-47, 63, 64 |
| `normalize_item_name` | R7 | INN-N-64, 65, 66, 67 |
| `normalize_item_name` | R8 | INN-N-68 |
| `normalize_item_name` | R8a [BUG-182] | INN-N-71; pass parts INN-N-69, 70 |
| `normalize_item_name` | Returns contract | INN-N-16 (whitespace shape); every case asserts the exact `str` |
| `normalize_item_name` | Errors: none | INN-N-02, 72 (no exception on `None` / long input) |
| module | `MIN_SIMILAR_NAME_LENGTH`, `SIMILARITY_THRESHOLD` | INN-K-01 |
| — | BUG-180 | INN-N-41, 55–62 |
| — | BUG-181 | INN-N-07–11 |
| — | BUG-182 | INN-N-42–44, 46, 47, 58, 71 |
| — | BUG-183 | INN-N-47, 63, 64 |
