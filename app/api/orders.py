import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.order import Order
from app.schemas.order import OrderCreateRequest, OrderResponse
from app.services.order_service import create_order

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/", response_model=OrderResponse, status_code=201)
def create_order_endpoint(
    request: OrderCreateRequest,
    db: Session = Depends(get_db),
):
    order = create_order(db, request)
    return order


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_endpoint(order_id: str, db: Session = Depends(get_db)):
    try:
        parsed_id = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    order = db.query(Order).filter(Order.id == parsed_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order