"""Parse optional numeric copies for production step condition values."""
from decimal import Decimal, InvalidOperation
from typing import Optional


def optional_numeric_from_text(value: Optional[str]) -> Optional[Decimal]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None
