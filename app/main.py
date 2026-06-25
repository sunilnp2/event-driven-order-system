import logging
import os
import time

from fastapi import FastAPI

from app.api.orders import router as orders_router
from app.consumers.inventory_consumer import start_inventory_consumer
from app.consumers.notification_consumer import start_notification_consumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ACTIVEMQ_HOST = os.getenv("ACTIVEMQ_HOST", "localhost")
ACTIVEMQ_PORT = int(os.getenv("ACTIVEMQ_PORT", "61613"))
ACTIVEMQ_USERNAME = os.getenv("ACTIVEMQ_USERNAME", "admin")
ACTIVEMQ_PASSWORD = os.getenv("ACTIVEMQ_PASSWORD", "admin")

app = FastAPI(title="EDA Order System", version="1.0.0")
app.include_router(orders_router)

_consumer_connections = []


def _start_with_retry(start_fn, retries: int = 10, delay: int = 3):
    for attempt in range(1, retries + 1):
        try:
            conn = start_fn(ACTIVEMQ_HOST, ACTIVEMQ_PORT, ACTIVEMQ_USERNAME, ACTIVEMQ_PASSWORD)
            return conn
        except Exception as e:
            logger.warning(
                "Consumer connect attempt %d/%d failed: %s", attempt, retries, e
            )
            if attempt < retries:
                time.sleep(delay)
    raise RuntimeError(f"Could not connect consumer after {retries} attempts")


@app.on_event("startup")
def startup_event():
    logger.info("Starting consumers...")
    inv_conn = _start_with_retry(start_inventory_consumer)
    notif_conn = _start_with_retry(start_notification_consumer)
    _consumer_connections.extend([inv_conn, notif_conn])
    logger.info("Both consumers are running.")


@app.on_event("shutdown")
def shutdown_event():
    logger.info("Shutting down consumers...")
    for conn in _consumer_connections:
        try:
            conn.disconnect()
        except Exception:
            pass
    logger.info("Consumers disconnected.")