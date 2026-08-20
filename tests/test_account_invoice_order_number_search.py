"""Tests for account invoice search by linked order number."""

from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, literal
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app.dao.account_invoice import AccountInvoiceDAO
from app.models.account_invoice import AccountInvoice


def test_escape_ilike_escapes_wildcards() -> None:
    assert AccountInvoiceDAO._escape_ilike("100%") == "100\\%"
    assert AccountInvoiceDAO._escape_ilike("PO_2026") == "PO\\_2026"
    assert AccountInvoiceDAO._escape_ilike("a\\b") == "a\\\\b"


def test_invoice_number_search_ilike_term_wraps_escaped_value() -> None:
    assert AccountInvoiceDAO._invoice_number_search_ilike_term("PO-2026") == "%PO-2026%"
    assert AccountInvoiceDAO._invoice_number_search_ilike_term("100%") == "%100\\%%"


def test_order_number_search_conditions_sql_includes_all_order_number_columns() -> None:
    dao = AccountInvoiceDAO(AccountInvoice)
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()

    condition = dao._order_number_search_conditions(
        session,
        workspace_id=42,
        term="%PO-2025%",
    )
    sql = str(condition.compile(dialect=postgresql.dialect()))

    assert "po_number" in sql
    assert "expense_number" in sql
    assert "sales_order_number" in sql
    assert "work_order_number" in sql
    assert "purchase_order" in sql
    assert "expense_order" in sql
    assert "sales_order" in sql
    assert "work_order" in sql


def test_list_invoices_page_filtered_forwards_invoice_number_search() -> None:
    dao = AccountInvoiceDAO(AccountInvoice)
    db = MagicMock()
    invoice = MagicMock()
    invoice.id = 99

    with patch.object(dao, "_build_filtered_query") as mock_build:
        chain = mock_build.return_value
        chain.count.return_value = 1
        chain.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            invoice
        ]

        items, total = dao.list_invoices_page_filtered(
            db,
            workspace_id=7,
            account_id=3,
            invoice_number_search="PO-2025-001",
            skip=0,
            limit=10,
        )

    mock_build.assert_called_once_with(
        db,
        workspace_id=7,
        account_id=3,
        invoice_type=None,
        payment_status=None,
        invoice_status=None,
        invoice_number_search="PO-2025-001",
        account_name_search=None,
        invoice_date_from=None,
        invoice_date_to=None,
        due_date_from=None,
        due_date_to=None,
        amount_min=None,
        amount_max=None,
        open_balance_only=False,
    )
    assert total == 1
    assert items == [invoice]


def test_build_filtered_query_invokes_order_number_search_helper() -> None:
    dao = AccountInvoiceDAO(AccountInvoice)
    db = MagicMock()
    base_query = MagicMock()
    db.query.return_value.join.return_value.filter.return_value = base_query
    base_query.filter.return_value = base_query

    with patch.object(dao, "_order_number_search_conditions", return_value=literal(True)) as mock_order_search:
        dao._build_filtered_query(db, workspace_id=1, invoice_number_search="EXP-2026")

    mock_order_search.assert_called_once_with(db, workspace_id=1, term="%EXP-2026%")
    base_query.filter.assert_called_once()


def test_build_filtered_query_adds_numeric_id_match() -> None:
    dao = AccountInvoiceDAO(AccountInvoice)
    db = MagicMock()
    base_query = MagicMock()
    db.query.return_value.join.return_value.filter.return_value = base_query
    base_query.filter.return_value = base_query

    with patch.object(dao, "_order_number_search_conditions", return_value=literal(True)):
        dao._build_filtered_query(db, workspace_id=1, invoice_number_search="42")

    filter_clause = base_query.filter.call_args[0][0]
    compiled = str(filter_clause.compile(dialect=postgresql.dialect()))
    assert "account_invoices.id" in compiled


def test_account_invoices_search_query_description() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    params = paths["/api/v1/account-invoices/"]["get"]["parameters"]
    search_param = next(p for p in params if p["name"] == "invoice_number_search")
    assert "order number" in search_param["description"].lower()


def test_account_detail_invoices_search_query_description() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    params = paths["/api/v1/accounts/{account_id}/invoices/"]["get"]["parameters"]
    search_param = next(p for p in params if p["name"] == "invoice_number_search")
    assert "order number" in search_param["description"].lower()
