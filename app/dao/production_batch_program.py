"""Production batch program DAO. SECURITY: queries filter by workspace_id."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.production_batch_program import ProductionBatchProgram
from app.schemas.production_batch_program import ProductionBatchProgramCreate


class ProductionBatchProgramDAO(
    BaseDAO[ProductionBatchProgram, ProductionBatchProgramCreate, ProductionBatchProgramCreate]
):
    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionBatchProgram]:
        return (
            db.query(ProductionBatchProgram)
            .filter(
                ProductionBatchProgram.id == id,
                ProductionBatchProgram.workspace_id == workspace_id,
            )
            .first()
        )

    def get_by_factory(
        self, db: Session, *, factory_id: int, workspace_id: int
    ) -> List[ProductionBatchProgram]:
        """Programs for one factory inside this workspace."""
        return self.list_by_workspace(db, workspace_id=workspace_id, factory_id=factory_id)

    def list_by_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        factory_id: Optional[int] = None,
    ) -> List[ProductionBatchProgram]:
        """Programs in this workspace, optionally filtered to one factory."""
        query = db.query(ProductionBatchProgram).filter(
            ProductionBatchProgram.workspace_id == workspace_id,
        )
        if factory_id is not None:
            query = query.filter(ProductionBatchProgram.factory_id == factory_id)
        return query.order_by(
            ProductionBatchProgram.created_at.desc(),
            ProductionBatchProgram.id.desc(),
        ).all()


production_batch_program_dao = ProductionBatchProgramDAO(ProductionBatchProgram)
