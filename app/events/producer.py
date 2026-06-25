import json
import logging
import os

import stomp

logger = logging.getLogger(__name__)

ACTIVEMQ_HOST = os.getenv("ACTIVEMQ_HOST", "localhost")
ACTIVEMQ_PORT = int(os.getenv("ACTIVEMQ_PORT", "61613"))
ACTIVEMQ_USERNAME = os.getenv("ACTIVEMQ_USERNAME", "admin")
ACTIVEMQ_PASSWORD = os.getenv("ACTIVEMQ_PASSWORD", "admin")


def publish_event(destination: str, payload: dict) -> None:
    conn = stomp.Connection(host_and_ports=[(ACTIVEMQ_HOST, ACTIVEMQ_PORT)])
    conn.connect(ACTIVEMQ_USERNAME, ACTIVEMQ_PASSWORD, wait=True)
    try:
        body = json.dumps(payload)
        conn.send(
            body=body,
            destination=destination,
            headers={"content-type": "application/json"}
        )
        logger.info("Published to %s: %s", destination, body)
    finally:
        conn.disconnect()