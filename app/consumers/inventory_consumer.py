import json
import logging
import uuid
from datetime import datetime, timezone

import stomp

from app.database.session import SessionLocal
from app.events.payloads import InventoryUpdatedEvent, OrderCreatedEvent
from app.events.producer import publish_event
from app.models.inventory import Inventory
from app.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)

ORDER_CREATED_QUEUE = "/queue/order.created"
INVENTORY_UPDATED_QUEUE = "/queue/inventory.updated"


class InventoryListener(stomp.ConnectionListener):

    def on_error(self, frame):
        logger.error("InventoryConsumer error: %s", frame.body)

    def on_message(self, frame):
        logger.info("InventoryConsumer received: %s", frame.body)
        try:
            data = json.loads(frame.body)
            event = OrderCreatedEvent(**data)
            self._process(event)
        except Exception as e:
            logger.error("InventoryConsumer failed to process message: %s", e)

    def _process(self, event: OrderCreatedEvent) -> None:
        db = SessionLocal()
        try:
            inventory = (
                db.query(Inventory)
                .filter(Inventory.product_id == event.product_id)
                .first()
            )

            if not inventory:
                logger.warning("No inventory record for product: %s", event.product_id)
                self._set_order_status(db, event.order_id, OrderStatus.failed)
                return

            if inventory.quantity < event.quantity:
                logger.warning(
                    "Insufficient stock for product %s: have %d, need %d",
                    event.product_id, inventory.quantity, event.quantity
                )
                self._set_order_status(db, event.order_id, OrderStatus.failed)
                return

            inventory.quantity -= event.quantity
            inventory.updated_at = datetime.now(timezone.utc)

            order = db.query(Order).filter(Order.id == uuid.UUID(event.order_id)).first()
            if order:
                order.status = OrderStatus.confirmed

            db.commit()
            logger.info(
                "Inventory updated for %s. Remaining: %d",
                event.product_id, inventory.quantity
            )

            updated_event = InventoryUpdatedEvent(
                order_id=event.order_id,
                product_id=event.product_id,
                quantity_deducted=event.quantity,
                remaining_quantity=inventory.quantity,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            publish_event(INVENTORY_UPDATED_QUEUE, updated_event.model_dump())

        except Exception as e:
            db.rollback()
            logger.error("InventoryConsumer DB error: %s", e)
        finally:
            db.close()

    def _set_order_status(self, db, order_id: str, status: OrderStatus) -> None:
        order = db.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
        if order:
            order.status = status
            db.commit()


def start_inventory_consumer(
    host: str, port: int, username: str, password: str
) -> stomp.Connection:
    conn = stomp.Connection(host_and_ports=[(host, port)])
    conn.set_listener("inventory_listener", InventoryListener())
    conn.connect(username, password, wait=True)
    conn.subscribe(destination=ORDER_CREATED_QUEUE, id=1, ack="auto")
    logger.info("InventoryConsumer subscribed to %s", ORDER_CREATED_QUEUE)
    return conn