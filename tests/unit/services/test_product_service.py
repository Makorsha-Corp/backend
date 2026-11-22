# ruff: noqa: SIM117, DTZ001
# (nested `with` blocks and naive datetimes are prescribed by the cards'
# Conventions.)
"""Unit tests for app/services/product_service.py.

Implements tests/unit/services/product_service.cases.md (revision 2,
2026-11-22), one test per card, in card order. Real Postgres session (`db`
fixture): a `commit()` only releases a savepoint, so the test's own "commit
point" and the service's commits are safe and the fixture's outer rollback
discards everything.

Patched, as Conventions name them: the commit / rollback / refresh spies and
failing variants (`patch.object(db, ...)`), and in the one `Author: claude`
card PRDS-D-05 the manager's `delete_product`. Nothing else is mocked. The
lock and order cards record the SQL with a `before_cursor_execute` listener on
`db.connection()`.

Standing rows are attributes of the namespace fixture `s` (`s.W1`, `s.F1`,
`s.I1`). `# Then N` marks the checks of the card's Then line N.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.core.exceptions import ValidationError as AppValidationError
from app.models.factory import Factory
from app.models.item import Item
from app.models.product import Product
from app.models.product_ledger import ProductLedger
from app.models.workspace import Workspace
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.product_service import ProductService, product_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = product_service
assert isinstance(svc, ProductService)

MISSING = 999999999
T0 = datetime(2026, 1, 15, 9, 0, 0)
T1 = datetime(2026, 3, 1, 9, 0, 0)
T2 = datetime(2026, 3, 1, 10, 0, 0)
T3 = datetime(2026, 3, 1, 11, 0, 0)
T4 = datetime(2026, 3, 1, 12, 0, 0)
T5 = datetime(2026, 3, 1, 13, 0, 0)

KEY_TAKEN = "Product record already exists for this item/factory/availability combination"

_BUGS = {
    640: "Ledger lists ordered by performed_at only; ties in no fixed order",
    992: "Ledger date filter with a time zone depends on the database's time-zone setting",
    1011: "Product can be created for another workspace's item",
    1336: "After a product row is soft-deleted, its key cannot be used again",
    2771: "Editing a product with no change still stamps updated_by",
    2772: "Opening a deleted product by id returns it",
    2773: "A product of a deleted factory or removed item can still be opened",
    2774: "A product holding stock can be deleted",
    2775: "Negative quantity, cost, price and minimum order accepted",
    2776: "Product cost and price with too many decimals or digits accepted",
    2777: "Product edit cannot clear cost, price, minimum order or note",
    2778: "Product average cost can change with no ledger row",
    2779: "Zero product cost records ledger total_cost as empty",
    2780: "Product can be created in a deleted factory or for a removed item",
    2781: "A taken product bucket key reaches the database as a raw unique violation",
    2793: "Finished goods can become sellable only by flipping the whole product row",
}


def xfail(n, strict=True):
    """Expect `xfail BUG-n` -> strict xfail; `(non-strict)` -> strict=False."""
    return pytest.mark.xfail(strict=strict, reason=f"BUG-{n}: {_BUGS[n]}")


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order, each flushed)
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    n = SimpleNamespace()
    n.W0 = make_workspace(db)
    n.W1 = make_workspace(db)
    n.W2 = make_workspace(db)
    n.U1 = make_profile(db)
    n.U2 = make_profile(db)  # the acting user
    n.F0 = _add(db, Factory(workspace_id=n.W0.id, name="Zero Plant", abbreviation="Z0"))
    n.F1 = _add(db, Factory(workspace_id=n.W1.id, name="Factory One", abbreviation="F1"))
    n.F2 = _add(db, Factory(workspace_id=n.W1.id, name="Factory Two", abbreviation="F2"))
    n.FD = _add(
        db,
        Factory(
            workspace_id=n.W1.id, name="Old Plant", abbreviation="OP",
            is_deleted=True, deleted_at=T0, deleted_by=n.U1.id,
        ),
    )
    n.FI = _add(
        db, Factory(workspace_id=n.W1.id, name="Idle Plant", abbreviation="IP", is_active=False)
    )
    n.F9 = _add(db, Factory(workspace_id=n.W2.id, name="Far Plant", abbreviation="F9"))

    def item(ws, name, **kw):
        return _add(
            db, Item(workspace_id=ws.id, name=name, name_normalized=name.lower(), unit="pcs", **kw)
        )

    n.I0 = item(n.W0, "Zero Nut")
    n.I1 = item(n.W1, "Bolt")
    n.I2 = item(n.W1, "Cam")
    n.IX = item(n.W1, "Old Gasket", is_active=False)
    n.I9 = item(n.W2, "Far Crate")
    return n


# Convention "stock": a products row; overrides list every differing column
def stock(db, s, **over):
    cols = {
        "workspace_id": s.W1.id, "item_id": s.I1.id, "factory_id": s.F1.id,
        "qty": 5, "created_by": s.U1.id,
    }
    cols.update(over)
    return _add(db, Product(**cols))


# Convention "for sale"
FOR_SALE = {"is_available_for_sale": True}


# Convention "deleted"
def deleted(s):
    return {"is_active": False, "is_deleted": True, "deleted_at": T0, "deleted_by": s.U1.id}


# Convention "entry": a product_ledger row
def entry(db, s, flush=True, **over):
    cols = {
        "workspace_id": s.W1.id, "factory_id": s.F1.id, "item_id": s.I1.id,
        "transaction_type": "manual_add", "quantity": 1, "qty_before": 0, "qty_after": 1,
        "performed_at": T1,
    }
    cols.update(over)
    row = ProductLedger(**cols)
    if flush:
        return _add(db, row)
    return row


# Named check "nothing written": products and product_ledger row counts, all workspaces
def counts(db):
    return (
        db.execute(select(func.count()).select_from(Product)).scalar(),
        db.execute(select(func.count()).select_from(ProductLedger)).scalar(),
    )


# Convention "commit point": the test commits; the "nothing written" snapshot is taken here
def commit_point(db):
    db.commit()
    return counts(db)


# Convention "X": a pending workspace, flushed, not committed
def mk_x(db):
    x = make_workspace(db)
    return x, x.id


# Named check "unchanged(R)": every column of R, read straight from the database
def snap(db, R_id, model=Product):
    table = model.__table__
    db.expire_all()
    row = db.execute(select(table).where(table.c.id == R_id)).mappings().one_or_none()
    return None if row is None else dict(row)


# Named check "re-read R"
def reread(db, model, rid):
    db.expire_all()
    return db.get(model, rid)


# Named check "ledger_of(F, I)"
def ledger_of(db, w1_id, f_id, i_id):
    db.expire_all()
    return list(
        db.scalars(
            select(ProductLedger)
            .where(
                ProductLedger.workspace_id == w1_id,
                ProductLedger.factory_id == f_id,
                ProductLedger.item_id == i_id,
            )
            .order_by(ProductLedger.id)
        )
    )


# count of products rows of a workspace, fresh query
def products_of(db, ws_id):
    db.expire_all()
    return list(db.scalars(select(Product).where(Product.workspace_id == ws_id)))


# count of all product_ledger rows, fresh query
def ledger_count(db):
    db.expire_all()
    return db.execute(select(func.count()).select_from(ProductLedger)).scalar()


# Named check "x_gone"
def x_gone(db, x_id):
    db.expire_all()
    return db.get(Workspace, x_id) is None


# Named check "loaded(r)"
def loaded(r):
    return inspect(r).expired_attributes.isdisjoint(
        {c.key for c in inspect(Product).column_attrs}
    )


# Named check "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# Convention "spies"
@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


# Convention "failing commit": the rollback spy is yielded
@contextmanager
def failing_commit(db):
    with (
        patch.object(db, "commit", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


# Convention "failing refresh": no rollback spy
@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        yield


# Convention "Statement recorder": before_cursor_execute on db.connection()
class Recorder:
    def __init__(self, db):
        self.conn = db.connection()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.conn, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.conn, "before_cursor_execute", self._record)
        return False

    @property
    def selects(self):
        return [st for st in self.statements if st.lstrip().upper().startswith("SELECT")]

    @property
    def psel(self):
        return [st for st in self.selects if "FROM products" in st]

    @property
    def lsel(self):
        (only,) = [st for st in self.selects if "FROM product_ledger" in st]
        return only

    @property
    def order_part(self):
        return self.lsel.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]

    @property
    def no_lock(self):
        return all("FOR UPDATE" not in st for st in self.selects)


# --------------------------------------------------------------------------- #
# ProductService.create_product
# --------------------------------------------------------------------------- #


def test_prds_c_01__create_committed_with_ledger(db, s):
    """PRDS-C-01 — a create is committed with its opening ledger row and returned re-read.
    Rules: create_product R1, Returns; TC1, TC2."""
    commit_point(db)
    w1, i1, f1, u2 = s.W1.id, s.I1.id, s.F1.id, s.U2.id

    with spies(db) as (cm, rb):
        result = svc.create_product(
            db,
            prod_in=ProductCreate(item_id=i1, factory_id=f1, qty=4, avg_cost=Decimal("12.50")),
            workspace_id=w1,
            user_id=u2,
        )

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, Product)
    assert result.id is not None
    assert result.created_at is not None
    # Then 3
    assert result.qty == 4
    assert result.created_by == u2
    # Then 4
    assert cm.call_count == 1
    # Then 5
    assert rb.call_count == 0
    rid = result.id
    db.rollback()
    # Then 6
    row = reread(db, Product, rid)
    assert row.workspace_id == w1
    assert row.item_id == i1
    assert row.factory_id == f1
    assert row.qty == 4
    assert row.avg_cost == Decimal("12.50")
    # Then 7
    led = ledger_of(db, w1, f1, i1)
    assert len(led) == 1
    # Then 8
    assert led[0].transaction_type == "manual_add"
    assert led[0].quantity == 4
    assert led[0].qty_before == 0
    assert led[0].qty_after == 4
    assert led[0].total_cost == Decimal("50.00")
    assert led[0].performed_by == u2


def test_prds_c_02__qty_zero_no_cost_no_ledger(db, s):
    """PRDS-C-02 — quantity 0 and no cost: the row is committed with no ledger row.
    Rules: create_product R1."""
    commit_point(db)

    result = svc.create_product(
        db, prod_in=ProductCreate(item_id=s.I1.id, factory_id=s.F1.id),
        workspace_id=s.W1.id, user_id=s.U2.id,
    )

    # Then 1
    assert result.id is not None
    assert result.qty == 0
    rid = result.id
    db.rollback()
    # Then 2
    row = reread(db, Product, rid)
    assert row.qty == 0
    assert row.avg_cost is None
    assert row.is_available_for_sale is False
    # Then 3
    assert ledger_count(db) == 0


def test_prds_c_03__unknown_factory_404_rolled_back(db, s):
    """PRDS-C-03 — an unknown factory: the 404 passes unchanged and the session is rolled back.
    Rules: create_product R2, Errors row 1; TC3."""
    before = commit_point(db)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.create_product(
                db, prod_in=ProductCreate(item_id=s.I1.id, factory_id=MISSING, qty=3),
                workspace_id=s.W1.id, user_id=s.U2.id,
            )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert counts(db) == before
    # Then 7
    assert usable(db)


def test_prds_c_04__live_key_409_rolled_back(db, s):
    """PRDS-C-04 — a live row of the key: the 409 passes unchanged and the session is rolled back.
    Rules: create_product R2, Errors row 3; TC3."""
    p = stock(db, s, **FOR_SALE, qty=9)
    before = commit_point(db)
    p_before = snap(db, p.id)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_product(
            db,
            prod_in=ProductCreate(
                item_id=s.I1.id, factory_id=s.F1.id, qty=3, is_available_for_sale=True
            ),
            workspace_id=s.W1.id, user_id=s.U2.id,
        )
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == KEY_TAKEN
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap(db, p_before["id"]) == p_before
    # Then 6
    assert usable(db)


def test_prds_c_05__unknown_item_nothing_saved(db, s):
    """PRDS-C-05 — an unknown item: whatever is raised, nothing is saved and the session is rolled back.
    Rules: create_product R2; TC3."""
    before = commit_point(db)
    i_missing, f1, w1, u2 = MISSING, s.F1.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises((IntegrityError, HTTPException)) as exc:
        svc.create_product(
            db, prod_in=ProductCreate(item_id=i_missing, factory_id=f1, qty=3),
            workspace_id=w1, user_id=u2,
        )
    assert isinstance(exc.value, (IntegrityError, HTTPException))
    # Then 2
    assert x_gone(db, x_id)
    # Then 3
    assert counts(db) == before
    # Then 4
    assert usable(db)


@xfail(1011)
def test_prds_c_06__unknown_item_404(db, s):
    """PRDS-C-06 — pass-through BUG-1011: an unknown item gets the 404.
    Rules: create_product R2 [BUG-1011]."""
    before = commit_point(db)
    f1, w1, u2 = s.F1.id, s.W1.id, s.U2.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_product(
            db, prod_in=ProductCreate(item_id=MISSING, factory_id=f1, qty=3),
            workspace_id=w1, user_id=u2,
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Item with ID 999999999 not found"
    # Then 3
    assert counts(db) == before


def test_prds_c_07__deleted_key_nothing_saved(db, s):
    """PRDS-C-07 — a soft-deleted row of the key: whatever is raised, nothing is saved, rolled back.
    Rules: create_product R2; TC3."""
    p = stock(db, s, **deleted(s), qty=0)
    before = commit_point(db)
    p_before = snap(db, p.id)
    i1, f1, w1, u2 = s.I1.id, s.F1.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises((IntegrityError, HTTPException)) as exc:
        svc.create_product(
            db, prod_in=ProductCreate(item_id=i1, factory_id=f1, qty=3),
            workspace_id=w1, user_id=u2,
        )
    assert isinstance(exc.value, (IntegrityError, HTTPException))
    # Then 2
    assert x_gone(db, x_id)
    # Then 3
    assert counts(db) == before
    # Then 4
    assert snap(db, p_before["id"]) == p_before
    # Then 5
    assert usable(db)


@xfail(1336)
def test_prds_c_08__deleted_key_409(db, s):
    """PRDS-C-08 — pass-through BUG-1336: a soft-deleted row of the key gets the 409.
    Rules: create_product R2 [BUG-1336]."""
    stock(db, s, **deleted(s), qty=0)
    before = commit_point(db)
    i1, f1, w1, u2 = s.I1.id, s.F1.id, s.W1.id, s.U2.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_product(
            db, prod_in=ProductCreate(item_id=i1, factory_id=f1, qty=3),
            workspace_id=w1, user_id=u2,
        )
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == KEY_TAKEN
    # Then 3
    assert counts(db) == before


@xfail(2780)
def test_prds_c_09__deleted_factory_404(db, s):
    """PRDS-C-09 — pass-through BUG-2780: a soft-deleted factory gets the 404.
    Rules: create_product R2 [BUG-2780]."""
    before = commit_point(db)
    fd = s.FD.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_product(
            db, prod_in=ProductCreate(item_id=s.I1.id, factory_id=fd, qty=3),
            workspace_id=s.W1.id, user_id=s.U2.id,
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory with ID {fd} not found"
    # Then 3
    assert counts(db) == before


def test_prds_c_10__inactive_live_factory_accepted(db, s):
    """PRDS-C-10 — an inactive but live factory is accepted and committed.
    Rules: create_product R1 (BUG-2780 companion)."""
    commit_point(db)
    fi, i1, w1 = s.FI.id, s.I1.id, s.W1.id

    result = svc.create_product(
        db, prod_in=ProductCreate(item_id=i1, factory_id=fi, qty=2),
        workspace_id=w1, user_id=s.U2.id,
    )

    # Then 1
    assert result.factory_id == fi
    rid = result.id
    db.rollback()
    # Then 2
    row = reread(db, Product, rid)
    assert row.factory_id == fi
    assert row.qty == 2
    # Then 3
    assert len(ledger_of(db, w1, fi, i1)) == 1


@xfail(2779)
def test_prds_c_11__zero_cost_total_zero(db, s):
    """PRDS-C-11 — pass-through BUG-2779: a zero cost gives a ledger total of 0.00.
    Rules: create_product R1 [BUG-2779]."""
    commit_point(db)
    w1, f1, i1 = s.W1.id, s.F1.id, s.I1.id

    result = svc.create_product(
        db, prod_in=ProductCreate(item_id=i1, factory_id=f1, qty=5, avg_cost=Decimal("0.00")),
        workspace_id=w1, user_id=s.U2.id,
    )

    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    led = ledger_of(db, w1, f1, i1)
    assert len(led) == 1
    # Then 3
    assert led[0].total_cost == Decimal("0.00")


def test_prds_c_12__zero_cost_ledger_unit_cost(db, s):
    """PRDS-C-12 — a zero cost: the opening ledger row is committed with the zero unit cost.
    Rules: create_product R1 (BUG-2779 companion)."""
    commit_point(db)
    w1, f1, i1 = s.W1.id, s.F1.id, s.I1.id

    result = svc.create_product(
        db, prod_in=ProductCreate(item_id=i1, factory_id=f1, qty=5, avg_cost=Decimal("0.00")),
        workspace_id=w1, user_id=s.U2.id,
    )

    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    led = ledger_of(db, w1, f1, i1)
    assert len(led) == 1
    # Then 3
    assert led[0].quantity == 5
    assert led[0].unit_cost == Decimal("0.00")
    assert led[0].avg_cost_after == Decimal("0.00")


@xfail(2778)
def test_prds_c_13__qty_zero_cost_writes_ledger(db, s):
    """PRDS-C-13 — pass-through BUG-2778: quantity 0 with a cost writes a zero-quantity ledger row.
    Rules: create_product R1 [BUG-2778]."""
    commit_point(db)
    w1, f1, i1 = s.W1.id, s.F1.id, s.I1.id

    result = svc.create_product(
        db, prod_in=ProductCreate(item_id=i1, factory_id=f1, qty=0, avg_cost=Decimal("7.00")),
        workspace_id=w1, user_id=s.U2.id,
    )

    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    led = ledger_of(db, w1, f1, i1)
    assert len(led) == 1
    # Then 3
    assert led[0].transaction_type == "manual_add"
    assert led[0].quantity == 0
    assert led[0].avg_cost_after == Decimal("7.00")
    assert led[0].total_cost == Decimal("0.00")


def test_prds_c_14__qty_zero_cost_stored(db, s):
    """PRDS-C-14 — quantity 0 with a cost: the row is committed with its cost.
    Rules: create_product R1 (BUG-2778 companion)."""
    commit_point(db)

    result = svc.create_product(
        db, prod_in=ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, qty=0, avg_cost=Decimal("7.00")),
        workspace_id=s.W1.id, user_id=s.U2.id,
    )

    # Then 1
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 2
    row = reread(db, Product, rid)
    assert row.qty == 0
    assert row.avg_cost == Decimal("7.00")


@xfail(2775)
def test_prds_c_15__negative_qty_refused_by_schema(db, s):
    """PRDS-C-15 — pass-through BUG-2775: a negative quantity is refused by the schema, nothing saved.
    Rules: create_product R2 [BUG-2775]."""
    before = commit_point(db)

    # Then 1
    with pytest.raises(PydanticValidationError) as exc:
        svc.create_product(
            db, prod_in=ProductCreate(item_id=s.I1.id, factory_id=s.F1.id, qty=-5),
            workspace_id=s.W1.id, user_id=s.U2.id,
        )
    assert exc.type is PydanticValidationError
    # Then 2
    assert counts(db) == before


@xfail(2776)
def test_prds_c_16__three_decimals_refused_by_schema(db, s):
    """PRDS-C-16 — pass-through BUG-2776: a cost with three decimals is refused by the schema.
    Rules: create_product R2 [BUG-2776]."""
    before = commit_point(db)

    # Then 1
    with pytest.raises(PydanticValidationError) as exc:
        svc.create_product(
            db,
            prod_in=ProductCreate(
                item_id=s.I1.id, factory_id=s.F1.id, qty=3, avg_cost=Decimal("10.005")
            ),
            workspace_id=s.W1.id, user_id=s.U2.id,
        )
    assert exc.type is PydanticValidationError
    # Then 2
    assert counts(db) == before


def test_prds_c_17__failing_commit_discards_all(db, s):
    """PRDS-C-17 — a failing commit discards the row, its ledger row and the extra row.
    Rules: create_product R1; TC4."""
    commit_point(db)
    w1, f1, i1, u2 = s.W1.id, s.F1.id, s.I1.id, s.U2.id
    data = ProductCreate(item_id=i1, factory_id=f1, qty=4, avg_cost=Decimal("12.50"))
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_product(db, prod_in=data, workspace_id=w1, user_id=u2)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert len(products_of(db, w1)) == 0
    # Then 4
    assert len(ledger_of(db, w1, f1, i1)) == 0
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert usable(db)


def test_prds_c_18__failing_refresh_keeps_saved(db, s):
    """PRDS-C-18 — a failing re-read after the commit leaves the row and its ledger row saved.
    Rules: create_product R1; TC5."""
    commit_point(db)
    w1, f1, i1, u2 = s.W1.id, s.F1.id, s.I1.id, s.U2.id
    data = ProductCreate(item_id=i1, factory_id=f1, qty=4, avg_cost=Decimal("12.50"))

    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_product(db, prod_in=data, workspace_id=w1, user_id=u2)
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    rows = products_of(db, w1)
    assert len(rows) == 1
    assert rows[0].qty == 4
    # Then 3
    assert len(ledger_of(db, w1, f1, i1)) == 1


# --------------------------------------------------------------------------- #
# ProductService.update_product
# --------------------------------------------------------------------------- #


def test_prds_u_01__qty_change_committed_with_adjustment(db, s):
    """PRDS-U-01 — a quantity change is committed with its adjustment row and returned re-read.
    Rules: update_product R1, Returns; TC1, TC2."""
    p = stock(db, s, avg_cost=Decimal("10.00"))
    commit_point(db)
    pid, w1, f1, i1, u2 = p.id, s.W1.id, s.F1.id, s.I1.id, s.U2.id

    with spies(db) as (cm, rb):
        result = svc.update_product(
            db, prod_id=pid, prod_in=ProductUpdate(qty=8), workspace_id=w1, user_id=u2
        )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == pid
    assert result.qty == 8
    assert result.updated_at is not None
    # Then 3
    assert cm.call_count == 1
    # Then 4
    assert rb.call_count == 0
    db.rollback()
    # Then 5
    row = reread(db, Product, pid)
    assert row.qty == 8
    assert row.updated_by == u2
    assert row.avg_cost == Decimal("10.00")
    # Then 6
    led = ledger_of(db, w1, f1, i1)
    assert len(led) == 1
    # Then 7
    assert led[0].transaction_type == "inventory_adjustment"
    assert led[0].quantity == 3
    assert led[0].qty_before == 5
    assert led[0].qty_after == 8
    assert led[0].notes == "Quantity adjusted from 5 to 8"


def test_prds_u_02__price_change_no_ledger(db, s):
    """PRDS-U-02 — a price change is committed with no ledger row; omitted fields are kept.
    Rules: update_product R1."""
    p = stock(db, s, note="Keep")
    commit_point(db)
    pid, u2 = p.id, s.U2.id

    result = svc.update_product(
        db, prod_id=pid, prod_in=ProductUpdate(selling_price=Decimal("20.00")),
        workspace_id=s.W1.id, user_id=u2,
    )

    # Then 1
    assert result.id == pid
    db.rollback()
    # Then 2
    row = reread(db, Product, pid)
    assert row.selling_price == Decimal("20.00")
    assert row.updated_by == u2
    # Then 3
    row = reread(db, Product, pid)
    assert row.note == "Keep"
    assert row.qty == 5
    # Then 4
    assert ledger_count(db) == 0


def test_prds_u_03__other_workspace_404_rolled_back(db, s):
    """PRDS-U-03 — a row of another workspace: the 404 passes unchanged and the session is rolled back.
    Rules: update_product R2, Errors row 1; TC3."""
    z = stock(db, s, workspace_id=s.W2.id, item_id=s.I9.id, factory_id=s.F9.id)
    before = commit_point(db)
    z_before = snap(db, z.id)
    zid, w1, u2 = z.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.update_product(
                db, prod_id=zid, prod_in=ProductUpdate(qty=8), workspace_id=w1, user_id=u2
            )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Product record with ID {zid} not found"
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert snap(db, zid) == z_before
    # Then 7
    assert counts(db) == before


def test_prds_u_04__deleted_row_400_rolled_back(db, s):
    """PRDS-U-04 — a soft-deleted row: the 400 passes unchanged and the session is rolled back.
    Rules: update_product R2, Errors row 2; TC3."""
    p = stock(db, s, **deleted(s))
    before = commit_point(db)
    p_before = snap(db, p.id)
    pid, w1, u2 = p.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_product(
            db, prod_id=pid, prod_in=ProductUpdate(qty=8), workspace_id=w1, user_id=u2
        )
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot update a deleted product record"
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, pid) == p_before
    # Then 5
    assert counts(db) == before
    # Then 6
    assert usable(db)


@xfail(2793)
def test_prds_u_05__flip_with_stock_refused(db, s):
    """PRDS-U-05 — pass-through BUG-2793: flipping a row that holds stock is refused and rolled back.
    Rules: update_product R2 [BUG-2793]; TC3."""
    p = stock(db, s, avg_cost=Decimal("10.00"))
    before = commit_point(db)
    p_before = snap(db, p.id)
    pid, w1, u2 = p.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_product(
            db, prod_id=pid, prod_in=ProductUpdate(is_available_for_sale=True),
            workspace_id=w1, user_id=u2,
        )
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Product record holds stock — use Make sellable to move units"
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, pid) == p_before
    # Then 5
    assert counts(db) == before


def test_prds_u_06__row_at_zero_flips(db, s):
    """PRDS-U-06 — a row at 0 flips to for sale and is committed.
    Rules: update_product R1 (BUG-2793 companion)."""
    p = stock(db, s, qty=0, avg_cost=Decimal("10.00"))
    commit_point(db)
    pid = p.id

    result = svc.update_product(
        db, prod_id=pid, prod_in=ProductUpdate(is_available_for_sale=True),
        workspace_id=s.W1.id, user_id=s.U2.id,
    )

    # Then 1
    assert result.id == pid
    db.rollback()
    # Then 2
    row = reread(db, Product, pid)
    assert row.is_available_for_sale is True
    assert row.qty == 0
    assert row.avg_cost == Decimal("10.00")
    # Then 3
    assert ledger_count(db) == 0


def test_prds_u_07__flip_onto_taken_key_nothing_saved(db, s):
    """PRDS-U-07 — a flip at 0 onto a taken key: whatever is raised, nothing is saved, rolled back.
    Rules: update_product R2; TC3."""
    ps = stock(db, s, **FOR_SALE, qty=30)
    p = stock(db, s, qty=0)
    before = commit_point(db)
    p_before, ps_before = snap(db, p.id), snap(db, ps.id)
    pid, psid, w1, u2 = p.id, ps.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises((IntegrityError, HTTPException)) as exc:
        svc.update_product(
            db, prod_id=pid, prod_in=ProductUpdate(is_available_for_sale=True),
            workspace_id=w1, user_id=u2,
        )
    assert isinstance(exc.value, (IntegrityError, HTTPException))
    # Then 2
    assert x_gone(db, x_id)
    # Then 3
    assert snap(db, pid) == p_before
    # Then 4
    assert snap(db, psid) == ps_before
    # Then 5
    assert counts(db) == before
    # Then 6
    assert usable(db)


@xfail(2781)
def test_prds_u_08__flip_onto_taken_key_409(db, s):
    """PRDS-U-08 — pass-through BUG-2781: a flip at 0 onto a taken key gets the 409.
    Rules: update_product R2 [BUG-2781]."""
    stock(db, s, **FOR_SALE, qty=30)
    p = stock(db, s, qty=0)
    commit_point(db)
    p_before = snap(db, p.id)
    pid, w1, u2 = p.id, s.W1.id, s.U2.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_product(
            db, prod_id=pid, prod_in=ProductUpdate(is_available_for_sale=True),
            workspace_id=w1, user_id=u2,
        )
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == KEY_TAKEN
    # Then 3
    assert snap(db, pid) == p_before


@xfail(2771)
def test_prds_u_09__empty_update_no_stamp(db, s):
    """PRDS-U-09 — pass-through BUG-2771: an empty update does not stamp updated_by.
    Rules: update_product R1 [BUG-2771]; HR-9."""
    p = stock(db, s)
    commit_point(db)
    pid = p.id

    result = svc.update_product(
        db, prod_id=pid, prod_in=ProductUpdate(), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == pid
    db.rollback()
    # Then 2
    assert reread(db, Product, pid).updated_by is None


def test_prds_u_10__empty_update_still_commits(db, s):
    """PRDS-U-10 — an empty update still commits and writes no ledger row.
    Rules: update_product R1 (BUG-2771 companion)."""
    p = stock(db, s)
    commit_point(db)
    pid = p.id

    with spies(db) as (cm, _rb):
        result = svc.update_product(
            db, prod_id=pid, prod_in=ProductUpdate(), workspace_id=s.W1.id, user_id=s.U2.id
        )

    # Then 1
    assert result.id == pid
    assert result.qty == 5
    # Then 2
    assert cm.call_count == 1
    db.rollback()
    # Then 3
    row = reread(db, Product, pid)
    assert row.qty == 5
    assert row.is_available_for_sale is False
    # Then 4
    assert ledger_count(db) == 0


@xfail(2777)
def test_prds_u_11__explicit_null_clears_price(db, s):
    """PRDS-U-11 — pass-through BUG-2777: an explicit null clears the selling price.
    Rules: update_product R1 [BUG-2777]."""
    p = stock(db, s, selling_price=Decimal("20.00"))
    commit_point(db)
    pid = p.id

    result = svc.update_product(
        db, prod_id=pid, prod_in=ProductUpdate(selling_price=None),
        workspace_id=s.W1.id, user_id=s.U2.id,
    )

    # Then 1
    assert result.id == pid
    db.rollback()
    # Then 2
    assert reread(db, Product, pid).selling_price is None


@xfail(2778)
def test_prds_u_12__cost_only_change_writes_ledger(db, s):
    """PRDS-U-12 — pass-through BUG-2778: a cost-only change writes a zero-quantity adjustment row.
    Rules: update_product R1 [BUG-2778]."""
    p = stock(db, s, avg_cost=Decimal("10.00"))
    commit_point(db)
    pid, w1, f1, i1 = p.id, s.W1.id, s.F1.id, s.I1.id

    result = svc.update_product(
        db, prod_id=pid, prod_in=ProductUpdate(avg_cost=Decimal("12.00")),
        workspace_id=w1, user_id=s.U2.id,
    )

    # Then 1
    assert result.id == pid
    db.rollback()
    # Then 2
    led = ledger_of(db, w1, f1, i1)
    assert len(led) == 1
    # Then 3
    assert led[0].transaction_type == "inventory_adjustment"
    assert led[0].quantity == 0
    assert led[0].qty_before == 5
    assert led[0].qty_after == 5
    assert led[0].avg_cost_before == Decimal("10.00")
    assert led[0].avg_cost_after == Decimal("12.00")


def test_prds_u_13__cost_only_change_stored(db, s):
    """PRDS-U-13 — a cost-only change is committed on the row.
    Rules: update_product R1 (BUG-2778 companion)."""
    p = stock(db, s, avg_cost=Decimal("10.00"))
    commit_point(db)
    pid, u2 = p.id, s.U2.id

    result = svc.update_product(
        db, prod_id=pid, prod_in=ProductUpdate(avg_cost=Decimal("12.00")),
        workspace_id=s.W1.id, user_id=u2,
    )

    # Then 1
    assert result.id == pid
    db.rollback()
    # Then 2
    row = reread(db, Product, pid)
    assert row.avg_cost == Decimal("12.00")
    assert row.qty == 5
    assert row.updated_by == u2


@xfail(2779)
def test_prds_u_14__adjustment_at_zero_cost_total_zero(db, s):
    """PRDS-U-14 — pass-through BUG-2779: an adjustment at cost 0 totals 0.00.
    Rules: update_product R1 [BUG-2779]."""
    p = stock(db, s, avg_cost=Decimal("0.00"))
    commit_point(db)
    pid, w1, f1, i1 = p.id, s.W1.id, s.F1.id, s.I1.id

    result = svc.update_product(
        db, prod_id=pid, prod_in=ProductUpdate(qty=8), workspace_id=w1, user_id=s.U2.id
    )

    # Then 1
    assert result.qty == 8
    db.rollback()
    # Then 2
    led = ledger_of(db, w1, f1, i1)
    assert len(led) == 1
    # Then 3
    assert led[0].total_cost == Decimal("0.00")


def test_prds_u_15__adjustment_at_zero_cost_unit_cost(db, s):
    """PRDS-U-15 — an adjustment at cost 0 is committed with the zero unit cost.
    Rules: update_product R1 (BUG-2779 companion)."""
    p = stock(db, s, avg_cost=Decimal("0.00"))
    commit_point(db)
    pid, w1, f1, i1 = p.id, s.W1.id, s.F1.id, s.I1.id

    result = svc.update_product(
        db, prod_id=pid, prod_in=ProductUpdate(qty=8), workspace_id=w1, user_id=s.U2.id
    )

    # Then 1
    assert result.qty == 8
    db.rollback()
    # Then 2
    led = ledger_of(db, w1, f1, i1)
    assert len(led) == 1
    # Then 3
    assert led[0].quantity == 3
    assert led[0].unit_cost == Decimal("0.00")


@xfail(2775)
def test_prds_u_16__negative_qty_refused_by_schema(db, s):
    """PRDS-U-16 — pass-through BUG-2775: a negative quantity is refused by the schema, nothing saved.
    Rules: update_product R2 [BUG-2775]."""
    p = stock(db, s)
    before = commit_point(db)
    p_before = snap(db, p.id)
    pid, w1, u2 = p.id, s.W1.id, s.U2.id

    # Then 1
    with pytest.raises(PydanticValidationError) as exc:
        svc.update_product(
            db, prod_id=pid, prod_in=ProductUpdate(qty=-1), workspace_id=w1, user_id=u2
        )
    assert exc.type is PydanticValidationError
    # Then 2
    assert snap(db, pid) == p_before
    # Then 3
    assert counts(db) == before


def test_prds_u_17__failing_commit_discards_change(db, s):
    """PRDS-U-17 — a failing commit discards the change, its adjustment row and the extra row.
    Rules: update_product R1; TC4."""
    p = stock(db, s, avg_cost=Decimal("10.00"))
    commit_point(db)
    pid, w1, u2 = p.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_product(
                db, prod_id=pid, prod_in=ProductUpdate(qty=8), workspace_id=w1, user_id=u2
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, Product, pid)
    assert row.qty == 5
    assert row.updated_by is None
    # Then 4
    assert ledger_count(db) == 0
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert usable(db)


# --------------------------------------------------------------------------- #
# ProductService.get_product
# --------------------------------------------------------------------------- #


def test_prds_g_01__live_row_returned(db, s):
    """PRDS-G-01 — the workspace's live row is returned.
    Rules: get_product R1."""
    stock(db, s, workspace_id=s.W0.id, item_id=s.I0.id, factory_id=s.F0.id)
    p = stock(db, s)
    stock(db, s, workspace_id=s.W2.id, item_id=s.I9.id, factory_id=s.F9.id)
    commit_point(db)

    result = svc.get_product(db, prod_id=p.id, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, Product)
    # Then 2
    assert result.id == p.id
    assert result.workspace_id == s.W1.id
    assert result.qty == 5


def test_prds_g_02__row_of_w0_404(db, s):
    """PRDS-G-02 — a row of W0 (lower id) gets the 404.
    Rules: get_product R1, Errors."""
    z0 = stock(db, s, workspace_id=s.W0.id, item_id=s.I0.id, factory_id=s.F0.id)
    stock(db, s)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_product(db, prod_id=z0.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Product record with ID {z0.id} not found"


def test_prds_g_03__row_of_w2_404(db, s):
    """PRDS-G-03 — a row of W2 (higher id) gets the 404.
    Rules: get_product R1, Errors."""
    stock(db, s)
    z2 = stock(db, s, workspace_id=s.W2.id, item_id=s.I9.id, factory_id=s.F9.id)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_product(db, prod_id=z2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Product record with ID {z2.id} not found"


@xfail(2772)
def test_prds_g_04__deleted_row_not_found(db, s):
    """PRDS-G-04 — pass-through BUG-2772: a soft-deleted row is not found by default.
    Rules: get_product R2 [BUG-2772]."""
    p = stock(db, s, **deleted(s))
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_product(db, prod_id=p.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Product record with ID {p.id} not found"


@xfail(2772)
def test_prds_g_05__include_deleted_returns_row(db, s):
    """PRDS-G-05 — BUG-2772: include_deleted=True returns a soft-deleted row.
    Rules: get_product Inputs, R2 [BUG-2772]."""
    p = stock(db, s, **deleted(s))
    commit_point(db)

    result = svc.get_product(db, prod_id=p.id, workspace_id=s.W1.id, include_deleted=True)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert result.is_deleted is True


@xfail(2772)
def test_prds_g_06__include_deleted_stays_in_workspace(db, s):
    """PRDS-G-06 — BUG-2772: include_deleted=True does not reach another workspace.
    Rules: get_product R1, R2 [BUG-2772]."""
    z2 = stock(db, s, workspace_id=s.W2.id, item_id=s.I9.id, factory_id=s.F9.id, **deleted(s))
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_product(db, prod_id=z2.id, workspace_id=s.W1.id, include_deleted=True)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Product record with ID {z2.id} not found"


@xfail(2773)
def test_prds_g_07__deleted_factory_row_not_found(db, s):
    """PRDS-G-07 — pass-through BUG-2773: a row of a soft-deleted factory is not found by default.
    Rules: get_product R2 [BUG-2773]."""
    p = stock(db, s, factory_id=s.FD.id)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_product(db, prod_id=p.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Product record with ID {p.id} not found"


@xfail(2773)
def test_prds_g_08__removed_item_row_not_found(db, s):
    """PRDS-G-08 — pass-through BUG-2773: a row of a removed item is not found by default.
    Rules: get_product R2 [BUG-2773]."""
    p = stock(db, s, item_id=s.IX.id)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_product(db, prod_id=p.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Product record with ID {p.id} not found"


def test_prds_g_09__inactive_live_factory_row_returned(db, s):
    """PRDS-G-09 — a row of an inactive but live factory is returned.
    Rules: get_product R1 (BUG-2773 companion)."""
    p = stock(db, s, factory_id=s.FI.id)
    commit_point(db)

    result = svc.get_product(db, prod_id=p.id, workspace_id=s.W1.id)

    # Then 1
    assert result.id == p.id
    assert result.factory_id == s.FI.id


def test_prds_g_10__read_no_commit_no_lock(db, s):
    """PRDS-G-10 — the read neither commits nor rolls back, and takes no lock.
    Rules: get_product R1; TC6."""
    p = stock(db, s)
    b = stock(db, s, item_id=s.I2.id, note="Old")
    commit_point(db)
    pid, bid, w1 = p.id, b.id, s.W1.id
    _, x_id = mk_x(db)
    n = Product(
        workspace_id=w1, item_id=s.I2.id, factory_id=s.F2.id, qty=5, created_by=s.U1.id
    )
    db.add(n)
    b.note = "Edited"

    with Recorder(db) as rec:
        with spies(db) as (cm, rb):
            result = svc.get_product(db, prod_id=pid, workspace_id=w1)

    # Then 1
    assert result.id == pid
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert n in db.new
    assert len(db.new) == 1
    # Then 5
    assert b in db.dirty
    assert len(db.dirty) == 1
    # Then 6
    assert rec.no_lock
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)
    # Then 8
    assert reread(db, Product, bid).note == "Old"


def test_prds_g_11__raising_read_no_rollback(db, s):
    """PRDS-G-11 — a read that raises the 404 does not roll back.
    Rules: get_product R1, Errors; TC6."""
    stock(db, s)
    commit_point(db)
    x, _ = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.get_product(db, prod_id=MISSING, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Product record with ID 999999999 not found"
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert x in db


# --------------------------------------------------------------------------- #
# ProductService.list_products
# --------------------------------------------------------------------------- #


def test_prds_l_01__defaults_live_rows_of_workspace(db, s):
    """PRDS-L-01 — the defaults return the workspace's live rows only (compared as a set).
    Rules: list_products R1."""
    stock(db, s, workspace_id=s.W0.id, item_id=s.I0.id, factory_id=s.F0.id)
    a = stock(db, s)
    stock(db, s, item_id=s.I2.id, **deleted(s))
    b = stock(db, s, **FOR_SALE)
    stock(db, s, workspace_id=s.W2.id, item_id=s.I9.id, factory_id=s.F9.id)
    commit_point(db)

    result = svc.list_products(db, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert {r.id for r in result} == {a.id, b.id}


def test_prds_l_02__factory_filter(db, s):
    """PRDS-L-02 — the factory filter is passed on.
    Rules: list_products R1."""
    stock(db, s)
    b = stock(db, s, factory_id=s.F2.id)
    c = stock(db, s, item_id=s.I2.id, factory_id=s.F2.id)
    commit_point(db)

    result = svc.list_products(db, workspace_id=s.W1.id, factory_id=s.F2.id)

    # Then 1
    assert {r.id for r in result} == {b.id, c.id}


def test_prds_l_03__for_sale_false_filters(db, s):
    """PRDS-L-03 — is_available_for_sale=False filters (not "no filter").
    Rules: list_products R1."""
    a = stock(db, s)
    stock(db, s, **FOR_SALE)
    c = stock(db, s, item_id=s.I2.id)
    commit_point(db)

    result = svc.list_products(db, workspace_id=s.W1.id, is_available_for_sale=False)

    # Then 1
    assert {r.id for r in result} == {a.id, c.id}


def test_prds_l_04__for_sale_true_filters(db, s):
    """PRDS-L-04 — is_available_for_sale=True returns only for-sale rows.
    Rules: list_products R1."""
    stock(db, s)
    b = stock(db, s, **FOR_SALE)
    stock(db, s, item_id=s.I2.id)
    commit_point(db)

    result = svc.list_products(db, workspace_id=s.W1.id, is_available_for_sale=True)

    # Then 1
    assert {r.id for r in result} == {b.id}


def test_prds_l_05__default_limit_100(db, s):
    """PRDS-L-05 — with the defaults 101 live rows give 100 distinct ones.
    Rules: list_products R1."""
    items = [
        Item(workspace_id=s.W1.id, name=f"Part {k:03d}", name_normalized=f"part {k:03d}", unit="pcs")
        for k in range(1, 102)
    ]
    db.add_all(items)
    db.flush()
    rows = [
        Product(workspace_id=s.W1.id, item_id=it.id, factory_id=s.F1.id, qty=5, created_by=s.U1.id)
        for it in items
    ]
    db.add_all(rows)
    db.flush()
    all_ids = {r.id for r in rows}
    commit_point(db)

    result = svc.list_products(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len({r.id for r in result}) == 100
    assert {r.id for r in result} <= all_ids


def _five_rows(db, s):
    a = stock(db, s)
    b = stock(db, s, **FOR_SALE)
    c = stock(db, s, item_id=s.I2.id)
    d = stock(db, s, item_id=s.I2.id, **FOR_SALE)
    e = stock(db, s, factory_id=s.F2.id)
    return a, b, c, d, e


def test_prds_l_06__skip_and_limit(db, s):
    """PRDS-L-06 — skip and limit are passed on: 5 rows, skip=1, limit=2 give 2 of them.
    Rules: list_products R1."""
    rows = _five_rows(db, s)
    commit_point(db)

    result = svc.list_products(db, workspace_id=s.W1.id, skip=1, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert len({r.id for r in result}) == 2
    assert {r.id for r in result} <= {r.id for r in rows}


def test_prds_l_07__skip_four_large_limit(db, s):
    """PRDS-L-07 — skip=4 with limit=1000 gives the one remaining row.
    Rules: list_products R1."""
    rows = _five_rows(db, s)
    commit_point(db)

    result = svc.list_products(db, workspace_id=s.W1.id, skip=4, limit=1000)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {r.id for r in rows}


def test_prds_l_08__list_no_commit_no_lock(db, s):
    """PRDS-L-08 — the list neither commits nor rolls back, and takes no lock.
    Rules: list_products R1; TC6."""
    a = stock(db, s)
    b = stock(db, s, workspace_id=s.W2.id, item_id=s.I9.id, factory_id=s.F9.id, note="Old")
    commit_point(db)
    aid, bid, w1 = a.id, b.id, s.W1.id
    _, x_id = mk_x(db)
    n = Product(
        workspace_id=w1, item_id=s.I2.id, factory_id=s.F2.id, qty=5, created_by=s.U1.id
    )
    db.add(n)
    b.note = "Edited"

    with Recorder(db) as rec:
        with spies(db) as (cm, rb):
            result = svc.list_products(db, workspace_id=w1)

    # Then 1
    assert {r.id for r in result} == {aid}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert n in db.new
    assert len(db.new) == 1
    # Then 5
    assert b in db.dirty
    assert len(db.dirty) == 1
    # Then 6
    assert rec.no_lock
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)
    # Then 8
    assert reread(db, Product, bid).note == "Old"


# --------------------------------------------------------------------------- #
# ProductService.delete_product
# --------------------------------------------------------------------------- #


def test_prds_d_01__row_at_zero_soft_deleted(db, s):
    """PRDS-D-01 — a row at 0 is soft-deleted, committed and returned re-read.
    Rules: delete_product R1, Returns; TC1, TC2."""
    p = stock(db, s, qty=0, avg_cost=Decimal("10.00"))
    commit_point(db)
    pid, u2 = p.id, s.U2.id

    with spies(db) as (cm, rb):
        result = svc.delete_product(db, prod_id=pid, workspace_id=s.W1.id, user_id=u2)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == pid
    assert result.is_deleted is True
    assert result.deleted_by == u2
    assert result.deleted_at is not None
    # Then 3
    assert cm.call_count == 1
    # Then 4
    assert rb.call_count == 0
    db.rollback()
    # Then 5
    row = reread(db, Product, pid)
    assert row.is_deleted is True
    assert row.is_active is False
    assert row.deleted_by == u2
    assert row.deleted_at is not None
    # Then 6
    row = reread(db, Product, pid)
    assert row.qty == 0
    assert row.avg_cost == Decimal("10.00")
    assert row.updated_by is None


def test_prds_d_02__already_deleted_400(db, s):
    """PRDS-D-02 — an already deleted row: the 400 passes unchanged and the session is rolled back.
    Rules: delete_product R2; TC3."""
    p = stock(db, s, qty=0, **deleted(s))
    commit_point(db)
    p_before = snap(db, p.id)
    pid, w1, u2 = p.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.delete_product(db, prod_id=pid, workspace_id=w1, user_id=u2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Product record is already deleted"
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert snap(db, pid) == p_before
    # Then 7
    assert usable(db)


def test_prds_d_03__unknown_id_404(db, s):
    """PRDS-D-03 — an unknown id: the 404 passes unchanged and the session is rolled back.
    Rules: delete_product R2; TC3."""
    p = stock(db, s, qty=0)
    commit_point(db)
    p_before = snap(db, p.id)
    pid, w1, u2 = p.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_product(db, prod_id=MISSING, workspace_id=w1, user_id=u2)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Product record with ID 999999999 not found"
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, pid) == p_before


@xfail(2774)
def test_prds_d_04__row_with_stock_refused(db, s):
    """PRDS-D-04 — pass-through BUG-2774: a row holding stock is refused with its blocker, rolled back.
    Rules: delete_product R2 [BUG-2774]; TC3."""
    p = stock(db, s, qty=4)
    before = commit_point(db)
    p_before = snap(db, p.id)
    pid, w1, u2 = p.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_product(db, prod_id=pid, workspace_id=w1, user_id=u2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Product record still holds stock"
    # Then 3
    assert exc.value.errors == [{"type": "product_stock", "id": pid, "qty": 4}]
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert snap(db, pid) == p_before
    # Then 6
    assert counts(db) == before


# [claude] PRDS-D-05
def test_prds_d_05__manager_validation_error_passes(db, s):
    """PRDS-D-05 — the manager's ValidationError passes as the same object after a rollback.
    Rules: delete_product R2 (BUG-2774 companion); TC3."""
    p = stock(db, s, qty=4)
    commit_point(db)
    p_before = snap(db, p.id)
    pid, w1, u2 = p.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)
    E = AppValidationError(
        "Product record still holds stock", errors=[{"type": "product_stock", "id": 5, "qty": 4}]
    )

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        with spies(db) as (cm, rb):
            with patch.object(product_service.manager, "delete_product", side_effect=E):
                svc.delete_product(db, prod_id=pid, workspace_id=w1, user_id=u2)
    assert exc.value is E
    # Then 2
    assert exc.value.detail == "Product record still holds stock"
    # Then 3
    assert exc.value.errors == [{"type": "product_stock", "id": 5, "qty": 4}]
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert cm.call_count == 0
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert snap(db, pid) == p_before


def test_prds_d_06__failing_commit_row_stays_live(db, s):
    """PRDS-D-06 — a failing commit leaves the row live and discards the extra row.
    Rules: delete_product R1; TC4."""
    p = stock(db, s, qty=0)
    commit_point(db)
    pid, w1, u2 = p.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_product(db, prod_id=pid, workspace_id=w1, user_id=u2)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, Product, pid)
    assert row.is_deleted is False
    assert row.deleted_by is None
    assert row.deleted_at is None
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert usable(db)


# --------------------------------------------------------------------------- #
# ProductService.list_ledger
# --------------------------------------------------------------------------- #


def test_prds_lg_01__defaults_workspace_entries(db, s):
    """PRDS-LG-01 — the defaults return the workspace's entries only (compared as a set).
    Rules: list_ledger R1."""
    entry(db, s, workspace_id=s.W0.id, factory_id=s.F0.id, item_id=s.I0.id)
    a = entry(db, s)
    b = entry(db, s, item_id=s.I2.id, performed_at=T2)
    entry(db, s, workspace_id=s.W2.id, factory_id=s.F9.id, item_id=s.I9.id)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert {r.id for r in result} == {a.id, b.id}


def test_prds_lg_02__factory_filter(db, s):
    """PRDS-LG-02 — the factory filter is passed on.
    Rules: list_ledger R1."""
    entry(db, s)
    b = entry(db, s, factory_id=s.F2.id)
    c = entry(db, s, factory_id=s.F2.id, item_id=s.I2.id)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, factory_id=s.F2.id)

    # Then 1
    assert {r.id for r in result} == {b.id, c.id}


def test_prds_lg_03__factory_of_w2_nothing(db, s):
    """PRDS-LG-03 — a factory of W2 (higher workspace id) shows nothing.
    Rules: list_ledger R3; HR-16."""
    entry(db, s)
    entry(db, s, workspace_id=s.W2.id, factory_id=s.F9.id, item_id=s.I9.id)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, factory_id=s.F9.id)

    # Then 1
    assert result == []


def test_prds_lg_04__factory_of_w0_nothing(db, s):
    """PRDS-LG-04 — a factory of W0 (lower workspace id) shows nothing.
    Rules: list_ledger R3; HR-16."""
    entry(db, s, workspace_id=s.W0.id, factory_id=s.F0.id, item_id=s.I0.id)
    entry(db, s)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, factory_id=s.F0.id)

    # Then 1
    assert result == []


def test_prds_lg_05__item_filter(db, s):
    """PRDS-LG-05 — the item filter is passed on.
    Rules: list_ledger R1."""
    entry(db, s)
    b = entry(db, s, item_id=s.I2.id)
    c = entry(db, s, factory_id=s.F2.id, item_id=s.I2.id)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, item_id=s.I2.id)

    # Then 1
    assert {r.id for r in result} == {b.id, c.id}


def test_prds_lg_06__item_of_w2_nothing(db, s):
    """PRDS-LG-06 — an item of W2 shows nothing.
    Rules: list_ledger R3; HR-16."""
    entry(db, s)
    entry(db, s, workspace_id=s.W2.id, factory_id=s.F9.id, item_id=s.I9.id)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, item_id=s.I9.id)

    # Then 1
    assert result == []


def test_prds_lg_07__factory_zero_filters(db, s):
    """PRDS-LG-07 — factory_id=0 filters and gives [].
    Rules: list_ledger R1."""
    entry(db, s)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, factory_id=0)

    # Then 1
    assert result == []


def test_prds_lg_08__item_zero_filters(db, s):
    """PRDS-LG-08 — item_id=0 filters and gives [].
    Rules: list_ledger R1."""
    entry(db, s)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, item_id=0)

    # Then 1
    assert result == []


def test_prds_lg_09__transaction_type_exact(db, s):
    """PRDS-LG-09 — the transaction type is compared exactly.
    Rules: list_ledger R1."""
    entry(db, s)
    b = entry(db, s, transaction_type="sale")
    entry(db, s, transaction_type="Sale")
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, transaction_type="sale")

    # Then 1
    assert {r.id for r in result} == {b.id}


def test_prds_lg_10__blank_type_no_filter(db, s):
    """PRDS-LG-10 — a blank transaction type applies no filter.
    Rules: list_ledger R1."""
    a = entry(db, s)
    b = entry(db, s, transaction_type="sale")
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, transaction_type="")

    # Then 1
    assert {r.id for r in result} == {a.id, b.id}


def test_prds_lg_11__naive_bounds_inclusive(db, s):
    """PRDS-LG-11 — naive date bounds are inclusive at both ends.
    Rules: list_ledger R1 (BUG-992 companion)."""
    entry(db, s)
    b = entry(db, s, performed_at=T2)
    c = entry(db, s, performed_at=T3)
    entry(db, s, performed_at=T4)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, start_date=T2, end_date=T3)

    # Then 1
    assert {r.id for r in result} == {b.id, c.id}


@xfail(992)
def test_prds_lg_12__aware_bounds_in_utc(db, s):
    """PRDS-LG-12 — pass-through BUG-992: aware bounds are compared in UTC.
    Rules: list_ledger R1 [BUG-992]."""
    a = entry(db, s, performed_at=datetime(2026, 3, 1, 12, 0, 0))
    entry(db, s, performed_at=T5)
    commit_point(db)
    aid, w1 = a.id, s.W1.id
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))

    result = svc.list_ledger(
        db, workspace_id=w1,
        start_date=datetime(2026, 3, 1, 11, 30, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 1, 12, 30, tzinfo=timezone.utc),
    )

    # Then 1
    assert [r.id for r in result] == [aid]


def test_prds_lg_13__deleted_parents_stay_listed(db, s):
    """PRDS-LG-13 — entries of a deleted factory, a removed item and a deleted product stay listed.
    Rules: list_ledger R1 (D2)."""
    stock(db, s, item_id=s.I2.id, qty=0, **deleted(s))
    a = entry(db, s, factory_id=s.FD.id)
    b = entry(db, s, item_id=s.IX.id)
    c = entry(db, s, item_id=s.I2.id, transaction_type="inventory_adjustment")
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id)

    # Then 1
    assert {r.id for r in result} == {a.id, b.id, c.id}


def test_prds_lg_14__newest_first(db, s):
    """PRDS-LG-14 — of different times the newest comes first, whatever the id order.
    Rules: list_ledger R2 (today's part)."""
    b = entry(db, s, performed_at=T2)
    c = entry(db, s, performed_at=T3)
    a = entry(db, s)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id)

    # Then 1
    assert [r.id for r in result] == [c.id, b.id, a.id]


# [claude] PRDS-LG-15
@xfail(640, strict=False)
def test_prds_lg_15__tied_times_id_descending(db, s):
    """PRDS-LG-15 — pass-through BUG-640: tied times come back id descending.
    Rules: list_ledger R2 [BUG-640]."""
    a = entry(db, s)
    b = entry(db, s)
    c = entry(db, s)
    a.notes = "x"
    db.flush()
    commit_point(db)
    ids = (a.id, b.id, c.id)
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))
    db.expire_all()

    result = svc.list_ledger(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert [r.id for r in result] == [ids[2], ids[1], ids[0]]


@xfail(640)
def test_prds_lg_16__order_breaks_ties_by_id(db, s):
    """PRDS-LG-16 — BUG-640: the ledger query breaks ties by id descending.
    Rules: list_ledger R2 [BUG-640]."""
    a = entry(db, s)
    b = entry(db, s, performed_at=T2)
    commit_point(db)

    with Recorder(db) as rec:
        result = svc.list_ledger(db, workspace_id=s.W1.id)

    # Then 1
    assert {r.id for r in result} == {a.id, b.id}
    # Then 2
    assert "performed_at DESC" in rec.order_part
    # Then 3
    assert "id DESC" in rec.order_part.split("performed_at DESC", 1)[1]


def test_prds_lg_17__default_limit_100(db, s):
    """PRDS-LG-17 — with the defaults 101 entries give 100.
    Rules: list_ledger R1."""
    db.add_all([entry(db, s, flush=False, performed_at=T1 + timedelta(minutes=k)) for k in range(1, 102)])
    db.flush()
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 100


def _five_entries(db, s):
    a = entry(db, s)
    b = entry(db, s, performed_at=T2)
    c = entry(db, s, performed_at=T3)
    d = entry(db, s, performed_at=T4)
    e = entry(db, s, performed_at=T5)
    return a, b, c, d, e


def test_prds_lg_18__skip_limit_after_order(db, s):
    """PRDS-LG-18 — skip and limit are passed on, after the order.
    Rules: list_ledger R1, R2."""
    _a, _b, c, d, _e = _five_entries(db, s)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, skip=1, limit=2)

    # Then 1
    assert [r.id for r in result] == [d.id, c.id]


def test_prds_lg_19__skip_four_gives_oldest(db, s):
    """PRDS-LG-19 — skip=4 with limit=1000 gives the oldest entry.
    Rules: list_ledger R1, R2."""
    a, *_ = _five_entries(db, s)
    commit_point(db)

    result = svc.list_ledger(db, workspace_id=s.W1.id, skip=4, limit=1000)

    # Then 1
    assert [r.id for r in result] == [a.id]


def test_prds_lg_20__ledger_list_no_commit_no_lock(db, s):
    """PRDS-LG-20 — the ledger list neither commits nor rolls back, and takes no lock.
    Rules: list_ledger R1; TC6."""
    a = entry(db, s)
    b = entry(db, s, notes="Old")
    commit_point(db)
    aid, bid, w1 = a.id, b.id, s.W1.id
    _, x_id = mk_x(db)
    n = entry(db, s, flush=False, item_id=s.I2.id)
    db.add(n)
    b.notes = "Edited"

    with Recorder(db) as rec:
        with spies(db) as (cm, rb):
            result = svc.list_ledger(db, workspace_id=w1)

    # Then 1
    assert {r.id for r in result} == {aid, bid}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert n in db.new
    assert len(db.new) == 1
    # Then 5
    assert b in db.dirty
    assert len(db.dirty) == 1
    # Then 6
    assert rec.no_lock
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)
    # Then 8
    assert reread(db, ProductLedger, bid).notes == "Old"


def test_prds_lg_21__negative_limit_data_error(db, s):
    """PRDS-LG-21 — a negative limit is rejected by the database, and the service does not roll back.
    Rules: list_ledger Errors; TC6."""
    entry(db, s)
    commit_point(db)
    x, _ = mk_x(db)
    w1 = s.W1.id

    # Then 1
    with pytest.raises(DataError) as exc:
        with spies(db) as (cm, rb):
            with db.begin_nested():
                svc.list_ledger(db, workspace_id=w1, limit=-1)
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert x in db


# --------------------------------------------------------------------------- #
# ProductService.make_sellable (new method, BUG-2793)
# --------------------------------------------------------------------------- #


# Given "S = stock, but qty 10, avg_cost 5.00" and "T = stock, but for sale, qty 4, avg_cost 8.00"
def _s_and_t(db, s):
    src = stock(db, s, qty=10, avg_cost=Decimal("5.00"))
    tgt = stock(db, s, **FOR_SALE, qty=4, avg_cost=Decimal("8.00"))
    return src, tgt


@xfail(2793)
def test_prds_ms_01__move_committed_two_ledger_rows(db, s):
    """PRDS-MS-01 — a move is committed on both buckets with two ledger rows; the target is returned.
    Rules: make_sellable S1, Returns (D1); TC1, TC2."""
    src, tgt = _s_and_t(db, s)
    commit_point(db)
    sid, tid, w1, f1, i1, u2 = src.id, tgt.id, s.W1.id, s.F1.id, s.I1.id, s.U2.id

    with spies(db) as (cm, rb):
        result = svc.make_sellable(db, prod_id=sid, quantity=3, workspace_id=w1, user_id=u2)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == tid
    assert result.qty == 7
    # Then 3
    assert cm.call_count == 1
    # Then 4
    assert rb.call_count == 0
    db.rollback()
    # Then 5
    row = reread(db, Product, sid)
    assert row.qty == 7
    assert row.avg_cost == Decimal("5.00")
    # Then 6
    row = reread(db, Product, tid)
    assert row.qty == 7
    assert row.avg_cost == Decimal("6.71")
    # Then 7
    led = ledger_of(db, w1, f1, i1)
    assert len(led) == 2
    assert all(r.transaction_type == "transfer" for r in led)
    assert all(r.source_type == "make_sellable" for r in led)
    assert all(r.quantity == 3 for r in led)


@xfail(2793)
def test_prds_ms_02__missing_target_created(db, s):
    """PRDS-MS-02 — a missing target is created and committed with the source average.
    Rules: make_sellable S1."""
    src = stock(db, s, qty=10, avg_cost=Decimal("5.00"))
    commit_point(db)
    sid, w1, f1, i1, u2 = src.id, s.W1.id, s.F1.id, s.I1.id, s.U2.id

    result = svc.make_sellable(db, prod_id=sid, quantity=4, workspace_id=w1, user_id=u2)

    # Then 1
    assert result.id != sid
    assert result.is_available_for_sale is True
    rid = result.id
    db.rollback()
    # Then 2
    row = reread(db, Product, rid)
    assert row.qty == 4
    assert row.avg_cost == Decimal("5.00")
    assert row.created_by == u2
    # Then 3
    assert reread(db, Product, sid).qty == 6
    # Then 4
    assert len(products_of(db, w1)) == 2
    # Then 5
    assert len(ledger_of(db, w1, f1, i1)) == 2


@xfail(2793)
def test_prds_ms_03__unknown_id_404(db, s):
    """PRDS-MS-03 — an unknown id: the 404 passes unchanged and the session is rolled back.
    Rules: make_sellable S2."""
    stock(db, s, qty=10)
    before = commit_point(db)
    w1, u2 = s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.make_sellable(db, prod_id=MISSING, quantity=3, workspace_id=w1, user_id=u2)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Product record with ID 999999999 not found"
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert counts(db) == before


@xfail(2793)
def test_prds_ms_04__source_of_w2_404(db, s):
    """PRDS-MS-04 — a source of W2: the 404 passes unchanged, nothing saved.
    Rules: make_sellable S2."""
    z2 = stock(db, s, workspace_id=s.W2.id, item_id=s.I9.id, factory_id=s.F9.id, qty=10)
    before = commit_point(db)
    z_before = snap(db, z2.id)
    zid, w1, u2 = z2.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.make_sellable(db, prod_id=zid, quantity=3, workspace_id=w1, user_id=u2)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Product record with ID {zid} not found"
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, zid) == z_before
    # Then 5
    assert counts(db) == before


@xfail(2793)
def test_prds_ms_05__deleted_source_400(db, s):
    """PRDS-MS-05 — a soft-deleted source: the 400 passes unchanged and the session is rolled back.
    Rules: make_sellable S2."""
    src = stock(db, s, qty=10, **deleted(s))
    before = commit_point(db)
    s_before = snap(db, src.id)
    sid, w1, u2 = src.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.make_sellable(db, prod_id=sid, quantity=3, workspace_id=w1, user_id=u2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot update a deleted product record"
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, sid) == s_before
    # Then 5
    assert counts(db) == before


@xfail(2793)
def test_prds_ms_06__for_sale_source_400(db, s):
    """PRDS-MS-06 — a for-sale source: the 400 passes unchanged and the session is rolled back.
    Rules: make_sellable S2."""
    tgt = stock(db, s, **FOR_SALE, qty=10)
    before = commit_point(db)
    t_before = snap(db, tgt.id)
    tid, w1, u2 = tgt.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.make_sellable(db, prod_id=tid, quantity=3, workspace_id=w1, user_id=u2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Only a not-for-sale product record can be made sellable"
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, tid) == t_before
    # Then 5
    assert counts(db) == before


@xfail(2793)
def test_prds_ms_07__quantity_zero_400(db, s):
    """PRDS-MS-07 — quantity 0: the 400 passes unchanged and the session is rolled back.
    Rules: make_sellable S2."""
    src = stock(db, s, qty=10)
    before = commit_point(db)
    s_before = snap(db, src.id)
    sid, w1, u2 = src.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.make_sellable(db, prod_id=sid, quantity=0, workspace_id=w1, user_id=u2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Quantity must be a positive whole number"
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, sid) == s_before
    # Then 5
    assert counts(db) == before


@xfail(2793)
def test_prds_ms_08__one_more_than_held_422(db, s):
    """PRDS-MS-08 — one more than held: the 422 passes unchanged, both buckets kept.
    Rules: make_sellable S2, S3."""
    src, tgt = _s_and_t(db, s)
    before = commit_point(db)
    s_before, t_before = snap(db, src.id), snap(db, tgt.id)
    sid, tid, w1, u2 = src.id, tgt.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.make_sellable(db, prod_id=sid, quantity=11, workspace_id=w1, user_id=u2)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Insufficient stock to make sellable: requested 11, available 10"
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, sid) == s_before
    # Then 5
    assert snap(db, tid) == t_before
    # Then 6
    assert counts(db) == before


@xfail(2793)
def test_prds_ms_09__failing_commit_saves_nothing(db, s):
    """PRDS-MS-09 — a failing commit saves nothing: source kept, no ledger row, sum unchanged.
    Rules: make_sellable S1, S3; TC4."""
    src, tgt = _s_and_t(db, s)
    commit_point(db)
    sid, tid, w1, u2 = src.id, tgt.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.make_sellable(db, prod_id=sid, quantity=3, workspace_id=w1, user_id=u2)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, Product, sid).qty == 10
    # Then 4
    row = reread(db, Product, tid)
    assert row.qty == 4
    assert row.avg_cost == Decimal("8.00")
    # Then 5
    assert reread(db, Product, sid).qty + reread(db, Product, tid).qty == 14
    # Then 6
    assert ledger_count(db) == 0
    # Then 7
    assert x_gone(db, x_id)


@xfail(2793)
def test_prds_ms_10__buckets_locked_one_commit(db, s):
    """PRDS-MS-10 — the buckets are locked by the move and committed once in the same call.
    Rules: make_sellable S1, S4 (clause only)."""
    src, tgt = _s_and_t(db, s)
    commit_point(db)
    sid, tid, w1, u2 = src.id, tgt.id, s.W1.id, s.U2.id

    with Recorder(db) as rec:
        with spies(db) as (cm, _rb):
            result = svc.make_sellable(db, prod_id=sid, quantity=3, workspace_id=w1, user_id=u2)

    # Then 1
    assert result.id == tid
    # Then 2
    assert sum("FOR UPDATE OF products" in st for st in rec.psel) >= 2
    # Then 3
    assert all(st.count("FOR UPDATE") == st.count("FOR UPDATE OF products") for st in rec.selects)
    # Then 4
    assert not any("SKIP LOCKED" in st for st in rec.selects)
    # Then 5
    assert not any("NOWAIT" in st for st in rec.selects)
    # Then 6
    assert cm.call_count == 1


@xfail(2793)
def test_prds_ms_11__failing_refresh_keeps_move(db, s):
    """PRDS-MS-11 — a failing re-read after the commit leaves the move saved.
    Rules: make_sellable S1; TC5."""
    src, tgt = _s_and_t(db, s)
    commit_point(db)
    sid, tid, w1, f1, i1, u2 = src.id, tgt.id, s.W1.id, s.F1.id, s.I1.id, s.U2.id

    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.make_sellable(db, prod_id=sid, quantity=3, workspace_id=w1, user_id=u2)
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert reread(db, Product, sid).qty == 7
    # Then 3
    assert reread(db, Product, tid).qty == 7
    # Then 4
    assert len(ledger_of(db, w1, f1, i1)) == 2
