# Spec — `app/utils/item_name_normalize.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

No house-rule violations (house rules cover stored names and uniqueness; this is a
comparison key only). No precedent matches in `docs/testing/bugs.md`.

### New questions

### Q1. Bengali (and other Indic) vowel signs are deleted, so different words become identical — 🐞 BUG-180
**Background:** Every item stores a "normalized name" computed by this function. The
"similar items" check (`GET /items/similar/`, shown when a user creates or renames a
catalog item) flags an existing item as an **exact duplicate** when its normalized
name equals the normalized proposed name. Bengali vowel signs (া ি ী ু ে …) and other
combining marks are separate Unicode characters that are neither letters nor digits
to Python's "word character" test, so the function treats them as punctuation.
**What happens today:** every vowel sign / combining mark is replaced by a space, so
Bengali words keep only their consonants.
**Example:** "চাল" (rice), "চুল" (hair) and "চিল" (kite) all normalize to `"চ ল"`. A user
creating the item "চুল" is told the existing item "চাল" is an exact duplicate; "মিনিকেট
চাল ৫ কেজি" normalizes to `"ম ন ক ট চ ল ৫ ক জ"`.
**Rules affected:** `normalize_item_name` R6a, R6b
**Answer:** bug — keep combining marks (Mn/Mc) as part of the word; replace only characters that are not letters, marks, digits or whitespace (reviewer accepted suggestion)
**Suggested answer:** bug — combining marks (Unicode categories Mn/Mc, e.g. Bengali vowel signs) are kept as part of the word; only characters that are not letters, marks, digits or whitespace are replaced by a space ("চাল" → "চাল", "চাল" ≠ "চুল")
**Resolution:** combining marks (Mn, Mc) are kept inside the word (R6a). Follow-up decided by best practice: the invisible in-word joiners ZERO WIDTH JOINER U+200D, ZERO WIDTH NON-JOINER U+200C and SOFT HYPHEN U+00AD (used inside Bengali conjuncts such as "র‍্যাব") are deleted without leaving a space, so they neither split the word nor distinguish spellings that render alike (R6b) (best-practice default, delegated by reviewer). Enclosing marks (Me) and all other format characters are not "marks" in the reviewer's sense and still become a space (R6). Stored `items.name_normalized` values must be backfilled when the fix ships (best-practice default, delegated by reviewer). Rules: `normalize_item_name` R6a, R6b.

### Q2. The same visible name typed with different Unicode encodings does not match — 🐞 BUG-181
**Background:** Unicode can encode the same visible text in several ways: "é" as one
precomposed character or as "e" + combining accent; full-width "Ｂｏｌｔ" (common from
some East-Asian/Bengali keyboards and PDF copy-paste) vs "Bolt". The function applies
no Unicode normalization (NFC/NFKC) before comparing.
**What happens today:** precomposed "café" normalizes to `"café"` but decomposed
"cafe" + U+0301 normalizes to `"cafe"` (the accent is stripped as punctuation);
full-width "Ｂｏｌｔ" normalizes to `"ｂｏｌｔ"`, not `"bolt"`.
**Example:** Item "Café Latte Cup" exists (typed on a phone, precomposed). A user pastes
"Café Latte Cup" copied from a PDF (decomposed). The similar-items check does not
report an exact duplicate, and the two stored normalized names differ.
**Rules affected:** `normalize_item_name` R2a
**Answer:** bug — apply Unicode NFKC normalization first (reviewer accepted suggestion)
**Suggested answer:** bug — apply Unicode NFKC normalization first, so canonically/compatibly equivalent spellings (precomposed vs decomposed accents, full-width vs ASCII) normalize identically
**Resolution:** NFKC is applied to the input before any other step (R2a). Stored `items.name_normalized` values must be backfilled when the fix ships (best-practice default, delegated by reviewer). Rules: `normalize_item_name` R2a.

### Q3. "10-mm" and "10 mm" normalize differently (unit gluing happens before punctuation is removed) — 🐞 BUG-182
**Background:** The function glues a number to a following short word ("22 m" →
"22m") so spacing variants of sizes match. It does this *before* it turns punctuation
into spaces, so a number and unit separated by punctuation are not glued.
**What happens today:** "Bolt 10 mm" and "Bolt 10mm" → `"bolt 10mm"`, but "Bolt 10-mm"
→ `"bolt 10 mm"`. As a side effect the function is not idempotent: normalizing
`"bolt 10 mm"` again gives `"bolt 10mm"`.
**Example:** Item "Bolt 10mm" exists. A user creates "Bolt 10-mm"; the similar-items
check shows it only as a fuzzy match, not an exact duplicate, although the docstring's
purpose is to make such variants equal.
**Rules affected:** `normalize_item_name` R5a, R8a
**Answer:** bug — glue number+unit after punctuation is replaced by spaces so all variants give "10mm" and the function is idempotent (reviewer accepted suggestion)
**Suggested answer:** bug — glue number+unit after punctuation has been replaced by spaces, so "10-mm", "10 mm", "10mm" and "10.mm" all normalize to "10mm" and the function is idempotent
**Resolution:** gluing runs after the punctuation step and the whitespace collapse, so punctuation between a number and a short word is treated like a space (R5a), and the function is idempotent for every input (R8a). Follow-up decided by best practice: once punctuation is gone, the short word must end at a space or the end of the text; a following letter, digit or combining mark means it is part of a longer word and is not glued (R5) (best-practice default, delegated by reviewer). Stored `items.name_normalized` values must be backfilled when the fix ships (best-practice default, delegated by reviewer). Rules: `normalize_item_name` R5a, R8a.

### Q4. Any 1–4 letter word after a number is glued, not only units — ✅ intended
**Background:** The code comment and docstring say the step glues a number to a
"short trailing unit token". The code glues any 1–4 letter ASCII word, whatever it
means.
**What happens today:** "iPhone 15 pro max" → `"iphone 15pro max"`, "Size 10 and up" →
`"size 10and up"`, "Model X5 pro" → `"model x5pro"`. The same transform is applied to
both the stored and the proposed name, so matching stays consistent.
**Example:** "iPhone 15 pro" and "iPhone 15pro" are reported as exact duplicates of
each other; "Size 10 and up" is stored normalized as `"size 10and up"`.
**Rules affected:** `normalize_item_name` R5
**Answer:** intended (reviewer accepted suggestion)
**Suggested answer:** intended

### Q5. Underscore is kept, while every other punctuation mark becomes a space — 🐞 BUG-183
**Background:** The punctuation step keeps "word characters", which in Python include
the underscore `_`.
**What happens today:** "Screw-Driver", "Screw.Driver" and "Screw Driver" all →
`"screw driver"`, but "Screw_Driver" → `"screw_driver"`.
**Example:** Item "Screw Driver" exists; a user creates "Screw_Driver" (e.g. imported
from a spreadsheet). The similar-items check does not report an exact duplicate.
**Rules affected:** `normalize_item_name` R6c
**Answer:** bug — treat underscore like other punctuation (replace it with a space) (reviewer accepted suggestion)
**Suggested answer:** bug — underscore is treated like other punctuation and replaced by a space ("Screw_Driver" → "screw driver")
**Resolution:** underscore is replaced by a space like any other punctuation (R6c). Stored `items.name_normalized` values must be backfilled when the fix ships (best-practice default, delegated by reviewer). Rules: `normalize_item_name` R6c.

## Overview
Pure helper that turns a catalog item name into a comparison key (`Item.name_normalized`)
used for duplicate / similar-name detection. Called by `ItemManager` on item create and
on update when `name` is supplied (stored in `items.name_normalized`, NOT NULL, trigram
GIN index), by `ItemManager.find_similar_items` and `ItemService` (to decide
`match_type = "exact_normalized"` and echo `normalized_query`), and by
`ItemDAO.find_similar_by_name_in_workspace`. The invariant it protects: names that a
user would consider the same item (case, spacing, punctuation, Unicode encoding,
"22 m" vs "22m") map to the same key, while genuinely different words (e.g. Bengali
words differing only in a vowel sign) do not. The key is advisory only — no
uniqueness is enforced on it.

Intended processing order (after BUG-180..BUG-183 are fixed): (1) empty/`None` → `""`;
(2) Unicode NFKC; (3) lowercase; (4) delete in-word joiners, replace every other
character that is not a letter, number, combining mark (Mn/Mc) or whitespace with a
space; (5) collapse whitespace and trim; (6) glue number + short ASCII word. Rules
below state the observable outcome of this order.

Module constants (not callables, consumed by `ItemDAO.find_similar_by_name_in_workspace`):
`MIN_SIMILAR_NAME_LENGTH = 3` (normalized names shorter than this get no suggestions)
and `SIMILARITY_THRESHOLD = 0.35` (minimum trigram score). Their effect is specified in
`tests/unit/dao/item.spec.md`; a test here may only assert their values.

**Callables:** 1 specified · 0 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:** pure function, no database or session needed. A
legacy test `tests/test_item_name_normalize.py` exists outside `tests/unit/`; do not
rely on it. Build non-ASCII inputs with explicit `\u` escapes so the intended code
points are unambiguous. Code points used in this spec:
- "চাল" = `"চাল"` (U+09BE is category Mc); "চুল" = `"চুল"`
  (U+09C1 is Mn); "চিল" = `"চিল"` (U+09BF is Mc); "চ ল" = `"চ ল"`.
- "র‍্যাব" (with ZERO WIDTH JOINER) = `"র‍্যাব"`; without the
  joiner = `"র্যাব"`.
- precomposed "café" = `"café"`; decomposed = `"café"`.
- full-width "Ｂｏｌｔ" = `"Ｂｏｌｔ"`; full-width "１０ ｍｍ" = `"１０ ｍｍ"`.
- "x²" = `"x²"`; ligature "ﬁle" = `"ﬁle"`; non-breaking space = `" "`;
  soft hyphen = `"­"`; zero width non-joiner = `"‌"`; zero width space = `"​"`
  (category Cf, NOT one of the deleted joiners); combining enclosing circle = `"⃝"` (Me).
- A combining mark with no precomposed form after an ASCII letter (for R5/R6a):
  `"q́"`.

Bug-tagged rules state intended behavior and are expected to fail until the fix
(`xfail(strict=True, reason="BUG-NNN")`). Several rules interact: where an example's
outcome depends on more than one bug, the rule lists every bug it needs.

## Not specified
- (none)

---

## `normalize_item_name(name)`
**Shape:** helper
**Persistence:** pure
**Visibility:** public (used by: `ItemManager.create_item`, `ItemManager.update_item`, `ItemManager.find_similar_items`, `ItemService` similar-items endpoint, `ItemDAO.find_similar_by_name_in_workspace`)

**Purpose:** produce the comparison key for an item name so spelling variants of the same name compare equal.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| name | `str` (annotated; `None` also accepted) | Any text. No length or content validation. |

**Returns:** a `str`, possibly empty; never contains leading/trailing whitespace or two consecutive spaces, and contains no whitespace other than the plain space `" "`. Intended (BUG-181, BUG-182): the result is NFKC-normalized and normalizing it again returns it unchanged.

**Rules:**
- **R1.** An empty string or `None` returns `""`.
- **R2.** Letters are lowercased with Python's `str.lower()` (Unicode-aware, not case-folding): `"SCREW"` → `"screw"`, `"ß"` stays `"ß"`, `"Café"` (precomposed) → `"café"` (precomposed accented letters are kept).
- **R2a.** [BUG-181] Unicode NFKC normalization is applied to the input before anything else, so canonically and compatibility-equivalent spellings give the same result: decomposed `"café"` → `"café"` (precomposed `"café"`, identical to the result for precomposed input); full-width `"Ｂｏｌｔ"` → `"bolt"`; `"x²"` → `"x2"`; ligature `"ﬁle"` → `"file"`; full-width `"１０ ｍｍ"` → `"10mm"` (with R5). *(Today: no normalization — decomposed `"café"` → `"cafe"` (accent stripped, R6), `"Ｂｏｌｔ"` → `"ｂｏｌｔ"`, `"x²"` → `"x²"`, `"ﬁle"` → `"ﬁle"`, `"１０ ｍｍ"` → `"１０ ｍｍ"`.)*
- **R3.** Leading and trailing whitespace is removed, and every run of whitespace inside the name (spaces, tabs, newlines, non-breaking space U+00A0) becomes a single space: `"  Screw   Driver  "` → `"screw driver"`, `"x\tY\nz"` → `"x y z"`, `"a b"` → `"a b"`.
- **R4.** Whitespace-only input returns `""` (`"  "` → `""`).
- **R5.** A number followed by whitespace and then a word of 1 to 4 ASCII letters (`a`–`z` after lowercasing) that ends there — at the end of the text or at a space — is glued together:
  - `"Screw Driver 22 m"` → `"screw driver 22m"`, `"10 mm Bolt"` → `"10mm bolt"`, `"22 M"` → `"22m"`, `"10 KG"` → `"10kg"`, `"5 kgs"` → `"5kgs"` (3 letters), `"5 pack"` → `"5pack"` (exactly 4 letters), `"5 kg-pack"` → `"5kg pack"`;
  - a word of 5+ letters is not glued: `"5 packs"` → `"5 packs"` (exactly 5 letters), `"22 metres"` → `"22 metres"`;
  - a short word directly followed by a letter or digit is part of a longer word and is not glued: `"5 kg2"` → `"5 kg2"`;
  - every occurrence is glued: `"10 mm, 20 mm"` → `"10mm 20mm"`; `"2 x 3 m"` → `"2x 3m"`;
  - any short word is glued, not only units: `"iPhone 15 pro max"` → `"iphone 15pro max"`, `"Size 10 and up"` → `"size 10and up"` ✅;
  - the number may end an alphanumeric token: `"Model X5 pro"` → `"model x5pro"`; a decimal number glues only its last digit group because the dot becomes a space (R6): `"1.5 mm"` → `"1 5mm"`;
  - the number may use any Unicode decimal digits (`"٢ kg"` → `"٢kg"`, `"৫ kg"` → `"৫kg"`), but the word must be ASCII letters: a Bengali unit is not glued (`"৫ কেজি"` stays separated; with R6a it → `"৫ কেজি"`).
- **R5a.** [BUG-182] A number and a short word separated by punctuation or symbols (with or without spaces) are glued exactly as if separated by a space: `"Bolt 10-mm"`, `"Bolt 10.mm"`, `"Bolt 10 / mm"`, `"Bolt 10mm"` and `"Bolt 10 mm"` all → `"bolt 10mm"`; `"Size 5 (pack)"` → `"size 5pack"`; `"Bolt 10_mm"` → `"bolt 10mm"` (also needs BUG-183). *(Today: gluing runs before punctuation is removed, so `"Bolt 10-mm"` → `"bolt 10 mm"`, `"Bolt 10.mm"` → `"bolt 10 mm"`, `"Size 5 (pack)"` → `"size 5 pack"`.)*
- **R6.** Every character that is not a letter or number (as Python's `str.isalnum()` sees it), not a combining mark of category Mn/Mc, not one of the in-word joiners of R6b, and not whitespace is replaced by a space, then R7 applies. This covers punctuation and symbols (`"Screw-Driver"` → `"screw driver"`, `"Screw.Driver"` → `"screw driver"`, `"Bolt (M8)"` → `"bolt m8"`), enclosing marks (category Me: `"a⃝b"` → `"a b"`) and other format characters such as zero width space (`"a​b"` → `"a b"`).
- **R6a.** [BUG-180] Combining marks (Unicode categories Mn and Mc — e.g. Bengali vowel signs and the virama U+09CD) are kept as part of the word: `"চাল"` → `"চাল"`; `"চাল"`, `"চুল"` and `"চিল"` give three different results; `"মিনিকেট চাল ৫ কেজি"` → `"মিনিকেট চাল ৫ কেজি"`. A short ASCII word followed by a combining mark is part of a longer word and is not glued by R5: `"5 kq́"` → `"5 kq́"` — this example needs **both** BUG-180 and BUG-182 fixed (with only BUG-180 fixed it gives `"5kq́"`, because gluing still runs first and treats the mark as a word boundary; with only BUG-182 fixed it gives `"5kq"`, because the mark is removed before gluing); tag it `BUG-180; BUG-182`. *(Today: every combining mark becomes a space: `"চাল"`, `"চুল"`, `"চিল"` all → `"চ ল"`; `"5 kq́"` → `"5kq"`.)*
- **R6b.** [BUG-180] The invisible in-word joiners ZERO WIDTH JOINER U+200D, ZERO WIDTH NON-JOINER U+200C and SOFT HYPHEN U+00AD are deleted without leaving a space: `"র‍্যাব"` (with U+200D) → the same result as `"র্যাব"` (without it) → `"র্যাব"`; `"Screw­driver"` → `"screwdriver"`; `"a‌b"` → `"ab"`. (best-practice default, delegated by reviewer) *(Today: each joiner becomes a space, and the neighbouring vowel sign/virama too (see R6a): `"র‍্যাব"` → `"র য ব"`, `"Screw­driver"` → `"screw driver"`, `"a‌b"` → `"a b"`.)*
- **R6c.** [BUG-183] Underscore `_` is replaced by a space like any other punctuation: `"Screw_Driver"` → `"screw driver"`; `"__"` → `""`. *(Today: underscore is kept: `"Screw_Driver"` → `"screw_driver"`, `"__"` → `"__"`.)*
- **R7.** After R6, runs of spaces are collapsed to one and the result is trimmed; a name made only of punctuation/symbols returns `""` (`"--"` → `""`, `"!!!"` → `""`).
- **R8.** Spacing, case and punctuation variants of the same name give the same result: `"Screw Driver 22m"`, `"Screw Driver 22 m"`, `"  screw   driver  22  M  "` and `"Screw-Driver 22m"` all → `"screw driver 22m"`.
- **R8a.** [BUG-182] The function is idempotent for every input: `normalize_item_name(normalize_item_name(x)) == normalize_item_name(x)`, e.g. for `"Bolt 10-mm"`, `"bolt 10 mm"`, `"2 x 3 m"`, `"café"`, `"Ｂｏｌｔ"`, `"চাল"` and every other example in this spec. `"Screw_Driver"` also gives `"screw driver"` (with BUG-183). *(Today: not idempotent when gluing only becomes possible after the punctuation step: `"Bolt 10-mm"` → `"bolt 10 mm"`, and normalizing `"bolt 10 mm"` again gives `"bolt 10mm"`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| none — any `str` or `None` is accepted | — | — |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 20 | `if not name` → `""` (`""`, `None`) | R1 |
| — (intended, no line today) | NFKC normalization before lowercasing | R2a |
| 23 | lowercase + trim | R2, R3 |
| 24 | whitespace runs → single space | R3 |
| 25 | unit-glue regex matches / does not match (≤4 vs ≥5 letters, ASCII-only word, followed by letter/digit/mark, punctuation separator, multiple matches); intended to run after line 27 | R5, R5a, R6a, R8a |
| 26 | non-word, non-space character → space (punctuation, symbols, Me, Cf; intended: Mn/Mc kept, joiners deleted, `_` replaced) | R6, R6a, R6b, R6c |
| 27 | final collapse + trim; empty result | R4, R7 |

## Gap log
- G1 (item_name_normalize.cases.md gap 1) — Fact — R5: the "(exactly 4 letters)" label was on `"5 kgs"` (3 letters); relabelled it "(3 letters)" and added the real boundary examples `"5 pack"` → `"5pack"` (exactly 4 letters) and `"5 packs"` → `"5 packs"` (exactly 5 letters, not glued), both verified against the code at e48a092 (`[a-z]{1,4}\b`).
- G2 (item_name_normalize.cases.md gap 2) — Fact — R6a: `"5 kq́"` → `"5 kq́"` needs both fixes; traced the code: with only BUG-180 fixed the result is `"5kq́"` (gluing still runs first and the kept mark is a regex word boundary), with only BUG-182 fixed it is `"5kq"` (mark removed before gluing). Rule now states the example is tagged `BUG-180; BUG-182`. No new bug.
