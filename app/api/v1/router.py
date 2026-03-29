"""API v1 router configuration"""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    workspaces,
    # Organization
    departments,
    factories,
    factory_sections,
    machines,
    machine_maintenance_logs,
    statuses,
    # Items & Inventory
    items,
    item_tags,
    storage_items,
    machine_items,
    damaged_items,
    inventory,
    products,
    # Accounts & Financial
    accounts,
    account_tags,
    account_invoices,
    invoice_payments,
    financial_audit_logs,
    # Orders
    orders,
    order_workflows,
    order_items,
    order_part_logs,
    work_orders,
    purchase_orders,
    transfer_orders,
    expense_orders,
    order_templates,
    # Sales
    sales_orders,
    sales_deliveries,
    # Production
    production_lines,
    production_formulas,
    production_batches,
    # Projects
    projects,
    project_components,
    project_component_items,
    project_component_tasks,
    miscellaneous_project_costs,
    project_component_notes,
    # Settings
    app_settings,
    access_control,
    # Ledgers
    ledgers,
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
api_router.include_router(storage_items.router, prefix="/storage-items", tags=["inventory"])
api_router.include_router(machine_items.router, prefix="/machine-items", tags=["inventory"])
api_router.include_router(damaged_items.router, prefix="/damaged-items", tags=["inventory"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(products.router, prefix="/products", tags=["inventory"])

# Accounts & Financial
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(account_tags.router, prefix="/account-tags", tags=["accounts"])
api_router.include_router(account_invoices.router, prefix="/account-invoices", tags=["accounts"])
api_router.include_router(invoice_payments.router, prefix="/invoice-payments", tags=["accounts"])
api_router.include_router(financial_audit_logs.router, prefix="/financial-audit-logs", tags=["audit"])

# Orders & Workflow
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(order_workflows.router, prefix="/order-workflows", tags=["orders"])
api_router.include_router(order_items.router, prefix="/order-items", tags=["orders"])
api_router.include_router(order_part_logs.router, prefix="/order-part-logs", tags=["orders"])

# Work Orders
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["orders"])

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
