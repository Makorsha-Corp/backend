"""
Enum types for the database models
"""
import enum


class RoleEnum(str, enum.Enum):
    """User roles"""
    OWNER = "owner"
    FINANCE = "finance"
    GROUND_TEAM = "ground-team"
    GROUND_TEAM_MANAGER = "ground-team-manager"


class AccessControlTypeEnum(str, enum.Enum):
    """Access control types"""
    PAGE = "page"
    MANAGE_ORDER_STATUS = "manage-order-status"
    FEATURE = "feature"


class ProjectStatusEnum(str, enum.Enum):
    """Project and component status"""
    PLANNING = "PLANNING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ON_HOLD = "ON_HOLD"
    CANCELLED = "CANCELLED"


class ProjectPriorityEnum(str, enum.Enum):
    """Project priority levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TaskPriorityEnum(str, enum.Enum):
    """Task priority levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class UnstableTypeEnum(str, enum.Enum):
    """Unstable part types"""
    QUALITY_ISSUE = "QUALITY_ISSUE"
    COMPATIBILITY_ISSUE = "COMPATIBILITY_ISSUE"
    DAMAGED = "DAMAGED"
    OTHER = "OTHER"


class MachineEventTypeEnum(str, enum.Enum):
    """Machine event types"""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    OFF = "OFF"
    MAINTENANCE = "MAINTENANCE"


class MaintenanceTypeEnum(str, enum.Enum):
    """Machine maintenance types"""
    PREVENTIVE = "PREVENTIVE"
    REPAIR = "REPAIR"
    EMERGENCY = "EMERGENCY"
    INSPECTION = "INSPECTION"


class WorkTypeEnum(str, enum.Enum):
    """Work order types"""
    MAINTENANCE = "MAINTENANCE"
    INSPECTION = "INSPECTION"
    INSTALLATION = "INSTALLATION"
    REPAIR = "REPAIR"
    CALIBRATION = "CALIBRATION"
    OVERHAUL = "OVERHAUL"
    FABRICATION = "FABRICATION"
    OTHER = "OTHER"


class WorkOrderPriorityEnum(str, enum.Enum):
    """Work order priority levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class WorkOrderStatusEnum(str, enum.Enum):
    """Work order status"""
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class InventoryTypeEnum(str, enum.Enum):
    """Inventory types for the unified inventory table"""
    STORAGE = "STORAGE"
    DAMAGED = "DAMAGED"
    WASTE = "WASTE"
    SCRAP = "SCRAP"
