"""Unit tests for app/dao/access_control.py.

Implements tests/unit/dao/access_control.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is read (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError

from app.dao.access_control import access_control_dao
from app.models.access_control import AccessControl
from app.models.enums import AccessControlTypeEnum, RoleEnum
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton access_control_dao"
dao = access_control_dao

# Conventions OWNER, FINANCE, PAGE, FEATURE
OWNER = RoleEnum.OWNER
FINANCE = RoleEnum.FINANCE
PAGE = AccessControlTypeEnum.PAGE
FEATURE = AccessControlTypeEnum.FEATURE

# Convention "MISSING" (no card uses it today; kept with the Conventions)
MISSING = 999999999


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

# Convention "W1, W2 = two workspaces rows from make_workspace(db)"; w2 after w1.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "Standing rows, no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (each flushes before it returns)
# --------------------------------------------------------------------------- #

def _rule_fields(workspace, columns):
    fields = {"workspace_id": workspace.id, "type": PAGE, "target": "/orders", "role": OWNER}
    fields.update(columns)
    return fields


# Convention "rule": AccessControl(workspace_id=W1.id, type=PAGE, target="/orders", role=OWNER)
@pytest.fixture
def mk_rule(db, w1):
    """mk_rule(**columns) -> AccessControl; the keywords are the columns after "but"."""
    def _mk(**columns):
        row = AccessControl(**_rule_fields(w1, columns))
        db.add(row)
        db.flush()
        return row
    return _mk


# The "101 rules E1 ... E101, built with add_all" Given
@pytest.fixture
def mk_many_rules(db, w1):
    """mk_many_rules(count) -> [E1, ..., Ecount]; Ek = rule, but target f"/p{k}"."""
    def _mk(count):
        rows = [AccessControl(**_rule_fields(w1, {"target": f"/p{k}"})) for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "idset(result)"
def idset(result):
    return {r.id for r in result}


# Convention "ids(result)": in the order returned
def ids(result):
    return [r.id for r in result]


# Convention "nothing written": the number of access_control rows stored
def stored_count(db):
    return db.scalar(select(func.count()).select_from(AccessControl.__table__))


# Convention "Statement recorder"
class StatementRecorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """The one SELECT from access_control; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.statements
                       if s.lstrip().upper().startswith("SELECT") and "FROM access_control" in s]
        return statement


# Convention "order_part"
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


BUG_1408 = "BUG-1408: Filtered permission lists have no sort order"
BUG_1408_NON_STRICT = (BUG_1408 + " (non-strict: the rows come back in physical order, "
                       "which can match the intended order by accident)")


# --------------------------------------------------------------------------- #
# DAOAccessControl.get_by_role
# --------------------------------------------------------------------------- #


# [claude] ACL-GR-01
def test_acl_gr_01__the_role_s_rows_of_the_workspace_every_type_duplicates_each_returned(db, w1, w2, mk_rule):
    """ACL-GR-01 — the role's rows of the workspace, every type, duplicates each returned.
    Rules: `get_by_role` R1, R3, Returns"""
    mk_rule(workspace_id=None)
    a = mk_rule()
    b = mk_rule(type=FEATURE, target="reports")
    mk_rule(role=FINANCE)
    d = mk_rule()
    mk_rule(workspace_id=w2.id)

    result = dao.get_by_role(db, role=OWNER, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a.id, b.id, d.id}
    # Then 3
    assert len(result) == 3


# [claude] ACL-GR-02
def test_acl_gr_02__the_workspace_filter_is_applied_before_the_page(db, w1, w2, mk_rule):
    """ACL-GR-02 — the workspace filter is applied before the page.
    Rules: `get_by_role` R1"""
    mk_rule(workspace_id=w2.id)
    a = mk_rule()
    b = mk_rule(target="/sales")

    result = dao.get_by_role(db, role=OWNER, workspace_id=w1.id, skip=1, limit=1000)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] ACL-GR-03
def test_acl_gr_03__the_role_as_its_value_owner_matches_the_same_rows(db, w1, mk_rule):
    """ACL-GR-03 — the role as its value "owner" matches the same rows.
    Rules: `get_by_role` R2"""
    a = mk_rule()
    mk_rule(role=FINANCE)

    result = dao.get_by_role(db, role="owner", workspace_id=w1.id)

    # Then 1
    assert idset(result) == {a.id}


# [claude] ACL-GR-04
def test_acl_gr_04__the_role_as_its_name_owner_matches_the_same_rows(db, w1, mk_rule):
    """ACL-GR-04 — the role as its name "OWNER" matches the same rows.
    Rules: `get_by_role` R2"""
    a = mk_rule()
    mk_rule(role=FINANCE)

    result = dao.get_by_role(db, role="OWNER", workspace_id=w1.id)

    # Then 1
    assert idset(result) == {a.id}


# [claude] ACL-GR-05
def test_acl_gr_05__a_string_that_is_not_a_role_raises_dataerror_22p02(db, w1, mk_rule):
    """ACL-GR-05 — a string that is not a role raises DataError 22P02.
    Rules: `get_by_role` R2, Errors row 1"""
    mk_rule()
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_role(db, role="nobody", workspace_id=w1.id)
    # Then 2
    assert exc.value.orig.pgcode == "22P02"
    # Then 3
    assert stored_count(db) == before


# [claude] ACL-GR-06
def test_acl_gr_06__workspace_id_none_returns_the_rows_with_no_workspace(db, mk_rule):
    """ACL-GR-06 — workspace_id=None returns the rows with no workspace.
    Rules: `get_by_role` R3"""
    a = mk_rule()
    n = mk_rule(workspace_id=None)

    result = dao.get_by_role(db, role=OWNER, workspace_id=None)

    # Then 1
    assert n.id in idset(result)
    # Then 2
    assert a.id not in idset(result)
    # Then 3
    assert all(r.workspace_id is None for r in result)


# [claude] ACL-GR-07
@pytest.mark.xfail(strict=False, reason=BUG_1408_NON_STRICT)
def test_acl_gr_07__rows_come_id_ascending_also_after_the_lowest_id_was_updated(db, w1, mk_rule):
    """ACL-GR-07 — rows come id ascending, also after the lowest id was updated.
    Rules: `get_by_role` R4 [BUG-1408]"""
    seqscan(db)
    a = mk_rule()
    b = mk_rule(target="/sales")
    c = mk_rule(target="/stock")
    d = mk_rule(target="/people")
    a.target = "/changed"
    db.flush()
    db.expire_all()

    result = dao.get_by_role(db, role=OWNER, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [a.id, b.id, c.id, d.id]


# [claude] ACL-GR-08
@pytest.mark.xfail(strict=True, reason=BUG_1408)
def test_acl_gr_08__the_query_orders_by_id_ascending(db, w1, mk_rule):
    """ACL-GR-08 — the query orders by id ascending.
    Rules: `get_by_role` R4 [BUG-1408]"""
    a = mk_rule()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_role(db, role=OWNER, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert "DESC" not in order_part.upper()
    # Then 5
    assert order_part.count(",") == 0


# [claude] ACL-GR-09
def test_acl_gr_09__with_the_defaults_101_rows_give_100(db, w1, mk_many_rules):
    """ACL-GR-09 — with the defaults 101 rows give 100.
    Rules: `get_by_role` R5"""
    e = mk_many_rules(101)

    result = dao.get_by_role(db, role=OWNER, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert idset(result) <= idset(e)


# [claude] ACL-GR-10
def test_acl_gr_10__limit_1000_gives_all_101(db, w1, mk_many_rules):
    """ACL-GR-10 — limit=1000 gives all 101.
    Rules: `get_by_role` R5"""
    e = mk_many_rules(101)

    result = dao.get_by_role(db, role=OWNER, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert idset(result) == idset(e)


# [claude] ACL-GR-11
def test_acl_gr_11__limit_0_returns_an_empty_list(db, w1, mk_rule):
    """ACL-GR-11 — limit=0 returns an empty list.
    Rules: `get_by_role` R5"""
    mk_rule()
    mk_rule(target="/sales")

    result = dao.get_by_role(db, role=OWNER, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] ACL-GR-12
def test_acl_gr_12__limit_1_returns_one_row(db, w1, mk_rule):
    """ACL-GR-12 — limit=1 returns one row.
    Rules: `get_by_role` R5"""
    a = mk_rule()
    b = mk_rule(target="/sales")

    result = dao.get_by_role(db, role=OWNER, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] ACL-GR-13
def test_acl_gr_13__skip_past_the_end_returns_an_empty_list(db, w1, mk_rule):
    """ACL-GR-13 — skip past the end returns an empty list.
    Rules: `get_by_role` R5"""
    mk_rule()
    mk_rule(target="/sales")

    result = dao.get_by_role(db, role=OWNER, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] ACL-GR-14
def test_acl_gr_14__skip_at_the_last_row_returns_one_row(db, w1, mk_rule):
    """ACL-GR-14 — skip at the last row returns one row.
    Rules: `get_by_role` R5"""
    a = mk_rule()
    b = mk_rule(target="/sales")

    result = dao.get_by_role(db, role=OWNER, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] ACL-GR-15
def test_acl_gr_15__workspace_id_0_returns_an_empty_list(db, mk_rule):
    """ACL-GR-15 — workspace id 0 returns an empty list.
    Rules: `get_by_role` R5"""
    mk_rule()

    result = dao.get_by_role(db, role=OWNER, workspace_id=0)

    # Then 1
    assert result == []


# [claude] ACL-GR-16
def test_acl_gr_16__a_negative_limit_raises_dataerror_2201w(db, w1, mk_rule):
    """ACL-GR-16 — a negative limit raises DataError 2201W.
    Rules: `get_by_role` R5, Errors row 2"""
    mk_rule()
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_role(db, role=OWNER, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] ACL-GR-17
def test_acl_gr_17__a_negative_skip_raises_dataerror_2201x(db, w1, mk_rule):
    """ACL-GR-17 — a negative skip raises DataError 2201X.
    Rules: `get_by_role` R5, Errors row 2"""
    mk_rule()
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_role(db, role=OWNER, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] ACL-GR-18
def test_acl_gr_18__positional_arguments_raise_typeerror(db, w1, mk_rule):
    """ACL-GR-18 — positional arguments raise TypeError.
    Rules: `get_by_role` Errors row 3"""
    mk_rule()

    # Then 1
    with pytest.raises(TypeError):
        dao.get_by_role(db, OWNER, w1.id)


# [claude] ACL-GR-19
def test_acl_gr_19__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, w2, mk_rule):
    """ACL-GR-19 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_role` Side effects"""
    a = mk_rule()
    b = mk_rule(workspace_id=w2.id)
    p = AccessControl(workspace_id=w1.id, type=PAGE, target="/pending", role=OWNER)
    db.add(p)
    b.target = "/edited"

    with StatementRecorder(db) as recorder:
        result = dao.get_by_role(db, role=OWNER, workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert b in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    # Then 7
    assert not db.deleted
    # Then 8
    assert written == []


# --------------------------------------------------------------------------- #
# DAOAccessControl.get_by_type
# --------------------------------------------------------------------------- #


# [claude] ACL-GT-01
def test_acl_gt_01__the_type_s_rows_of_the_workspace_every_role_duplicates_each_returned(db, w1, w2, mk_rule):
    """ACL-GT-01 — the type's rows of the workspace, every role, duplicates each returned.
    Rules: `get_by_type` R1, Returns"""
    mk_rule(workspace_id=None)
    a = mk_rule()
    b = mk_rule(role=FINANCE)
    mk_rule(type=FEATURE, target="reports")
    d = mk_rule()
    mk_rule(workspace_id=w2.id)

    result = dao.get_by_type(db, access_type=PAGE, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a.id, b.id, d.id}
    # Then 3
    assert len(result) == 3


# [claude] ACL-GT-02
def test_acl_gt_02__the_type_as_its_value_page_matches_the_same_rows(db, w1, mk_rule):
    """ACL-GT-02 — the type as its value "page" matches the same rows.
    Rules: `get_by_type` R2"""
    a = mk_rule()
    mk_rule(type=FEATURE, target="reports")

    result = dao.get_by_type(db, access_type="page", workspace_id=w1.id)

    # Then 1
    assert idset(result) == {a.id}


# [claude] ACL-GT-03
def test_acl_gt_03__the_type_as_its_name_page_matches_the_same_rows(db, w1, mk_rule):
    """ACL-GT-03 — the type as its name "PAGE" matches the same rows.
    Rules: `get_by_type` R2"""
    a = mk_rule()
    mk_rule(type=FEATURE, target="reports")

    result = dao.get_by_type(db, access_type="PAGE", workspace_id=w1.id)

    # Then 1
    assert idset(result) == {a.id}


# [claude] ACL-GT-04
def test_acl_gt_04__a_string_that_is_not_a_type_raises_dataerror_22p02(db, w1, mk_rule):
    """ACL-GT-04 — a string that is not a type raises DataError 22P02.
    Rules: `get_by_type` R2, Errors"""
    mk_rule()
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_type(db, access_type="nobody", workspace_id=w1.id)
    # Then 2
    assert exc.value.orig.pgcode == "22P02"
    # Then 3
    assert stored_count(db) == before


# [claude] ACL-GT-05
def test_acl_gt_05__a_row_whose_type_was_updated_moves_to_the_other_type_s_results(db, w1, mk_rule):
    """ACL-GT-05 — a row whose type was updated moves to the other type's results.
    Rules: `get_by_type` R3"""
    a = mk_rule()
    b = mk_rule(target="/sales")
    a.type = FEATURE
    db.flush()

    result = dao.get_by_type(db, access_type=PAGE, workspace_id=w1.id)

    # Then 1
    assert idset(result) == {b.id}


# [claude] ACL-GT-06
def test_acl_gt_06__the_workspace_filter_is_applied_before_the_page(db, w1, w2, mk_rule):
    """ACL-GT-06 — the workspace filter is applied before the page.
    Rules: `get_by_type` R1"""
    mk_rule(workspace_id=w2.id)
    a = mk_rule()
    b = mk_rule(target="/sales")

    result = dao.get_by_type(db, access_type=PAGE, workspace_id=w1.id, skip=1, limit=1000)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] ACL-GT-07
def test_acl_gt_07__workspace_id_none_returns_the_rows_with_no_workspace(db, mk_rule):
    """ACL-GT-07 — workspace_id=None returns the rows with no workspace.
    Rules: `get_by_type` R1"""
    a = mk_rule()
    n = mk_rule(workspace_id=None)

    result = dao.get_by_type(db, access_type=PAGE, workspace_id=None)

    # Then 1
    assert n.id in idset(result)
    # Then 2
    assert a.id not in idset(result)
    # Then 3
    assert all(r.workspace_id is None for r in result)


# [claude] ACL-GT-08
@pytest.mark.xfail(strict=False, reason=BUG_1408_NON_STRICT)
def test_acl_gt_08__rows_come_id_ascending_also_after_the_lowest_id_was_updated(db, w1, mk_rule):
    """ACL-GT-08 — rows come id ascending, also after the lowest id was updated.
    Rules: `get_by_type` R4 [BUG-1408]"""
    seqscan(db)
    a = mk_rule()
    b = mk_rule(target="/sales")
    c = mk_rule(target="/stock")
    d = mk_rule(target="/people")
    a.target = "/changed"
    db.flush()
    db.expire_all()

    result = dao.get_by_type(db, access_type=PAGE, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [a.id, b.id, c.id, d.id]


# [claude] ACL-GT-09
@pytest.mark.xfail(strict=True, reason=BUG_1408)
def test_acl_gt_09__the_query_orders_by_id_ascending(db, w1, mk_rule):
    """ACL-GT-09 — the query orders by id ascending.
    Rules: `get_by_type` R4 [BUG-1408]"""
    a = mk_rule()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_type(db, access_type=PAGE, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert "DESC" not in order_part.upper()
    # Then 5
    assert order_part.count(",") == 0


# [claude] ACL-GT-10
def test_acl_gt_10__with_the_defaults_101_rows_give_100(db, w1, mk_many_rules):
    """ACL-GT-10 — with the defaults 101 rows give 100.
    Rules: `get_by_type` R5"""
    e = mk_many_rules(101)

    result = dao.get_by_type(db, access_type=PAGE, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert idset(result) <= idset(e)


# [claude] ACL-GT-11
def test_acl_gt_11__limit_1000_gives_all_101(db, w1, mk_many_rules):
    """ACL-GT-11 — limit=1000 gives all 101.
    Rules: `get_by_type` R5"""
    e = mk_many_rules(101)

    result = dao.get_by_type(db, access_type=PAGE, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert idset(result) == idset(e)


# [claude] ACL-GT-12
def test_acl_gt_12__limit_0_returns_an_empty_list(db, w1, mk_rule):
    """ACL-GT-12 — limit=0 returns an empty list.
    Rules: `get_by_type` R5"""
    mk_rule()
    mk_rule(target="/sales")

    result = dao.get_by_type(db, access_type=PAGE, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] ACL-GT-13
def test_acl_gt_13__a_negative_limit_raises_dataerror_2201w(db, w1, mk_rule):
    """ACL-GT-13 — a negative limit raises DataError 2201W.
    Rules: `get_by_type` R5, Errors"""
    mk_rule()
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_type(db, access_type=PAGE, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert stored_count(db) == before


# [claude] ACL-GT-14
def test_acl_gt_14__a_negative_skip_raises_dataerror_2201x(db, w1, mk_rule):
    """ACL-GT-14 — a negative skip raises DataError 2201X.
    Rules: `get_by_type` R5, Errors"""
    mk_rule()
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_type(db, access_type=PAGE, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert stored_count(db) == before


# [claude] ACL-GT-15
def test_acl_gt_15__positional_arguments_raise_typeerror(db, w1, mk_rule):
    """ACL-GT-15 — positional arguments raise TypeError.
    Rules: `get_by_type` Errors"""
    mk_rule()

    # Then 1
    with pytest.raises(TypeError):
        dao.get_by_type(db, PAGE, w1.id)


# [claude] ACL-GT-16
def test_acl_gt_16__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, w2, mk_rule):
    """ACL-GT-16 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_type` Side effects"""
    a = mk_rule()
    b = mk_rule(workspace_id=w2.id)
    p = AccessControl(workspace_id=w1.id, type=PAGE, target="/pending", role=OWNER)
    db.add(p)
    b.target = "/edited"

    with StatementRecorder(db) as recorder:
        result = dao.get_by_type(db, access_type=PAGE, workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert b in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    # Then 7
    assert not db.deleted
    # Then 8
    assert written == []
