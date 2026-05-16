"""
SQLAlchemy Base class and common imports

Import all models here to ensure they are registered with SQLAlchemy
before Alembic attempts to autogenerate migrations
"""
from app.db.base_class import Base

# Import all models here to ensure they are discovered by Alembic
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_invitation import WorkspaceInvitation
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.models.refresh_token import RefreshToken
from app.models.subscription_plan import SubscriptionPlan
from app.models.department import Department
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.item import Item
from app.models.item_tag import ItemTag
from app.models.item_tag_assignment import ItemTagAssignment
from app.models.machine_item import MachineItem
from app.models.machine_item_ledger import MachineItemLedger
from app.models.status import Status
from app.models.order_workflow import OrderWorkflow
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_part_log import OrderPartLog
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_item import ProjectComponentItem
from app.models.project_component_item_ledger import ProjectComponentItemLedger
from app.models.project_component_task import ProjectComponentTask
from app.models.miscellaneous_project_cost import MiscellaneousProjectCost
from app.models.app_settings import AppSettings
from app.models.access_control import AccessControl
from app.models.attachment import Attachment
from app.models.order_attachment import OrderAttachment
from app.models.project_attachment import ProjectAttachment
from app.models.project_component_attachment import ProjectComponentAttachment
from app.models.machine_event import MachineEvent
from app.models.machine_maintenance_log import MachineMaintenanceLog
from app.models.account import Account
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.models.account_invoice import AccountInvoice
from app.models.invoice_payment import InvoicePayment
from app.models.financial_audit_log import FinancialAuditLog
# Inventory & Products
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.product import Product
from app.models.product_ledger import ProductLedger
# Work Orders
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
# Purchase Orders
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
# Transfer Orders
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
# Expense Orders
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_item import ExpenseOrderItem
# Order Templates
from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
# Sales Orders
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
# Sales Deliveries
from app.models.sales_delivery import SalesDelivery
from app.models.sales_delivery_item import SalesDeliveryItem
# Production
from app.models.production_line import ProductionLine
from app.models.production_formula import ProductionFormula
from app.models.production_formula_item import ProductionFormulaItem
from app.models.production_batch import ProductionBatch
from app.models.production_batch_item import ProductionBatchItem
