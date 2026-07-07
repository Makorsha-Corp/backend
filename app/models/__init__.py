"""Models module.

Alembic discovers models via app/db/base.py — keep imports there in sync with exports here.
"""

# Workspace multi-tenancy models
from app.models.subscription_plan import SubscriptionPlan
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_invitation import WorkspaceInvitation
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.models.refresh_token import RefreshToken

# User & Access Control
from app.models.profile import Profile
from app.models.access_control import AccessControl

# Items & Tagging
from app.models.item import Item
from app.models.item_tag import ItemTag
from app.models.item_tag_assignment import ItemTagAssignment

# Inventory (Snapshot Tables)
from app.models.machine_item import MachineItem
from app.models.inventory import Inventory
from app.models.product import Product

# Inventory Ledgers (Transaction Logs)
from app.models.machine_item_ledger import MachineItemLedger
from app.models.inventory_ledger import InventoryLedger
from app.models.product_ledger import ProductLedger
from app.models.project_component_item_ledger import ProjectComponentItemLedger

# Production Module
from app.models.production_line import ProductionLine
from app.models.production_formula import ProductionFormula
from app.models.production_formula_item import ProductionFormulaItem
from app.models.production_batch import ProductionBatch
from app.models.production_batch_item import ProductionBatchItem

# Order System (New Split Architecture)
from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.models.transfer_order_approver import TransferOrderApprover
from app.models.transfer_order_event import TransferOrderEvent
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_item import ExpenseOrderItem
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.expense_order_event import ExpenseOrderEvent

# Sales Module
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.sales_delivery import SalesDelivery
from app.models.sales_delivery_item import SalesDeliveryItem

# Order Workflow & Status
from app.models.order_workflow import OrderWorkflow
from app.models.status import Status

# Organization
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.department import Department
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_maintenance_log import MachineMaintenanceLog

# Projects
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.project_event import ProjectEvent
from app.models.project_component import ProjectComponent
from app.models.project_component_item import ProjectComponentItem
from app.models.project_component_task import ProjectComponentTask
from app.models.miscellaneous_project_cost import MiscellaneousProjectCost

# Attachments
from app.models.attachment import Attachment
from app.models.project_attachment import ProjectAttachment
from app.models.project_component_attachment import ProjectComponentAttachment

# Accounts & Financial
from app.models.account import Account
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.models.account_invoice import AccountInvoice
from app.models.invoice_item import InvoiceItem
from app.models.invoice_event import InvoiceEvent
from app.models.invoice_payment import InvoicePayment
from app.models.invoice_status_tracker import InvoiceStatusTracker
from app.models.financial_audit_log import FinancialAuditLog

# Work Orders
from app.models.work_order_type import WorkOrderType
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_template_item import WorkOrderTemplateItem
from app.models.work_order_template_approver import WorkOrderTemplateApprover
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.work_order_approver import WorkOrderApprover
from app.models.work_order_event import WorkOrderEvent
from app.models.project_component_activity_event import ProjectComponentActivityEvent

from app.models.app_settings import AppSettings
from app.models.discussion import Discussion
from app.models.notification import Notification

__all__ = [
    # Workspace models
    "SubscriptionPlan",
    "Workspace",
    "WorkspaceMember",
    "WorkspaceInvitation",
    "WorkspaceAuditLog",
    "RefreshToken",
    # User & Access Control
    "Profile",
    "AccessControl",
    # Items & Tagging
    "Item",
    "ItemTag",
    "ItemTagAssignment",
    # Inventory (Snapshot Tables)
    "MachineItem",
    "Inventory",
    "Product",
    # Inventory Ledgers (Transaction Logs)
    "MachineItemLedger",
    "InventoryLedger",
    "ProductLedger",
    "ProjectComponentItemLedger",
    # Production Module
    "ProductionLine",
    "ProductionFormula",
    "ProductionFormulaItem",
    "ProductionBatch",
    "ProductionBatchItem",
    # Order System (New Split Architecture)
    "OrderTemplate",
    "OrderTemplateItem",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "PurchaseOrderApprover",
    "PurchaseOrderEvent",
    "TransferOrder",
    "TransferOrderItem",
    "TransferOrderApprover",
    "TransferOrderEvent",
    "ExpenseOrder",
    "ExpenseOrderItem",
    "ExpenseOrderApprover",
    "ExpenseOrderEvent",
    # Sales Module
    "SalesOrder",
    "SalesOrderItem",
    "SalesDelivery",
    "SalesDeliveryItem",
    # Order Workflow & Status
    "OrderWorkflow",
    "Status",
    # Organization
    "Factory",
    "FactorySection",
    "Department",
    "Machine",
    "MachineActivityEvent",
    "MachineMaintenanceLog",
    # Projects
    "Project",
    "ProjectMember",
    "ProjectEvent",
    "ProjectComponent",
    "ProjectComponentItem",
    "ProjectComponentTask",
    "MiscellaneousProjectCost",
    # Attachments
    "Attachment",
    "ProjectAttachment",
    "ProjectComponentAttachment",
    # Accounts & Financial
    "Account",
    "AccountTag",
    "AccountTagAssignment",
    "AccountInvoice",
    "InvoiceItem",
    "InvoiceEvent",
    "InvoicePayment",
    "InvoiceStatusTracker",
    "FinancialAuditLog",
    # Work Orders
    "WorkOrderType",
    "WorkOrderTemplate",
    "WorkOrderTemplateItem",
    "WorkOrderTemplateApprover",
    "WorkOrder",
    "WorkOrderItem",
    "WorkOrderApprover",
    "WorkOrderEvent",
    "ProjectComponentActivityEvent",
    "AppSettings",
    "Discussion",
    "Notification",
]
