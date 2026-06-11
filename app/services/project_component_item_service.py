"""Project component item service for business orchestration"""
from sqlalchemy.orm import Session
from app.dao.project_component_item import project_component_item_dao
from app.dao.project_component import project_component_dao
from app.managers.project_manager import project_manager
from app.schemas.project_component_item import ProjectComponentItemCreate, ProjectComponentItemUpdate


class ProjectComponentItemService:
    """Service for project component item workflows - handles transactions"""

    def _guard_component(self, db: Session, component_id: int, workspace_id: int, user_id: int):
        project_manager.require_component_access(db, component_id, workspace_id, user_id)

    def _filter_accessible_items(self, db: Session, items, workspace_id: int, user_id: int):
        accessible = []
        for item in items:
            component = project_component_dao.get_by_id_and_workspace(
                db, id=item.project_component_id, workspace_id=workspace_id
            )
            if not component:
                continue
            project = project_manager.project_dao.get_by_id_and_workspace(
                db, id=component.project_id, workspace_id=workspace_id
            )
            if project and project_manager.can_access_project(
                db, project, user_id, workspace_id
            ):
                accessible.append(item)
        return accessible

    def get_items(
        self,
        db: Session,
        workspace_id: int,
        user_id: int,
        project_component_id: int = None,
        skip: int = 0,
        limit: int = 100,
    ):
        if project_component_id:
            self._guard_component(db, project_component_id, workspace_id, user_id)
            return project_component_item_dao.get_by_component(
                db,
                project_component_id=project_component_id,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit,
            )

        all_items = project_component_item_dao.get_by_workspace(
            db, workspace_id=workspace_id, skip=skip, limit=limit
        )
        return self._filter_accessible_items(db, all_items, workspace_id, user_id)

    def get_by_id(self, db: Session, item_id: int, workspace_id: int, user_id: int):
        item = project_component_item_dao.get_by_id_and_workspace(
            db, id=item_id, workspace_id=workspace_id
        )
        if not item:
            return None
        self._guard_component(db, item.project_component_id, workspace_id, user_id)
        return item

    def create_component_item(
        self,
        db: Session,
        item_in: ProjectComponentItemCreate,
        workspace_id: int,
        user_id: int,
    ):
        try:
            self._guard_component(
                db, item_in.project_component_id, workspace_id, user_id
            )
            item_dict = item_in.model_dump()
            item_dict['workspace_id'] = workspace_id
            item = project_component_item_dao.create(db, obj_in=item_dict)
            project_manager.log_for_component(
                db,
                item.project_component_id,
                workspace_id,
                'item_added',
                f'Added item to component (qty {item.qty})',
                user_id,
                metadata={'item_id': item.item_id, 'qty': str(item.qty)},
            )
            db.commit()
            db.refresh(item)
            return item
        except Exception:
            db.rollback()
            raise

    def update_component_item(
        self,
        db: Session,
        item_id: int,
        item_in: ProjectComponentItemUpdate,
        workspace_id: int,
        user_id: int,
    ):
        try:
            item = self.get_by_id(db, item_id, workspace_id, user_id)
            if not item:
                return None
            item = project_component_item_dao.update(db, db_obj=item, obj_in=item_in)
            project_manager.log_for_component(
                db,
                item.project_component_id,
                workspace_id,
                'item_updated',
                f'Updated component item (qty {item.qty})',
                user_id,
                metadata={'item_id': item.item_id, 'qty': str(item.qty)},
            )
            db.commit()
            db.refresh(item)
            return item
        except Exception:
            db.rollback()
            raise

    def delete_component_item(
        self, db: Session, item_id: int, workspace_id: int, user_id: int
    ):
        try:
            item = self.get_by_id(db, item_id, workspace_id, user_id)
            if not item:
                return False
            project_manager.log_for_component(
                db,
                item.project_component_id,
                workspace_id,
                'item_removed',
                f'Removed item from component',
                user_id,
                metadata={'item_id': item.item_id},
            )
            project_component_item_dao.remove(db, id=item_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


project_component_item_service = ProjectComponentItemService()
