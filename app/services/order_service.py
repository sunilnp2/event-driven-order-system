import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.events.payloads import OrderCreatedEvent
from app.events.producer import publish_event
from app.models.order import Order, OrderStatus
from app.schemas.order import OrderCreateRequest

logger = logging.getLogger(__name__)

ORDER_CREATED_QUEUE = "/queue/order.created"


def create_order(db: Session, request: OrderCreateRequest) -> Order:
    order = Order(
        product_id=request.product_id,
        quantity=request.quantity,
        status=OrderStatus.pending,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    logger.info("Order saved to DB: %s", order.id)

    event = OrderCreatedEvent(
        order_id=str(order.id),
        product_id=order.product_id,
        quantity=order.quantity,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    publish_event(ORDER_CREATED_QUEUE, event.model_dump())
    logger.info("OrderCreated event published for order: %s", order.id)

    return order