"""API v1 router configuration"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    access_control,
    account_invoices,
    account_tags,
    # Accounts & Financial
    accounts,
    # Settings
    app_settings,
    attachments,
    auth,
    calendar,
    delivery_methods,
    # Organization
    departments,
    # Discussions & Notifications
    discussions,
    expense_orders,
    factories,
    factory_sections,
    financial_audit_logs,
    help_tickets,
    inventory,
    invoice_items,
    invoice_payments,
    item_tags,
    # Items & Inventory
    items,
    landing_perf_reports,
    # Ledgers
    ledgers,
    machine_items,
    machine_maintenance_logs,
    machines,
    miscellaneous_project_costs,
    mobile_upload,
    notifications,
    order_templates,
    # Orders
    order_workflows,
    orders_overview,
    payments,
    platform_help,
    production_batches,
    production_formulas,
    # Production
    production_lines,
    products,
    project_component_items,
    project_component_notes,
    project_component_tasks,
    project_components,
    # Projects
    projects,
    purchase_orders,
    sales_deliveries,
    # Sales
    sales_orders,
    statuses,
    transfer_orders,
    waitlist,
    work_order_templates,
    work_order_types,
    work_orders,
    workspaces,
)

api_router = APIRouter()


# Health check endpoint
@api_router.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}


# Authentication & Workspaces
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])

# Organization & Structure
api_router.include_router(departments.router, prefix="/departments", tags=["organization"])
api_router.include_router(factories.router, prefix="/factories", tags=["organization"])
api_router.include_router(factory_sections.router, prefix="/factory-sections", tags=["organization"])
api_router.include_router(machines.router, prefix="/machines", tags=["organization"])
api_router.include_router(machine_maintenance_logs.router, prefix="/machine-maintenance-logs", tags=["organization"])
api_router.include_router(statuses.router, prefix="/statuses", tags=["organization"])

# Items & Inventory
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(item_tags.router, prefix="/item-tags", tags=["items"])
api_router.include_router(machine_items.router, prefix="/machine-items", tags=["inventory"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(products.router, prefix="/products", tags=["inventory"])

# Accounts & Financial
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(account_tags.router, prefix="/account-tags", tags=["accounts"])
api_router.include_router(account_invoices.router, prefix="/account-invoices", tags=["accounts"])
api_router.include_router(invoice_items.router, prefix="/invoice-items", tags=["accounts"])
api_router.include_router(invoice_payments.router, prefix="/invoice-payments", tags=["accounts"])
api_router.include_router(financial_audit_logs.router, prefix="/financial-audit-logs", tags=["audit"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])

# Orders & Workflow
api_router.include_router(orders_overview.router, prefix="/orders/overview", tags=["orders"])
api_router.include_router(order_workflows.router, prefix="/order-workflows", tags=["orders"])

# Work Orders
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["orders"])
api_router.include_router(work_order_types.router, prefix="/work-order-types", tags=["orders"])
api_router.include_router(work_order_templates.router, prefix="/work-order-templates", tags=["orders"])

# Purchase Orders
api_router.include_router(purchase_orders.router, prefix="/purchase-orders", tags=["orders"])

# Transfer Orders
api_router.include_router(transfer_orders.router, prefix="/transfer-orders", tags=["orders"])

# Expense Orders
api_router.include_router(expense_orders.router, prefix="/expense-orders", tags=["orders"])

# Order Templates
api_router.include_router(order_templates.router, prefix="/order-templates", tags=["orders"])

# Sales
api_router.include_router(sales_orders.router, prefix="/sales-orders", tags=["sales"])
api_router.include_router(sales_deliveries.router, prefix="/sales-deliveries", tags=["sales"])
api_router.include_router(delivery_methods.router, prefix="/delivery-methods", tags=["sales"])

# Production
api_router.include_router(production_lines.router, prefix="/production-lines", tags=["production"])
api_router.include_router(production_formulas.router, prefix="/production-formulas", tags=["production"])
api_router.include_router(production_batches.router, prefix="/production-batches", tags=["production"])

# Projects
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(project_components.router, prefix="/project-components", tags=["projects"])
api_router.include_router(project_component_items.router, prefix="/project-component-items", tags=["projects"])
api_router.include_router(project_component_tasks.router, prefix="/project-component-tasks", tags=["projects"])
api_router.include_router(miscellaneous_project_costs.router, prefix="/miscellaneous-project-costs", tags=["projects"])
api_router.include_router(project_component_notes.router, prefix="/project-component-notes", tags=["projects"])

# Settings & Access Control
api_router.include_router(app_settings.router, prefix="/app-settings", tags=["settings"])
api_router.include_router(access_control.router, prefix="/access-control", tags=["settings"])

# Ledgers & Reconciliation
api_router.include_router(ledgers.router, prefix="/ledgers", tags=["ledgers"])

# Discussions & Notifications
api_router.include_router(discussions.router, prefix="/discussions", tags=["discussions"])
api_router.include_router(notifications.router, prefix="/me/notifications", tags=["notifications"])

# Calendar
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])

# Landing waitlist (public signup + platform admin list)
api_router.include_router(waitlist.router, prefix="/waitlist", tags=["waitlist"])

# Landing perf feedback (public submit + platform admin list)
api_router.include_router(
    landing_perf_reports.router,
    prefix="/landing-perf-reports",
    tags=["landing-perf-reports"],
)

# Attachments (Cloudinary signed uploads)
api_router.include_router(attachments.router, prefix="/attachments", tags=["attachments"])

# Mobile upload portal (QR phone-to-desktop staging)
api_router.include_router(mobile_upload.router, prefix="/mobile-upload", tags=["mobile-upload"])

# Help / support tickets
api_router.include_router(help_tickets.router, prefix="/help", tags=["help"])

# Platform admin (Makorsha staff)
api_router.include_router(platform_help.router, prefix="/platform", tags=["platform"])
