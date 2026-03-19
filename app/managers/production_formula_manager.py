"""Production Formula Manager for business logic"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.managers.base_manager import BaseManager
from app.models.production_formula import ProductionFormula
from app.models.production_formula_item import ProductionFormulaItem
from app.dao.production_formula import production_formula_dao
from app.dao.production_formula_item import production_formula_item_dao
from app.dao.item import item_dao
from app.schemas.production_formula import ProductionFormulaCreate, ProductionFormulaUpdate
from app.schemas.production_formula_item import ProductionFormulaItemCreate, ProductionFormulaItemUpdate


class ProductionFormulaManager(BaseManager[ProductionFormula]):
    """
    STANDALONE MANAGER: Production formula business logic.

    Manages: ProductionFormula and ProductionFormulaItem entities
    Operations: CRUD with validation, default formula management

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    VALID_ITEM_ROLES = {'input', 'output', 'waste', 'byproduct'}

    def __init__(self):
        super().__init__(ProductionFormula)
        self.formula_dao = production_formula_dao
        self.formula_item_dao = production_formula_item_dao

    # ─── Formula CRUD ───────────────────────────────────────────────

    def create_formula(
        self,
        session: Session,
        formula_data: ProductionFormulaCreate,
        workspace_id: int,
        user_id: int
    ) -> ProductionFormula:
        """
        Create a new production formula with validation.

        Validates:
        - formula_code is unique within workspace

        If is_default=True, clears default flag on other formulas in workspace.
        """
        # Validate formula_code uniqueness within workspace
        existing = self.formula_dao.get_by_formula_code(
            session, formula_code=formula_data.formula_code, workspace_id=workspace_id
        )
        if existing:
            raise ValueError(
                f"Formula code '{formula_data.formula_code}' already exists in this workspace"
            )

        # If this is set as default, clear other defaults in workspace
        if formula_data.is_default:
            self._clear_other_defaults(session, workspace_id)

        # Build creation dict
        formula_dict = formula_data.model_dump()
        formula_dict['workspace_id'] = workspace_id
        formula_dict['created_by'] = user_id

        return self.formula_dao.create(session, obj_in=formula_dict)

    def update_formula(
        self,
        session: Session,
        formula_id: int,
        formula_data: ProductionFormulaUpdate,
        workspace_id: int,
        user_id: int
    ) -> ProductionFormula:
        """
        Update an existing production formula.

        Validates workspace ownership. If is_default is set to True,
        clears default flag on other formulas in workspace.
        """
        formula = self.formula_dao.get(session, id=formula_id)
        if not formula:
            raise ValueError(f"Production formula {formula_id} not found")
        if formula.workspace_id != workspace_id:
            raise ValueError(
                f"Production formula {formula_id} does not belong to workspace {workspace_id}"
            )

        # If setting as default, clear other defaults
        update_dict = formula_data.model_dump(exclude_unset=True)
        if update_dict.get('is_default') is True:
            self._clear_other_defaults(session, workspace_id, exclude_id=formula_id)

        update_dict['updated_by'] = user_id
        return self.formula_dao.update(session, db_obj=formula, obj_in=update_dict)

    def get_formula(
        self,
        session: Session,
        formula_id: int,
        workspace_id: int
    ) -> Optional[ProductionFormula]:
        """Get formula by ID within workspace."""
        return self.formula_dao.get_by_id_and_workspace(
            session, id=formula_id, workspace_id=workspace_id
        )

    def get_formulas(
        self,
        session: Session,
        workspace_id: int,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProductionFormula]:
        """Get formulas with optional filtering."""
        if active_only:
            return self.formula_dao.get_active_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )
        else:
            return self.formula_dao.get_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )

    def delete_formula(
        self,
        session: Session,
        formula_id: int,
        workspace_id: int
    ) -> ProductionFormula:
        """Soft delete a formula (set is_active=False)."""
        formula = self.formula_dao.get(session, id=formula_id)
        if not formula:
            raise ValueError(f"Production formula {formula_id} not found")
        if formula.workspace_id != workspace_id:
            raise ValueError(
                f"Production formula {formula_id} does not belong to workspace {workspace_id}"
            )

        return self.formula_dao.update(
            session, db_obj=formula, obj_in={'is_active': False, 'is_default': False}
        )

    # ─── Formula Item CRUD ──────────────────────────────────────────

    def add_formula_item(
        self,
        session: Session,
        item_data: ProductionFormulaItemCreate,
        workspace_id: int
    ) -> ProductionFormulaItem:
        """
        Add an item to a formula.

        Validates:
        - Formula exists and belongs to workspace
        - Item exists and belongs to workspace
        - item_role is valid
        """
        # Validate formula
        formula = self.formula_dao.get_by_id_and_workspace(
            session, id=item_data.formula_id, workspace_id=workspace_id
        )
        if not formula:
            raise ValueError(f"Production formula {item_data.formula_id} not found")

        # Validate item
        item = item_dao.get(session, id=item_data.item_id)
        if not item:
            raise ValueError(f"Item {item_data.item_id} not found")
        if item.workspace_id != workspace_id:
            raise ValueError(
                f"Item {item_data.item_id} does not belong to workspace {workspace_id}"
            )

        # Validate item_role
        if item_data.item_role not in self.VALID_ITEM_ROLES:
            raise ValueError(
                f"Invalid item_role '{item_data.item_role}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
            )

        item_dict = item_data.model_dump()
        item_dict['workspace_id'] = workspace_id

        return self.formula_item_dao.create(session, obj_in=item_dict)

    def update_formula_item(
        self,
        session: Session,
        formula_item_id: int,
        item_data: ProductionFormulaItemUpdate,
        workspace_id: int
    ) -> ProductionFormulaItem:
        """Update a formula item."""
        formula_item = self.formula_item_dao.get_by_id_and_workspace(
            session, id=formula_item_id, workspace_id=workspace_id
        )
        if not formula_item:
            raise ValueError(f"Formula item {formula_item_id} not found")

        update_dict = item_data.model_dump(exclude_unset=True)

        # Validate item_role if being updated
        if 'item_role' in update_dict and update_dict['item_role'] not in self.VALID_ITEM_ROLES:
            raise ValueError(
                f"Invalid item_role '{update_dict['item_role']}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
            )

        return self.formula_item_dao.update(session, db_obj=formula_item, obj_in=update_dict)

    def remove_formula_item(
        self,
        session: Session,
        formula_item_id: int,
        workspace_id: int
    ) -> ProductionFormulaItem:
        """Remove an item from a formula (hard delete)."""
        formula_item = self.formula_item_dao.get_by_id_and_workspace(
            session, id=formula_item_id, workspace_id=workspace_id
        )
        if not formula_item:
            raise ValueError(f"Formula item {formula_item_id} not found")

        return self.formula_item_dao.remove(session, id=formula_item_id)

    def get_formula_items(
        self,
        session: Session,
        formula_id: int,
        workspace_id: int,
        item_role: Optional[str] = None
    ) -> List[ProductionFormulaItem]:
        """Get items for a formula with optional role filter."""
        # Validate formula exists in workspace
        formula = self.formula_dao.get_by_id_and_workspace(
            session, id=formula_id, workspace_id=workspace_id
        )
        if not formula:
            raise ValueError(f"Production formula {formula_id} not found")

        if item_role:
            if item_role not in self.VALID_ITEM_ROLES:
                raise ValueError(
                    f"Invalid item_role '{item_role}'. Must be one of: {', '.join(self.VALID_ITEM_ROLES)}"
                )
            return self.formula_item_dao.get_by_formula_and_role(
                session, formula_id=formula_id, item_role=item_role, workspace_id=workspace_id
            )

        return self.formula_item_dao.get_by_formula(
            session, formula_id=formula_id, workspace_id=workspace_id
        )

    def get_formula_base_output(
        self,
        session: Session,
        formula_id: int,
        workspace_id: int
    ) -> int:
        """
        Calculate the base output quantity for a formula.

        Sums up the quantities of all 'output' role items.
        Used for scaling calculations when starting a batch.

        Returns:
            Total base output quantity (sum of all output items)

        Raises:
            ValueError: If formula has no output items defined
        """
        output_items = self.formula_item_dao.get_by_formula_and_role(
            session, formula_id=formula_id, item_role='output', workspace_id=workspace_id
        )
        if not output_items:
            raise ValueError(
                f"Formula {formula_id} has no output items defined. "
                f"Add at least one item with role='output' before using the formula."
            )
        return sum(item.quantity for item in output_items)

    # ─── Helpers ────────────────────────────────────────────────────

    def _clear_other_defaults(
        self,
        session: Session,
        workspace_id: int,
        exclude_id: Optional[int] = None
    ) -> None:
        """Clear is_default flag on all other formulas in the workspace."""
        default_formulas = self.formula_dao.get_default_formulas(
            session, workspace_id=workspace_id
        )
        for f in default_formulas:
            if exclude_id and f.id == exclude_id:
                continue
            if f.is_default:
                self.formula_dao.update(session, db_obj=f, obj_in={'is_default': False})


# Singleton instance
production_formula_manager = ProductionFormulaManager()
