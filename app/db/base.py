"""
SQLAlchemy Base class and common imports

Import all models here to ensure they are registered with SQLAlchemy
before Alembic attempts to autogenerate migrations
"""
# ruff: noqa: F401  (imports register every model with Base.metadata for Alembic — they look unused but must stay)
from app.db.base_class import Base
from app.models.access_control import AccessControl
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.models.app_settings import AppSettings
from app.models.attachment import Attachment
from app.models.attachment_ledger import AttachmentLedger
from app.models.attachment_link import AttachmentLink
from app.models.attachment_markup import AttachmentMarkup
from app.models.attachment_markup_event import AttachmentMarkupEvent
from app.models.delivery_method import DeliveryMethod
from app.models.department import Department
from app.models.discussion import Discussion

# Expense Orders
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.expense_order_event import ExpenseOrderEvent
from app.models.expense_order_item import ExpenseOrderItem
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.financial_audit_log import FinancialAuditLog
from app.models.help_ticket import HelpTicket

# Inventory & Products
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.invoice_payment import InvoicePayment
from app.models.invoice_status_tracker import InvoiceStatusTracker
from app.models.item import Item
from app.models.item_tag import ItemTag
from app.models.item_tag_assignment import ItemTagAssignment
from app.models.landing_perf_report import LandingPerfReport
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_item import MachineItem
from app.models.machine_item_ledger import MachineItemLedger
from app.models.machine_maintenance_log import MachineMaintenanceLog
from app.models.miscellaneous_project_cost import MiscellaneousProjectCost
from app.models.mobile_upload_session import MobileUploadSession
from app.models.notification import Notification

# Order Templates
from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
from app.models.order_workflow import OrderWorkflow
from app.models.payment_transaction import PaymentTransaction
from app.models.payment_transaction_event import PaymentTransactionEvent
from app.models.po_receive_event import PoReceiveEvent, PoReceiveEventItem
from app.models.product import Product
from app.models.product_ledger import ProductLedger
from app.models.production_batch import ProductionBatch
from app.models.production_batch_item import ProductionBatchItem
from app.models.production_batch_stage_log import ProductionBatchStageLog
from app.models.production_formula import ProductionFormula
from app.models.production_formula_item import ProductionFormulaItem
from app.models.production_formula_stage import ProductionFormulaStage

# Production
from app.models.production_line import ProductionLine

# Import all models here to ensure they are discovered by Alembic
from app.models.profile import Profile
from app.models.project import Project
from app.models.project_attachment import ProjectAttachment
from app.models.project_component import ProjectComponent
from app.models.project_component_attachment import ProjectComponentAttachment
from app.models.project_component_item import ProjectComponentItem
from app.models.project_component_item_ledger import ProjectComponentItemLedger
from app.models.project_component_task import ProjectComponentTask
from app.models.project_event import ProjectEvent
from app.models.project_member import ProjectMember

# Purchase Orders
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_return import (
    PurchaseOrderReturn,
    PurchaseOrderReturnItem,
)
from app.models.refresh_token import RefreshToken

# Sales Deliveries
from app.models.sales_delivery import SalesDelivery
from app.models.sales_delivery_item import SalesDeliveryItem

# Sales Orders
from app.models.sales_order import SalesOrder
from app.models.sales_order_approver import SalesOrderApprover
from app.models.sales_order_event import SalesOrderEvent
from app.models.sales_order_item import SalesOrderItem
from app.models.sales_order_return import SalesOrderReturn, SalesOrderReturnItem
from app.models.status import Status
from app.models.subscription_plan import SubscriptionPlan

# Transfer Orders
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_approver import TransferOrderApprover
from app.models.transfer_order_event import TransferOrderEvent
from app.models.transfer_order_item import TransferOrderItem
from app.models.waitlist_signup import WaitlistSignup
from app.models.work_order import WorkOrder

# Work Orders
from app.models.work_order_assignee import WorkOrderAssignee
from app.models.work_order_completer import WorkOrderCompleter
from app.models.work_order_item import WorkOrderItem
from app.models.workspace import Workspace
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.models.workspace_invitation import WorkspaceInvitation
from app.models.workspace_member import WorkspaceMember
