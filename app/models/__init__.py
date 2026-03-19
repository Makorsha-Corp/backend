"""Models module"""

# Workspace multi-tenancy models
from app.models.subscription_plan import SubscriptionPlan
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_invitation import WorkspaceInvitation
from app.models.workspace_audit_log import WorkspaceAuditLog

# User & Access Control
from app.models.profile import Profile
from app.models.access_control import AccessControl

# Items & Tagging
from app.models.item import Item
from app.models.item_tag import ItemTag
from app.models.item_tag_assignment import ItemTagAssignment

# Inventory (Snapshot Tables)
from app.models.storage_item import StorageItem
from app.models.machine_item import MachineItem
from app.models.damaged_item import DamagedItem
from app.models.inventory import Inventory

# Inventory Ledgers (Transaction Logs)
from app.models.storage_item_ledger import StorageItemLedger
from app.models.machine_item_ledger import MachineItemLedger
from app.models.damaged_item_ledger import DamagedItemLedger
from app.models.inventory_ledger import InventoryLedger
from app.models.project_component_item_ledger import ProjectComponentItemLedger

# Production Module
from app.models.production_line import ProductionLine
from app.models.production_formula import ProductionFormula
from app.models.production_formula_item import ProductionFormulaItem
from app.models.production_batch import ProductionBatch
from app.models.production_batch_item import ProductionBatchItem

# Orders (Legacy - being migrated)
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_part_log import OrderPartLog

# Order System (New Split Architecture)
from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_item import ExpenseOrderItem

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
from app.models.machine_event import MachineEvent

# Projects
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_item import ProjectComponentItem
from app.models.project_component_task import ProjectComponentTask
from app.models.miscellaneous_project_cost import MiscellaneousProjectCost

# Attachments
from app.models.attachment import Attachment
from app.models.order_attachment import OrderAttachment
from app.models.project_attachment import ProjectAttachment
from app.models.project_component_attachment import ProjectComponentAttachment

# Accounts & Financial
from app.models.account import Account
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.models.account_invoice import AccountInvoice
from app.models.invoice_payment import InvoicePayment

# Vendors & Settings (Vendor deprecated - use Account)
from app.models.vendor import Vendor
from app.models.app_settings import AppSettings

__all__ = [
    # Workspace models
    "SubscriptionPlan",
    "Workspace",
    "WorkspaceMember",
    "WorkspaceInvitation",
    "WorkspaceAuditLog",
    # User & Access Control
    "Profile",
    "AccessControl",
    # Items & Tagging
    "Item",
    "ItemTag",
    "ItemTagAssignment",
    # Inventory (Snapshot Tables)
    "StorageItem",
    "MachineItem",
    "DamagedItem",
    "Inventory",
    # Inventory Ledgers (Transaction Logs)
    "StorageItemLedger",
    "MachineItemLedger",
    "DamagedItemLedger",
    "InventoryLedger",
    "ProjectComponentItemLedger",
    # Production Module
    "ProductionLine",
    "ProductionFormula",
    "ProductionFormulaItem",
    "ProductionBatch",
    "ProductionBatchItem",
    # Orders (Legacy - being migrated)
    "Order",
    "OrderItem",
    "OrderPartLog",
    # Order System (New Split Architecture)
    "OrderTemplate",
    "OrderTemplateItem",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "TransferOrder",
    "TransferOrderItem",
    "ExpenseOrder",
    "ExpenseOrderItem",
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
    "MachineEvent",
    # Projects
    "Project",
    "ProjectComponent",
    "ProjectComponentItem",
    "ProjectComponentTask",
    "MiscellaneousProjectCost",
    # Attachments
    "Attachment",
    "OrderAttachment",
    "ProjectAttachment",
    "ProjectComponentAttachment",
    # Accounts & Financial
    "Account",
    "AccountTag",
    "AccountTagAssignment",
    "AccountInvoice",
    "InvoicePayment",
    # Vendors & Settings
    "Vendor",
    "AppSettings",
]
