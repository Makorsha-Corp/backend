"""Purchase tour sample stays out of hub lists and blocks ledger writes."""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dao.purchase_order import _apply_purchase_order_hub_filters
from app.models.purchase_order import PurchaseOrder
from app.services.purchase_tour_sample import TOUR_DESCRIPTION, reject_tour_sample_action


def test_tour_sample_routes_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/purchase-orders/tour-sample/" in paths
    assert "/api/v1/purchase-orders/tour-sample/reset/" in paths


def test_hub_list_query_excludes_tour_sample() -> None:
    engine = create_engine("sqlite://")
    session = sessionmaker(bind=engine)()
    query = _apply_purchase_order_hub_filters(session.query(PurchaseOrder), workspace_id=1)
    sql = str(query.statement.compile(dialect=engine.dialect))
    assert "is_tour_sample" in sql
    session.close()


def test_reject_tour_sample_action() -> None:
    sample = MagicMock()
    sample.is_tour_sample = True
    with pytest.raises(HTTPException) as exc:
        reject_tour_sample_action(sample, "Sample order cannot receive goods.")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Sample order cannot receive goods."

    real = MagicMock()
    real.is_tour_sample = False
    reject_tour_sample_action(real, "Sample order cannot receive goods.")


def test_template_description_is_stable() -> None:
    assert TOUR_DESCRIPTION == "Routine spares restock for ring frame section."
