# -*- coding: utf-8 -*-
import json, os, datetime

HERE = os.path.dirname(__file__)
INV = json.load(open(os.path.join(HERE, "inventory.json")))
OUTDIR = os.path.abspath(os.path.join(HERE, ".."))  # docs/testing/
os.makedirs(OUTDIR, exist_ok=True)

# ---- potentially-unused lookup (from deadcode.py heuristic) ----
DEAD = json.load(open(os.path.join(HERE, "deadcode.json")))
DEAD_METHODS = set()   # (file, "Class.method") or (file, "func")
DEAD_CLASSES = set()   # (file, "Class")
for fpath, items in DEAD:
    for kind, name, ln in items:
        if kind == "class":
            DEAD_CLASSES.add((fpath, name))
        else:
            DEAD_METHODS.add((fpath, name))
FLAG = " ⚠️ **[possibly unused — verify before testing]**"

LAYER_TITLES = {
    "app/managers": "Managers",
    "app/services": "Services",
    "app/utils": "Utils",
    "app/core": "Core",
    "app/integrations": "Integrations",
    "app/dao": "DAOs",
}
LAYER_ORDER = ["app/managers", "app/services", "app/utils", "app/core", "app/integrations", "app/dao"]

# ---- domain mapping by file stem ----
DOMAIN = {
    # Auth & Security
    "auth_service": "Auth & Security",
    "security": "Auth & Security",
    "profile_auth": "Auth & Security",
    "profile_stamp_manager": "Auth & Security",
    "profile": "Auth & Security",
    "refresh_token": "Auth & Security",
    "timezone_validate": "Auth & Security",
    # Workspace, Accounts & Org Structure
    "workspace_manager": "Workspace, Accounts & Org Structure",
    "workspace_service": "Workspace, Accounts & Org Structure",
    "workspace": "Workspace, Accounts & Org Structure",
    "workspace_member": "Workspace, Accounts & Org Structure",
    "workspace_invitation": "Workspace, Accounts & Org Structure",
    "workspace_audit_log": "Workspace, Accounts & Org Structure",
    "access_control": "Workspace, Accounts & Org Structure",
    "access_control_service": "Workspace, Accounts & Org Structure",
    "account_manager": "Workspace, Accounts & Org Structure",
    "account_service": "Workspace, Accounts & Org Structure",
    "account": "Workspace, Accounts & Org Structure",
    "account_tag": "Workspace, Accounts & Org Structure",
    "account_tag_service": "Workspace, Accounts & Org Structure",
    "account_tag_assignment": "Workspace, Accounts & Org Structure",
    "department_manager": "Workspace, Accounts & Org Structure",
    "department_service": "Workspace, Accounts & Org Structure",
    "department": "Workspace, Accounts & Org Structure",
    "factory_manager": "Workspace, Accounts & Org Structure",
    "factory_service": "Workspace, Accounts & Org Structure",
    "factory": "Workspace, Accounts & Org Structure",
    "factory_section_manager": "Workspace, Accounts & Org Structure",
    "factory_section_service": "Workspace, Accounts & Org Structure",
    "factory_section": "Workspace, Accounts & Org Structure",
    "app_settings": "Workspace, Accounts & Org Structure",
    "app_settings_service": "Workspace, Accounts & Org Structure",
    # Attachments & Uploads
    "attachment_manager": "Attachments & Uploads",
    "attachment_markup_manager": "Attachments & Uploads",
    "attachment_service": "Attachments & Uploads",
    "attachment_markup_service": "Attachments & Uploads",
    "attachment": "Attachments & Uploads",
    "attachment_ledger": "Attachments & Uploads",
    "attachment_link": "Attachments & Uploads",
    "attachment_markup": "Attachments & Uploads",
    "attachment_markup_event": "Attachments & Uploads",
    "attachment_allowlist": "Attachments & Uploads",
    "cloudinary_client": "Attachments & Uploads",
    "mobile_upload_session_manager": "Attachments & Uploads",
    "mobile_upload_service": "Attachments & Uploads",
    "mobile_upload_session": "Attachments & Uploads",
    "project_attachment": "Attachments & Uploads",
    "project_component_attachment": "Attachments & Uploads",
    # Items & Catalog
    "item_manager": "Items & Catalog",
    "item_service": "Items & Catalog",
    "item_summary_service": "Items & Catalog",
    "item_orders_service": "Items & Catalog",
    "item": "Items & Catalog",
    "item_tag": "Items & Catalog",
    "item_tag_service": "Items & Catalog",
    "item_tag_assignment": "Items & Catalog",
    "item_name_normalize": "Items & Catalog",
    "order_catalog_items": "Items & Catalog",
    "product_manager": "Items & Catalog",
    "product_service": "Items & Catalog",
    "product": "Items & Catalog",
    "product_ledger": "Inventory & Ledgers",
    # Inventory & Ledgers
    "inventory_manager": "Inventory & Ledgers",
    "inventory_movements": "Inventory & Ledgers",
    "inventory_service": "Inventory & Ledgers",
    "inventory": "Inventory & Ledgers",
    "inventory_ledger": "Inventory & Ledgers",
    "ledger_manager": "Inventory & Ledgers",
    "ledger_service": "Inventory & Ledgers",
    "to_inventory": "Inventory & Ledgers",
    "po_machine_inventory": "Inventory & Ledgers",
    "po_receive_inventory": "Inventory & Ledgers",
    "po_return_inventory": "Inventory & Ledgers",
    "po_storage_inventory": "Inventory & Ledgers",
    "project_component_item_ledger": "Inventory & Ledgers",
    "machine_item_ledger": "Inventory & Ledgers",
    # Purchase Orders
    "purchase_order_manager": "Purchase Orders",
    "purchase_order_return_manager": "Purchase Orders",
    "purchase_order_service": "Purchase Orders",
    "purchase_order_item_insights_service": "Purchase Orders",
    "purchase_order": "Purchase Orders",
    "purchase_order_approver": "Purchase Orders",
    "purchase_order_event": "Purchase Orders",
    "purchase_order_return": "Purchase Orders",
    "po_receive_event": "Purchase Orders",
    # Sales Orders & Deliveries
    "sales_manager": "Sales Orders & Deliveries",
    "sales_order_return_manager": "Sales Orders & Deliveries",
    "sales_service": "Sales Orders & Deliveries",
    "sales_order": "Sales Orders & Deliveries",
    "sales_order_approver": "Sales Orders & Deliveries",
    "sales_order_event": "Sales Orders & Deliveries",
    "sales_order_item": "Sales Orders & Deliveries",
    "sales_order_return": "Sales Orders & Deliveries",
    "sales_delivery": "Sales Orders & Deliveries",
    "sales_delivery_item": "Sales Orders & Deliveries",
    # Transfer Orders
    "transfer_order_manager": "Transfer Orders",
    "transfer_order_service": "Transfer Orders",
    "transfer_order": "Transfer Orders",
    "transfer_order_approver": "Transfer Orders",
    "transfer_order_event": "Transfer Orders",
    # Work Orders
    "work_order_manager": "Work Orders",
    "work_order_template_manager": "Work Orders",
    "work_order_type_manager": "Work Orders",
    "work_order_service": "Work Orders",
    "work_order_template_service": "Work Orders",
    "work_order_type_service": "Work Orders",
    "machine_work_service": "Work Orders",
    "work_order": "Work Orders",
    "work_order_approver": "Work Orders",
    "work_order_assignee": "Work Orders",
    "work_order_completer": "Work Orders",
    "work_order_event": "Work Orders",
    "work_order_item": "Work Orders",
    "work_order_template": "Work Orders",
    "work_order_type": "Work Orders",
    "work_order_calendar": "Work Orders",
    "work_order_generation": "Work Orders",
    "work_order_recurrence": "Work Orders",
    "work_order_workers": "Work Orders",
    # Expense Orders
    "expense_order_manager": "Expense Orders",
    "expense_order_service": "Expense Orders",
    "expense_order": "Expense Orders",
    "expense_order_approver": "Expense Orders",
    "expense_order_event": "Expense Orders",
    # Order Infrastructure & Workflow
    "order_template_manager": "Order Infrastructure & Workflow",
    "order_template_service": "Order Infrastructure & Workflow",
    "order_template": "Order Infrastructure & Workflow",
    "order_workflow_service": "Order Infrastructure & Workflow",
    "order_workflow": "Order Infrastructure & Workflow",
    "order_workflow_terminal": "Order Infrastructure & Workflow",
    "orders_overview_service": "Order Infrastructure & Workflow",
    "order_hub_stats_helpers": "Order Infrastructure & Workflow",
    "approval_notification_service": "Order Infrastructure & Workflow",
    "status_service": "Order Infrastructure & Workflow",
    "status": "Order Infrastructure & Workflow",
    "delivery_method_manager": "Order Infrastructure & Workflow",
    "delivery_method_service": "Order Infrastructure & Workflow",
    "delivery_method": "Order Infrastructure & Workflow",
    # Machines
    "machine_manager": "Machines",
    "machine_activity_manager": "Machines",
    "machine_item_manager": "Machines",
    "machine_maintenance_log_manager": "Machines",
    "machine_section_assignment_manager": "Machines",
    "machine_service": "Machines",
    "machine_item_service": "Machines",
    "machine_maintenance_log_service": "Machines",
    "machine": "Machines",
    "machine_activity_event": "Machines",
    "machine_item": "Machines",
    "machine_maintenance_log": "Machines",
    "machine_section_assignment": "Machines",
    # Projects
    "project_manager": "Projects",
    "project_component_activity_manager": "Projects",
    "project_service": "Projects",
    "project_component_service": "Projects",
    "project_component_item_service": "Projects",
    "project_component_note_service": "Projects",
    "project_component_task_service": "Projects",
    "miscellaneous_project_cost_service": "Projects",
    "project": "Projects",
    "project_component": "Projects",
    "project_component_activity_event": "Projects",
    "project_component_item": "Projects",
    "project_component_task": "Projects",
    "project_event": "Projects",
    "project_member": "Projects",
    "miscellaneous_project_cost": "Projects",
    # Production
    "production_batch_manager": "Production",
    "production_formula_manager": "Production",
    "production_line_manager": "Production",
    "production_batch_service": "Production",
    "production_formula_service": "Production",
    "production_line_service": "Production",
    "production_batch": "Production",
    "production_batch_item": "Production",
    "production_batch_stage_log": "Production",
    "production_formula": "Production",
    "production_formula_item": "Production",
    "production_formula_stage": "Production",
    "production_line": "Production",
    # Invoicing & AR
    "account_invoice_manager": "Invoicing & Accounts Receivable",
    "invoice_payment_manager": "Invoicing & Accounts Receivable",
    "account_invoice_service": "Invoicing & Accounts Receivable",
    "invoice_payment_service": "Invoicing & Accounts Receivable",
    "account_invoice": "Invoicing & Accounts Receivable",
    "invoice_item": "Invoicing & Accounts Receivable",
    "invoice_payment": "Invoicing & Accounts Receivable",
    "invoice_event": "Invoicing & Accounts Receivable",
    # Subscription Billing & Payment Gateway
    "payment_transaction_manager": "Subscription Billing & Payment Gateway",
    "payment_transaction_service": "Subscription Billing & Payment Gateway",
    "payment_transaction": "Subscription Billing & Payment Gateway",
    "payment_transaction_event": "Subscription Billing & Payment Gateway",
    "subscription_plan": "Subscription Billing & Payment Gateway",
    "client": "Subscription Billing & Payment Gateway",
    "mock_client": "Subscription Billing & Payment Gateway",
    # Notifications & Discussions
    "notification_service": "Notifications & Discussions",
    "notification_stream": "Notifications & Discussions",
    "notification": "Notifications & Discussions",
    "notification_entity_label": "Notifications & Discussions",
    "notification_channels": "Notifications & Discussions",
    "notification_types": "Notifications & Discussions",
    "discussion_service": "Notifications & Discussions",
    "discussion": "Notifications & Discussions",
    # Calendar
    "calendar_service": "Calendar",
    # Help, Waitlist & Platform Admin
    "help_ticket_manager": "Help, Waitlist & Platform Admin",
    "help_ticket_service": "Help, Waitlist & Platform Admin",
    "help_ticket": "Help, Waitlist & Platform Admin",
    "waitlist_service": "Help, Waitlist & Platform Admin",
    "waitlist": "Help, Waitlist & Platform Admin",
    "waitlist_admin": "Help, Waitlist & Platform Admin",
    "waitlist_signup": "Help, Waitlist & Platform Admin",
    # Financial Audit
    "financial_audit_log_service": "Financial Audit",
    "financial_audit_log": "Financial Audit",
    "audit_logger": "Financial Audit",
    # Shared Infrastructure
    "base_manager": "Shared Infrastructure",
    "base_service": "Shared Infrastructure",
    "base": "Shared Infrastructure",
    "config": "Shared Infrastructure",
    "deps": "Shared Infrastructure",
    "exceptions": "Shared Infrastructure",
    "limiter": "Shared Infrastructure",
    "middleware": "Shared Infrastructure",
    "utc_json_middleware": "Shared Infrastructure",
    "datetime_serialize": "Shared Infrastructure",
    "time": "Shared Infrastructure",
}

DOMAIN_ORDER = [
    "Auth & Security",
    "Workspace, Accounts & Org Structure",
    "Items & Catalog",
    "Inventory & Ledgers",
    "Purchase Orders",
    "Sales Orders & Deliveries",
    "Transfer Orders",
    "Work Orders",
    "Expense Orders",
    "Order Infrastructure & Workflow",
    "Machines",
    "Projects",
    "Production",
    "Invoicing & Accounts Receivable",
    "Subscription Billing & Payment Gateway",
    "Notifications & Discussions",
    "Calendar",
    "Attachments & Uploads",
    "Help, Waitlist & Platform Admin",
    "Financial Audit",
    "Shared Infrastructure",
]

def stem(path):
    return os.path.splitext(os.path.basename(path))[0]

UNMAPPED = set()

def domain_for(path):
    s = stem(path)
    if s in DOMAIN:
        return DOMAIN[s]
    if "sslcommerz" in path:
        return "Subscription Billing & Payment Gateway"
    UNMAPPED.add(path)
    return "Unclassified"

def file_entries():
    """yield (file, layer, classes, functions) skipping empty files."""
    for e in INV:
        if "error" in e:
            continue
        if not e["classes"] and not e["functions"]:
            continue
        yield e

def tag(m):
    parts = []
    if m.get("async"):
        parts.append("async")
    if m.get("dunder"):
        parts.append("dunder")
    elif m.get("private"):
        parts.append("private")
    return (" _(" + ", ".join(parts) + ")_") if parts else ""

def render_file_block(e, lines):
    fp = e["file"]
    for c in sorted(e["classes"], key=lambda x: x["lineno"]):
        base = f" ({', '.join(c['bases'])})" if c["bases"] else ""
        cflag = FLAG if (fp, c["name"]) in DEAD_CLASSES else ""
        lines.append(f"#### class `{c['name']}`{base}{cflag}")
        lines.append("")
        if not c["methods"]:
            lines.append("_(no methods defined in class body)_")
            lines.append("")
        for m in c["methods"]:
            mf = FLAG if (fp, f'{c["name"]}.{m["name"]}') in DEAD_METHODS else ""
            lines.append(f"- [ ] `{c['name']}.{m['name']}()` — L{m['lineno']}{tag(m)}{mf}")
        lines.append("")
    modfns = [f for f in e["functions"]]
    if modfns:
        lines.append("#### module-level functions")
        lines.append("")
        for f in sorted(modfns, key=lambda x: x["lineno"]):
            t = " _(private)_" if f.get("private") else ""
            t += " _(async)_" if f.get("async") else ""
            ff = FLAG if (fp, f["name"]) in DEAD_METHODS else ""
            lines.append(f"- [ ] `{f['name']}()` — L{f['lineno']}{t}{ff}")
        lines.append("")

def count_callables(e):
    return sum(len(c["methods"]) for c in e["classes"]) + len(e["functions"])

# ================= FILE 1: BY LAYER =================
def build_by_layer():
    entries = list(file_entries())
    total = sum(count_callables(e) for e in entries)
    L = []
    L.append("# Unit Test Checklist — by Code Layer")
    L.append("")
    L.append(f"> Generated {datetime.date.today().isoformat()} from `app/` source via AST parse. "
             f"One checkbox per function/method. Use this file to drive **unit-test** coverage.")
    L.append("")
    L.append(f"**Total callables:** {total} across {len(entries)} files "
             f"(managers, services, utils, core, integrations, DAOs). Private helpers and dunder "
             f"methods are included and tagged.")
    L.append("")
    L.append("Legend: `_(private)_` leading-underscore helper · `_(async)_` coroutine · "
             "`_(dunder)_` magic method · `Lnnn` source line · "
             "⚠️ reference scan found no use of this callable — triage before testing, see "
             "`dead-code-removal-checklist.md`.")
    L.append("")
    # per-layer summary table
    L.append("| Layer | Files | Classes | Callables |")
    L.append("|---|--:|--:|--:|")
    for layer in LAYER_ORDER:
        le = [e for e in entries if e["layer"] == layer]
        nc = sum(len(e["classes"]) for e in le)
        ncall = sum(count_callables(e) for e in le)
        L.append(f"| {LAYER_TITLES[layer]} | {len(le)} | {nc} | {ncall} |")
    L.append("")
    for layer in LAYER_ORDER:
        le = sorted([e for e in entries if e["layer"] == layer], key=lambda x: x["file"])
        if not le:
            continue
        ncall = sum(count_callables(e) for e in le)
        L.append(f"## {LAYER_TITLES[layer]} ({ncall} callables)")
        L.append("")
        for e in le:
            L.append(f"### `{e['file']}` ({count_callables(e)})")
            L.append("")
            render_file_block(e, L)
    return "\n".join(L) + "\n"

# ================= FILE 2: BY DOMAIN =================
def build_by_domain():
    entries = list(file_entries())
    # group
    groups = {}
    for e in entries:
        d = domain_for(e["file"])
        groups.setdefault(d, []).append(e)
    total = sum(count_callables(e) for e in entries)
    L = []
    L.append("# Unit Test Checklist — by Domain")
    L.append("")
    L.append(f"> Generated {datetime.date.today().isoformat()} from `app/` source via AST parse. "
             f"Same callables as the by-layer file, regrouped by business domain so each domain's "
             f"checklist can also seed **integration-test** planning.")
    L.append("")
    L.append(f"**Total callables:** {total}. Each function appears once, under a single domain. "
             f"Within a domain, files are ordered managers → services → utils → core → integrations → DAOs.")
    L.append("")
    L.append("Legend: `_(private)_` leading-underscore helper · `_(async)_` coroutine · "
             "`_(dunder)_` magic method · `Lnnn` source line · "
             "⚠️ reference scan found no use of this callable — triage before testing, see "
             "`dead-code-removal-checklist.md`.")
    L.append("")
    L.append("| Domain | Files | Callables |")
    L.append("|---|--:|--:|")
    order = DOMAIN_ORDER + sorted(d for d in groups if d not in DOMAIN_ORDER)
    for d in order:
        if d not in groups:
            continue
        ge = groups[d]
        L.append(f"| {d} | {len(ge)} | {sum(count_callables(e) for e in ge)} |")
    L.append("")
    for d in order:
        if d not in groups:
            continue
        ge = sorted(groups[d], key=lambda e: (LAYER_ORDER.index(e["layer"]), e["file"]))
        ncall = sum(count_callables(e) for e in ge)
        L.append(f"## {d} ({ncall} callables)")
        L.append("")
        cur_layer = None
        for e in ge:
            if e["layer"] != cur_layer:
                cur_layer = e["layer"]
                L.append(f"### {LAYER_TITLES[cur_layer]}")
                L.append("")
            L.append(f"#### `{e['file']}` ({count_callables(e)})")
            L.append("")
            render_file_block(e, L)
    return "\n".join(L) + "\n"

CONFIRMED_DEAD = {
    ("app/managers/po_machine_inventory.py", "post_purchase_order_to_machine"):
        "legacy PO→inventory posting, superseded by po_receive_inventory",
    ("app/managers/po_storage_inventory.py", "post_purchase_order_to_storage"):
        "same; only its PO_INVENTORY_SOURCE_TYPE constant is still imported",
    ("app/services/sales_service.py", "SalesService.create_sales_order"):
        "dead wrapper; endpoint calls create_sales_order_from_dict directly",
    ("app/services/account_service.py", "AccountService.get_accounts"):
        "no caller",
}

def build_unused():
    total = len(DEAD_METHODS) + len(DEAD_CLASSES)
    L = []
    L.append("# Dead-Code Removal Checklist")
    L.append("")
    L.append(f"> Generated {datetime.date.today().isoformat()}. **Heuristic** static reference "
             f"scan over `app/`, `tests/`, `alembic/`, `scripts/`. Each entry below is a "
             f"function / method / class whose name is **never referenced anywhere** outside its "
             f"own definition — no call, no import, no identifier-string.")
    L.append("")
    L.append(f"**{total} candidates across {len(DEAD)} files.** Same items are flagged ⚠️ in the "
             f"two unit-test checklists; deleting one here means striking its ⚠️ line there too.")
    L.append("")
    L.append("## How to work this list (from the IDE)")
    L.append("")
    L.append("For each unchecked item:")
    L.append("")
    L.append("1. Open `file:line` (click the ref).")
    L.append("2. **Find Usages** on the symbol — PyCharm `Alt+F7`, VS Code `Shift+F12`.")
    L.append("3. Also grep the repo for the name as a **string** (dynamic dispatch, `getattr`, router wiring).")
    L.append("4. Decide:")
    L.append("   - **truly unused** → delete the definition (and its now-orphaned imports / tests); tick the box.")
    L.append("   - **used after all** → tick the box, append `— KEEP: <where it's used>`.")
    L.append("   - **should be used but isn't (bug/regression)** → tick, append `— BUG: <note>`, open a ticket.")
    L.append("5. Run `pytest -q` after each file's worth of deletions.")
    L.append("")
    L.append("### Blind spots (why an item might actually be live)")
    L.append("- Dynamic dispatch: `getattr`, string-keyed registries.")
    L.append("- Callers that lived only in Alembic data migrations since squashed.")
    L.append("- Called from the frontend repo or ad-hoc scripts not scanned here.")
    L.append("- Reverse name-collision can *hide* a real dead one — treat this list as a floor.")
    L.append("")
    L.append("### Already spot-checked — confirmed dead, safe to delete")
    for (fp, nm), why in CONFIRMED_DEAD.items():
        L.append(f"- [ ] `{fp}` → `{nm}` — {why}")
    L.append("")
    L.append("---")
    L.append("")
    by_layer = {}
    for fpath, items in DEAD:
        e = next(x for x in INV if x["file"] == fpath)
        by_layer.setdefault(e["layer"], []).append((fpath, items))
    for layer in LAYER_ORDER:
        grp = sorted(by_layer.get(layer, []))
        if not grp:
            continue
        n = sum(len(i) for _, i in grp)
        L.append(f"## {LAYER_TITLES[layer]} — {n} candidate(s), {len(grp)} file(s)")
        L.append("")
        for fpath, items in grp:
            L.append(f"### `{fpath}`")
            L.append("")
            for kind, name, ln in items:
                note = ""
                if (fpath, name) in CONFIRMED_DEAD:
                    note = f"  **← confirmed dead: {CONFIRMED_DEAD[(fpath, name)]}**"
                priv = " _(private helper)_" if name.split(".")[-1].startswith("_") else ""
                L.append(f"- [ ] [`{fpath}:{ln}`]({fpath}#L{ln}) — {kind} `{name}`{priv}{note}")
            L.append("")
    return "\n".join(L) + "\n"

f1 = build_by_layer()
f2 = build_by_domain()
f3 = build_unused()
open(os.path.join(OUTDIR, "unit-test-checklist-by-layer.md"), "w", encoding="utf-8").write(f1)
open(os.path.join(OUTDIR, "unit-test-checklist-by-domain.md"), "w", encoding="utf-8").write(f2)
open(os.path.join(OUTDIR, "dead-code-removal-checklist.md"), "w", encoding="utf-8").write(f3)
print("wrote", OUTDIR)
print("unmapped files ->", sorted(UNMAPPED))
print("flagged:", len(DEAD_METHODS) + len(DEAD_CLASSES))
