import json
import logging

import stomp

from app.events.payloads import InventoryUpdatedEvent

logger = logging.getLogger(__name__)

INVENTORY_UPDATED_QUEUE = "/queue/inventory.updated"


class NotificationListener(stomp.ConnectionListener):

    def on_error(self, frame):
        logger.error("NotificationConsumer error: %s", frame.body)

    def on_message(self, frame):
        logger.info("NotificationConsumer received: %s", frame.body)
        try:
            data = json.loads(frame.body)
            event = InventoryUpdatedEvent(**data)
            self._notify(event)
        except Exception as e:
            logger.error("NotificationConsumer failed to process message: %s", e)

    def _notify(self, event: InventoryUpdatedEvent) -> None:
        logger.info(
            "[NOTIFICATION] Order %s confirmed. "
            "Product '%s': deducted %d units, remaining stock: %d.",
            event.order_id,
            event.product_id,
            event.quantity_deducted,
            event.remaining_quantity,
        )


def start_notification_consumer(
    host: str, port: int, username: str, password: str
) -> stomp.Connection:
    conn = stomp.Connection(host_and_ports=[(host, port)])
    conn.set_listener("notification_listener", NotificationListener())
    conn.connect(username, password, wait=True)
    conn.subscribe(destination=INVENTORY_UPDATED_QUEUE, id=1, ack="auto")
    logger.info("NotificationConsumer subscribed to %s", INVENTORY_UPDATED_QUEUE)
    return conn