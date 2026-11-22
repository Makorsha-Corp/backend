# Execution notes — `app/managers/attachment_markup_manager.py`

> Cases: `tests/unit/managers/attachment_markup_manager.cases.md` (revision 4) · Tests: `tests/unit/managers/test_attachment_markup_manager.py` · Source commit: e48a092
> Result: 97 passed · 105 xfailed (103 strict, 2 non-strict) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_attachment_markup_manager.py -q -p no:cacheprovider`

## How the tests are built
- One test per card (193), in card order, named `test_amup_<group>_<nn>__<slug>`; the first docstring line starts with the card ID. `# Then N` comments precede the checks of Then line N.
- **Standing rows** = fixture `S` (W0, W1, W2; U1 "Ana Rahman", U2 "Bilal Khan", UG "Mia Khan" with their W1 memberships; F0 / F1 / F9; A1 = att("plan.png") with link(A1, "scratch", 1)). Pure cards (`_is_markupable`, `_summarize_payload`) take no fixture.
- **Given rows** = local helpers named as in Conventions: `member`, `att` (`deleted=True` = deleted att, keywords = the "but" columns), `link`, `link_in` (a link filed under another workspace, the cards' explicit `AttachmentLink(workspace_id=W2.id, …)`), `proj` (`where="W0"/"W2"`, `private`, `deleted`), `pmem`, `comp`, `mach`, `item`, `ticket`, `set_owner`, `admin`, `stamp`, `layer`, `mev`, `older`, `seqscan`, `touchL`, `touchE`. Each adds and flushes one row.
- **Named checks**: `reread`, `NOW_DB(db)`, `layers_of`, `events_of` (expire, then select by attachment ordered by id), `counts` ("nothing written": rows of `attachment_markups` and `attachment_markup_events`, all workspaces; snapshot taken after the last Given line), `recorder` (+ `profile_reads`, `markup_reads`), `uids`, `eids`. `session:` lines are the three `not db.new / dirty / deleted` asserts, before any count.
- **call_uid**: `call_uid(fn, *args, user_id, **kw)` — the same helper as test_attachment_manager.py (reconciled across ATCM/AMUP). It adds `user_id=` only when `inspect.signature(fn)` has it, so the R1–R4 cards of `_get_ready_attachment` hold before and after BUG-2115.
- **Settings**: autouse fixture `amup_settings` (monkeypatch on `app.core.config.settings`); per-card overrides call `amup_settings.setattr(...)`.
- **Mocks**: none of the module (the spec names no external). Race simulation only in AMUP-PL-25: `patch("app.dao.attachment_markup.AttachmentMarkupDAO.get_for_user", return_value=None)`, the When inside `db.begin_nested()` (`sp.rollback()` on error, `sp.commit()` otherwise). "Rolled back" cards (LE-02, PL-26, DL-12) wrap `db.commit` with `patch.object(..., wraps=...)` around a savepoint that is rolled back.
- **xfail markers**: module-level `X2115 … X2120`, `X1437` strict; `X1435` (LL-05) and `X1436` (LV-04) non-strict, as the cards say.

### Verification done at execution
- `--runxfail` (scratch plugin `failcheck.py`): every one of the 97 strict xfails fails inside its card's named Then line. The 15 "returns" cards of BUG-2115 (GR-12, 13, …) and PL-25 fail on the When line itself, with the exception the card names (`TypeError: … unexpected keyword argument 'user_id'`, `IntegrityError` 23505) — that is what their "Fails today on" describes. LL-12 fails with 10 profile reads, LV-11 with 5, LV-06 with 200, SS-12 on Then 2. Revision 4: 105 failed — 103 strict on their named Then (GR-64…67 TypeError inside Then 1; GR-68 at the When, the call raising TypeError as its Then 1 line says; LL-14 DID NOT RAISE), 2 non-strict (LL-05, LV-04).
- **Reference plugin** (scratch `ref_amup.py`, loaded with `-p ref_amup --runxfail`; replaces methods in-process, never edits `app/`): patches in BUG-2115 (PR-1/2/3/5 check in `_get_ready_attachment(…, user_id)`, run before R3/R4; public methods pass their caller id), BUG-2116/2117 (minted-form `fullmatch`, url rebuilt with `build_signed_delivery_url`), BUG-2118 (no event on an equal payload), BUG-2119 (one `IN` query for authors), BUG-2120 (insert in a savepoint; `IntegrityError` → update the existing row, `markup_updated`), BUG-1435/1436 (id tie-breaks), BUG-1437 (no cap), and (Revision 3) the link-DAO fixes BUG-1433 (links ORDER BY id) / BUG-1434 (failed uploads not counted). Result: **193 passed**, so every line after each failure point runs. Revision 4 additions: the workspace owner (`owner_user_id`) opens every ticket of the workspace (BUG-2103); a platform admin opens tickets only, never a private project or its component (the project branch never consults `is_platform_admin`); visibility runs before the ready / markable checks; on a unique-key clash with the caller's row filed under another workspace the insert error stands and that row is never updated (PL-30). `-p ref_amup --runxfail` → **202 passed**.
- 3 plain runs: 94 passed, 99 xfailed each time (no flakiness). Revision 3 re-run: 94 passed · 99 xfailed twice, and once 94 passed · 98 xfailed · 1 xpassed — a non-strict tie-break card (LL-05 / LV-04, BUG-1435 / 1436) coming back in id order by chance, which is why those two are non-strict. Ruff clean; LF line endings.

## Discrepancies
None open. DISCREPANCY-1 (import of `MARKUP_UNAVAILABLE_MSG`) and DISCREPANCY-2 (PL-21 Fails-today wording) of revision 2 are closed by cases Revision 3; neither changed a marker or an expected value.

## Coverage gaps
None — 100% branch coverage (93 statements, 26 branches).

## Factories added
None (all builders local; shared decision for the ATCM / AMUP / MOBS batch).

## New bugs
None found (range BUG-2160…2169 unused).

## Notes for maintainers
- When BUG-2115 is fixed, the 53 GR xfails, LL-08/09/10/13, LV-09/10, PL-15…19, 21, 28, 29 and DL-08/09/10/13 will XPASS → remove `@X2115`. The `call_uid` pass cards keep working unchanged.
- LL-05 / LV-04 (non-strict) depend on `seqscan` + a physical row move; they may pass by chance before BUG-1435 / BUG-1436 are fixed.
- PL-01 / PL-04 compare `updated_at` with the database's `now()`, which is constant inside the test transaction.
- BUG-2117 fix calls the Cloudinary URL builder, which runs `cloudinary.config(...)` from settings (global state, no network).
- For upcoming features: the reference `_get_ready_attachment` is a working shape of the shared PR-1/2/3/5 parent check (link → record → `can_access_project` / `can_access_ticket` with the active-membership role) that the permissions work can lift into one helper (spec FU-2 asks the same for the minted-stamp check). Markup events (`markup_saved` / `markup_updated` / `markup_cleared`, with `session_id`) are the natural notification source; BUG-2118 must be fixed first or no-op saves would notify. Nothing here touches money.

## Revision history
- **2026-11-04 — Revision 2** (first execution): 193 cases → 94 passed · 99 xfailed (97 strict, 2 non-strict); DISCREPANCY-1, -2 recorded (card text only). Later the same day `call_uid` was aligned with test_attachment_manager.py: `call_uid(fn, *args, user_id, **kw)`.
- **2026-11-04 — Revision 3** (cases updated from these notes; no card added or removed): Conventions now name `MARKUP_UNAVAILABLE_MSG` as a class attribute (closes DISCREPANCY-1); PL-21's Fails-today line names the `AttachmentValidationError` (closes DISCREPANCY-2). No test code changed. Reference plugin extended with the link-DAO fixes BUG-1433 / BUG-1434; `--runxfail` 99 failed (97 strict on their named Then line, 2 non-strict), `-p ref_amup --runxfail` 193 passed; coverage 100%; ruff clean.
- **2026-11-04 — Revision 4** (verifier findings 1–3, spec G5 / BUG-2103): 202 cases → 97 passed · 105 xfailed (103 strict, 2 non-strict), 0 discrepancies.
  - New tests: GR-64 / GR-65 (platform admin refused a private project / its component, xfail BUG-2115), GR-66 / GR-67 (W1 link to a W2 / W0 ticket hidden, xfail BUG-2115), GR-68 (workspace owner opens another member's ticket, new marker `X2103`, strict xfail BUG-2103), LL-14 (admin sees no layers of a private project, xfail BUG-2115), PL-30 / DL-14 (caller's W2-filed row neither replaced nor deleted, pass; PL-30 wraps the When in a savepoint and rolls back on IntegrityError as the card says), PL-31 (G5: only the leading "Updated marks" becomes "Saved marks", pass).
  - Helper change: `layer(db, a, u, p, ws=None)` — `ws` is the card's "but workspace_id W"; existing calls unchanged. Import added: `sqlalchemy.exc.IntegrityError`.
  - No existing card changed; no test removed.
  - Checks: 3 plain runs 97 / 105 each; `--runxfail` 105 failed (103 strict on their named Then); `-p ref_amup --runxfail` 202 passed; branch coverage 100% (93 statements, 26 branches); ruff clean; LF.
