## Fix: Plan-day stops making work orders for templates in deleted factory sections, and template lists keep a fixed order

**Fixes BUG-2330, BUG-2331 and BUG-2332.** One file. No database change, no API shape change.

---

### What was wrong

**1. Plan-day made work orders for sections that had been deleted (BUG-2332). This is the one with a real effect.**

Recurring work order templates belong to a factory section, for example "Weaving – Line 2". When you run **Plan day** for a factory, the system creates a draft work order for every recurring template that is due. It never checked whether the template's section had been **deleted**.

*Example:* Factory A had a section "Dyeing", which was deleted last month when that area closed. Its daily "Clean the dye vats" template still existed. Every Plan-day run for Factory A kept creating a "Clean the dye vats" draft for a section that no longer exists. Running Plan day for the deleted section itself also still produced its templates' drafts.

**2. The template list could repeat or skip a template (BUG-2330)**

Same problem as on other lists: templates created at the same moment had no fixed order, so paging could show one twice and miss another.

**3. A template's default approvers came back in random order (BUG-2331)**

The approvers set on a template had no order, so they could appear differently each time, including when copied onto a new work order.

---

### What changed

All in `app/dao/work_order_template.py`:

```diff
  # Plan-day for a factory: a template only matches if its section is in that factory AND not deleted
- | (FactorySection.factory_id == factory_id)
+ | ((FactorySection.factory_id == factory_id) & (FactorySection.is_deleted == False))

  # Plan-day for one section: the section must still exist
+ WorkOrderTemplate.default_factory_section_id.in_(<ids of sections that are not deleted>)

  # template list: tie-break on id
- .order_by(desc(WorkOrderTemplate.created_at))
+ .order_by(desc(WorkOrderTemplate.created_at), desc(WorkOrderTemplate.id))

  # default approvers: in the order they were added
+ .order_by(WorkOrderTemplateApprover.id)
```

Templates with **no section** still match a factory run, as before.

### What you'll notice

- Plan day no longer creates drafts for templates whose section was deleted. **Plan-day runs may create fewer drafts than before.** That's the intended result.
- Drafts that were already created are left alone; nothing is deleted or edited.
- If a deleted section is later restored, its templates are picked up again on the next run, with one draft for that day. Missed days are not back-filled, which is how overdue templates already behave.
- Template lists and approver lists keep a fixed order.

### What to look at when reviewing

- **The two Plan-day conditions above.** This is the only change that alters behaviour. The rest is ordering.
- **One remaining gap, not in this PR.** When you run Plan day for a *single section*, the manager has a fallback that also picks up that section's templates without checking whether it was deleted. So for that one case, a deleted section still gets drafts. It's logged as **BUG-3300** for a later fix in the manager file, and BUG-889 is related.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:**
  - The only caller of the Plan-day query is `WorkOrderTemplateManager.generate_drafts` (`POST /work-order-templates/generate-drafts/`).
  - The planning-sheet recurrence paths work on one template by id and are unaffected.
  - Checked combinations: both factory and section given, templates with no section, factory id 0, section id 0. All behave as intended.
  - Approval logic counts approvers and doesn't depend on their order.
- **Contract:** no change. No frontend PR.
- **Tests:** the 9 tests marked as known failures for these bugs now pass, and their markers are removed. Every other test in the full suite had the same result before and after (flip check CLEAN, base `d5fea1c`).
- **Commits:** `23cb9e5` (fix), `ca320bd` (merge of main for Postgres 18 CI).

</details>
