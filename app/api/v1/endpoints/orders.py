"""Order endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user
from app.models.profile import Profile
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse
from app.services.order_service import order_service


router = APIRouter()


@router.get("/", response_model=List[OrderResponse])
def get_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get all orders with pagination

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of orders
    """
    orders = order_service.get_orders(db, skip=skip, limit=limit)
    return orders


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get order by ID

    Args:
        order_id: Order ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Order data

    Raises:
        HTTPException: If order not found
    """
    try:
        order = order_service.get_order(db, order_id)
        return order
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/", response_model=OrderResponse, status_code=201)
def create_order(
    order_in: OrderCreate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Create new order

    Args:
        order_in: Order creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created order
    """
    try:
        order = order_service.create_order(db, order_in, current_user)
        return order
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: int,
    order_in: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Update order

    Args:
        order_id: Order ID
        order_in: Order update data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated order

    Raises:
        HTTPException: If order not found
    """
    try:
        order = order_service.update_order(db, order_id, order_in, current_user)
        return order
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{order_id}", status_code=204)
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Delete order

    Args:
        order_id: Order ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If order not found
    """
    try:
        order_service.delete_order(db, order_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
