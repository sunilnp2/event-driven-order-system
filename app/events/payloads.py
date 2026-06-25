from pydantic import BaseModel


class OrderCreatedEvent(BaseModel):
    event_type: str = "OrderCreated"
    order_id: str
    product_id: str
    quantity: int
    created_at: str


class InventoryUpdatedEvent(BaseModel):
    event_type: str = "InventoryUpdated"
    order_id: str
    product_id: str
    quantity_deducted: int
    remaining_quantity: int
    updated_at: str