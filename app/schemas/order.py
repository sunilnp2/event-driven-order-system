import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.order import OrderStatus


class OrderCreateRequest(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(..., gt=0)


class OrderResponse(BaseModel):
    id: uuid.UUID
    product_id: str
    quantity: int
    status: OrderStatus
    created_at: datetime

    model_config = {"from_attributes": True}