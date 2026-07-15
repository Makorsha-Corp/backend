#!/usr/bin/env python3
"""Sweep payment_transactions stuck in INITIATED past the timeout window and
resolve them directly against SSLCommerz. Safety net for the case where both
the browser redirect and the IPN webhook never arrive (network drop, crash).

Intended to run on a schedule (Railway cron or similar) — safe to run
repeatedly and concurrently with live traffic; each row is re-locked and
re-checked immediately before being acted on.

Usage:
    python scripts/reconcile_payments.py [--older-than-minutes 30] [--limit 200]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.managers.payment_transaction_manager import (  # noqa: E402
    RECONCILE_TIMEOUT_MINUTES,
    payment_transaction_manager,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--older-than-minutes", type=int, default=RECONCILE_TIMEOUT_MINUTES)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        resolved = payment_transaction_manager.reconcile_stuck_transactions(
            db, older_than_minutes=args.older_than_minutes, limit=args.limit
        )
        # Capture display data before commit expires the ORM instances.
        summary = [(txn.tran_id, txn.status) for txn in resolved]
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if not summary:
        print("No stuck transactions found.")
        return 0

    print(f"Reconciled {len(summary)} transaction(s):")
    for tran_id, txn_status in summary:
        print(f"  {tran_id}  ->  {txn_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
