"""
Payment API endpoints — SSLCommerz checkout.

Route groups:
  - Authenticated, workspace-scoped: initiate, list, detail, resolve-risk
  - Public (no JWT, no X-Workspace-ID — SSLCommerz never sends either):
    success/fail/cancel (browser redirect targets) and ipn (server-to-server
    webhook). These four all funnel into the same locked validation logic in
    the manager, so a transaction is only ever finalized once.
  - Mock-only, public: the fake hosted gateway page and its "complete" action,
    which exist purely to exercise success/fail/cancel/ipn exactly as the real
    gateway would call them, for local dev and the billing trial page.
"""
import asyncio
from typing import List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.core.limiter import limiter
from app.dao.payment_transaction import payment_transaction_dao
from app.dao.workspace_member import workspace_member_dao
from app.db.session import SessionLocal
from app.integrations.sslcommerz import get_sslcommerz_client
from app.integrations.sslcommerz.mock_client import MockSSLCommerzClient
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.payment_transaction import (
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    PaymentTransactionDetailResponse,
    PaymentTransactionResponse,
    ResolveRiskRequest,
)
from app.services.payment_transaction_service import payment_transaction_service

router = APIRouter()


# ==================== AUTHENTICATED ====================

@router.post(
    "/initiate/",
    response_model=InitiatePaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a checkout session",
)
def initiate_payment(
    payment_in: InitiatePaymentRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return payment_transaction_service.initiate_payment(
        db, workspace_id=workspace.id, user=current_user, request=payment_in
    )


@router.get(
    "/",
    response_model=List[PaymentTransactionResponse],
    summary="List payment transactions (ledger)",
)
def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return payment_transaction_service.list_transactions(db, workspace_id=workspace.id, skip=skip, limit=limit)


@router.get(
    "/{tran_id}/",
    response_model=PaymentTransactionDetailResponse,
    summary="Get a payment transaction with its event history",
)
def get_payment(
    tran_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return payment_transaction_service.get_transaction_by_tran_id(db, tran_id=tran_id, workspace_id=workspace.id)


@router.post(
    "/{transaction_id}/resolve-risk/",
    response_model=PaymentTransactionResponse,
    summary="Approve or reject a risk-held transaction",
)
def resolve_risk(
    transaction_id: int,
    body: ResolveRiskRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    member = workspace_member_dao.get_by_workspace_and_user(db, workspace_id=workspace.id, user_id=current_user.id)
    if member is None or member.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the workspace owner can resolve a risk hold")
    return payment_transaction_service.resolve_risk(
        db, transaction_id=transaction_id, workspace_id=workspace.id,
        user_id=current_user.id, approve=body.approve, note=body.note,
    )


# ==================== PUBLIC GATEWAY CALLBACKS ====================
# No auth, no workspace header — SSLCommerz sends neither. Everything here
# resolves the workspace from tran_id and trusts only server-to-server
# validation, never the raw POST body.

@router.post("/success", include_in_schema=False)
@limiter.limit("30/minute")
async def payment_success(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    tran_id = form.get("tran_id")
    val_id = form.get("val_id")
    if not tran_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing tran_id")

    if val_id:
        payment_transaction_service.handle_gateway_callback(
            db, tran_id=str(tran_id), val_id=str(val_id), source="redirect_success"
        )
    else:
        payment_transaction_service.handle_terminal_without_validation(
            db, tran_id=str(tran_id), terminal_status="VALIDATED_FAILED", source="redirect_success_no_val_id"
        )
    return RedirectResponse(
        url=f"{settings.FRONTEND_BASE_URL}/billing/trial?tran_id={tran_id}", status_code=status.HTTP_302_FOUND
    )


@router.post("/fail", include_in_schema=False)
@limiter.limit("30/minute")
async def payment_fail(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    tran_id = form.get("tran_id")
    val_id = form.get("val_id")
    if not tran_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing tran_id")

    if val_id:
        payment_transaction_service.handle_gateway_callback(
            db, tran_id=str(tran_id), val_id=str(val_id), source="redirect_fail"
        )
    else:
        payment_transaction_service.handle_terminal_without_validation(
            db, tran_id=str(tran_id), terminal_status="VALIDATED_FAILED", source="redirect_fail_no_val_id"
        )
    return RedirectResponse(
        url=f"{settings.FRONTEND_BASE_URL}/billing/trial?tran_id={tran_id}", status_code=status.HTTP_302_FOUND
    )


@router.post("/cancel", include_in_schema=False)
@limiter.limit("30/minute")
async def payment_cancel(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    tran_id = form.get("tran_id")
    if not tran_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing tran_id")

    payment_transaction_service.handle_terminal_without_validation(
        db, tran_id=str(tran_id), terminal_status="CANCELLED", source="redirect_cancel"
    )
    return RedirectResponse(
        url=f"{settings.FRONTEND_BASE_URL}/billing/trial?tran_id={tran_id}", status_code=status.HTTP_302_FOUND
    )


@router.post("/ipn", include_in_schema=False)
@limiter.limit("60/minute")
async def payment_ipn(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    tran_id = form.get("tran_id")
    val_id = form.get("val_id")
    if not tran_id or not val_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing tran_id or val_id")

    client = get_sslcommerz_client()
    if not client.verify_signature(form):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid IPN signature")

    payment_transaction_service.handle_gateway_callback(
        db, tran_id=str(tran_id), val_id=str(val_id), source="ipn"
    )
    return {"status": "received"}


# ==================== MOCK GATEWAY (dev / billing trial page only) ====================

def _require_mock_mode() -> MockSSLCommerzClient:
    if not settings.SSLCOMMERZ_MOCK_MODE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mock gateway is disabled (SSLCOMMERZ_MOCK_MODE=false)")
    client = get_sslcommerz_client()
    assert isinstance(client, MockSSLCommerzClient)
    return client


_OUTCOME_TO_GATEWAY_STATUS = {"success": "VALID", "fail": "FAILED", "cancel": "CANCELLED"}
_OUTCOME_TO_CALLBACK_PATH = {"success": "success", "fail": "fail", "cancel": "cancel"}


@router.get("/mock-gateway/{tran_id}", response_class=HTMLResponse, include_in_schema=False)
def mock_gateway_page(tran_id: str, db: Session = Depends(get_db)):
    _require_mock_mode()
    txn = payment_transaction_dao.get_by_tran_id(db, tran_id=tran_id)
    if txn is None:
        return HTMLResponse("<h1>Unknown transaction</h1>", status_code=404)
    if txn.status != "INITIATED":
        return HTMLResponse(
            f"<h1>This checkout session already resolved</h1><p>Current status: <b>{txn.status}</b></p>",
            status_code=409,
        )

    action = f"{settings.API_V1_STR}/payments/mock-gateway/{tran_id}/complete"
    return HTMLResponse(f"""
<!doctype html><html><head><meta charset="utf-8"><title>SSLCommerz (Mock)</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 480px; margin: 60px auto; color: #1e1b2e; }}
  .badge {{ display:inline-block; background:#eee; border-radius:6px; padding:2px 8px; font-size:12px; color:#555; }}
  .card {{ border:1px solid #ddd; border-radius:12px; padding:24px; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
  h1 {{ font-size:20px; }}
  .amount {{ font-size:32px; font-weight:700; margin:8px 0 20px; }}
  fieldset {{ border:1px solid #eee; border-radius:8px; padding:12px 16px; margin-bottom:12px; }}
  legend {{ font-weight:600; font-size:13px; color:#555; padding:0 4px; }}
  label {{ display:block; margin:6px 0; font-size:14px; }}
  button {{ width:100%; padding:12px; border-radius:8px; border:none; background:#5b3fa0; color:#fff; font-size:15px; cursor:pointer; }}
  .hint {{ font-size:12px; color:#888; margin-top:4px; }}
</style></head>
<body>
  <span class="badge">MOCK GATEWAY — not the real SSLCommerz</span>
  <div class="card">
    <h1>Complete your payment</h1>
    <div class="amount">{txn.amount} {txn.currency}</div>
    <p style="color:#888;font-size:13px">tran_id: {txn.tran_id}</p>
    <form method="post" action="{action}">
      <fieldset>
        <legend>Outcome</legend>
        <label><input type="radio" name="outcome" value="success" checked> Success</label>
        <label><input type="radio" name="outcome" value="fail"> Fail</label>
        <label><input type="radio" name="outcome" value="cancel"> Cancel</label>
      </fieldset>
      <fieldset>
        <legend>Simulate real-world conditions</legend>
        <label><input type="checkbox" name="risky" value="1"> High-risk transaction (risk_level=1 &rarr; held for review)</label>
        <label><input type="checkbox" name="drop_redirect" value="1"> Drop the browser redirect (app crash / closed tab)</label>
        <div class="hint">With this checked, only the async IPN webhook resolves the transaction — watch the ledger stay INITIATED until it arrives.</div>
      </fieldset>
      <button type="submit">Complete Payment (Simulate)</button>
    </form>
  </div>
</body></html>
""")


async def _fire_mock_ipn(form_body: dict, delay_seconds: float = 2.5) -> None:
    await asyncio.sleep(delay_seconds)
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            await http_client.post(f"{settings.BACKEND_BASE_URL}{settings.API_V1_STR}/payments/ipn", data=form_body)
    except Exception:
        pass  # best-effort — real SSLCommerz IPN delivery isn't guaranteed either; that's what reconciliation is for


@router.post("/mock-gateway/{tran_id}/complete", response_class=HTMLResponse, include_in_schema=False)
async def mock_gateway_complete(
    tran_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    client = _require_mock_mode()
    txn = payment_transaction_dao.get_by_tran_id(db, tran_id=tran_id)
    if txn is None:
        return HTMLResponse("<h1>Unknown transaction</h1>", status_code=404)
    if txn.status != "INITIATED":
        return HTMLResponse(f"<h1>Already resolved: {txn.status}</h1>", status_code=409)

    form = await request.form()
    outcome = form.get("outcome", "success")
    risky = form.get("risky") == "1"
    drop_redirect = form.get("drop_redirect") == "1"

    gateway_status = _OUTCOME_TO_GATEWAY_STATUS.get(str(outcome), "FAILED")
    risk_level = 1 if (risky and gateway_status == "VALID") else 0

    val_id = client.build_val_id(
        tran_id=txn.tran_id, amount=txn.amount, currency=txn.currency, status=gateway_status, risk_level=risk_level
    )
    result = client.validate(val_id)
    form_body = {
        "tran_id": result.tran_id,
        "val_id": result.val_id,
        "amount": str(result.amount),
        "currency": result.currency,
        "status": result.status,
        "risk_level": str(result.risk_level),
        "risk_title": result.risk_title,
        "bank_tran_id": result.bank_tran_id,
        "card_type": result.card_type,
        "verify_sign": result.verify_sign,
        "verify_key": result.verify_key,
    }

    # Channel B (IPN) fires independently of the browser, with a delay — exactly
    # like the real gateway's async webhook. This happens regardless of whether
    # the browser redirect below is dropped.
    background_tasks.add_task(_fire_mock_ipn, form_body)

    if drop_redirect:
        return HTMLResponse("""
<!doctype html><html><body style="font-family:system-ui;max-width:480px;margin:60px auto">
  <h1>Connection dropped (simulated)</h1>
  <p>The browser will not return to the app. In real life this is a closed tab,
  a network drop, or an OS killing the app mid-payment.</p>
  <p>The IPN webhook is still in flight in the background and will resolve this
  transaction shortly — go check the ledger table on the billing trial page.</p>
</body></html>
""")

    action_path = _OUTCOME_TO_CALLBACK_PATH[str(outcome)]
    action_url = f"{settings.BACKEND_BASE_URL}{settings.API_V1_STR}/payments/{action_path}"
    inputs = "\n".join(f'<input type="hidden" name="{k}" value="{v}">' for k, v in form_body.items() if v is not None)
    return HTMLResponse(f"""
<!doctype html><html><body style="font-family:system-ui;max-width:480px;margin:60px auto">
  <p>Redirecting back to the merchant…</p>
  <form id="f" method="post" action="{action_url}">{inputs}</form>
  <script>document.getElementById('f').submit();</script>
</body></html>
""")
