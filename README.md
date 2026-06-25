
---
Project Structure
```aiignore
eda-order-system/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── db/
│   └── migrations/
│       └── 20240101000000_initial_schema.sql
└── app/
    ├── __init__.py
    ├── main.py
    ├── database/
    │   ├── __init__.py
    │   └── session.py
    ├── models/
    │   ├── __init__.py
    │   ├── order.py
    │   └── inventory.py
    ├── schemas/
    │   ├── __init__.py
    │   └── order.py
    ├── events/
    │   ├── __init__.py
    │   ├── payloads.py
    │   └── producer.py
    ├── consumers/
    │   ├── __init__.py
    │   ├── inventory_consumer.py
    │   └── notification_consumer.py
    ├── api/
    │   ├── __init__.py
    │   └── orders.py
    └── services/
        ├── __init__.py
        └── order_service.py
```
## Running the Project

```markdown

To spin up the entire infrastructure and test the event-driven system, follow these steps.

### Build and Start Infrastructure
Run the following command to build and start all Docker containers (FastAPI, PostgreSQL, and ActiveMQ) in the foreground:
```bash
docker compose up --build

```

### Simulating an Order Flow

Open a separate terminal window and execute the following commands to interact with the system.

1. **Create a new order:**
```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"product_id": "PROD-001", "quantity": 5}'

```


2. **Check the order status** (Replace `<order-id>` with the UUID returned from the previous command):
```bash
curl http://localhost:8000/orders/<order-id>

```



### Web Consoles & Documentation

* **ActiveMQ Web Console:** [http://localhost:8161](https://www.google.com/search?q=http://localhost:8161)
* *Username:* `admin` | *Password:* `admin`


* **Interactive API Docs (Swagger UI):** [http://localhost:8000/docs](https://www.google.com/search?q=http://localhost:8000/docs)

---

## Event Flow Walkthrough

Here is exactly what happens behind the scenes when a client triggers the `POST /orders` endpoint.

```
[ Client ] ---> ( FastAPI ) ---> [ PostgreSQL (Pending) ]
                    |
                    v
               ( ActiveMQ ) ---> [ InventoryListener ] ---> [ PostgreSQL (Confirmed) ]
                                        |
                                        v
                                   ( ActiveMQ ) ---------> [ NotificationListener ]

```

### Step 1 — HTTP Request Arrives

The client sends a `POST` request to `/orders` with the following payload:

```json
{
  "product_id": "PROD-001",
  "quantity": 5
}

```

FastAPI routes the request to `create_order_endpoint`. Pydantic v2 validates the request body against the `OrderCreateRequest` schema. If `quantity <= 0` or `product_id` is empty, FastAPI immediately short-circuits and returns a `422 Unprocessable Entity` status.

### Step 2 — Order Saved to PostgreSQL

If validation passes, the order is initialized with a `pending` state and committed to the database:

```python
order = Order(product_id="PROD-001", quantity=5, status=OrderStatus.pending)
db.add(order)
db.commit()

```

A new row is inserted into the `orders` table. Calling `db.refresh(order)` loads the automatically generated database UUID back into the Python object.

### Step 3 — `OrderCreated` Event Published

An event payload is constructed and published asynchronously:

```python
event = OrderCreatedEvent(
    order_id=str(order.id),
    product_id="PROD-001",
    quantity=5,
    created_at="2024-01-01T00:00:00+00:00"
)
publish_event("/queue/order.created", event.model_dump())

```

The `publish_event` utility opens a STOMP connection to ActiveMQ, dispatches the JSON-serialized payload to `/queue/order.created`, and immediately disconnects. At this exact point, the HTTP response is returned to the client with `status: pending`.

### Step 4 — `InventoryListener` Receives the Event

ActiveMQ delivers the message to the `InventoryListener`. This worker executes inside `stomp.py`'s background thread, completely decoupled from the original HTTP request lifecycle. The raw JSON string resides inside `frame.body`.

### Step 5 — Inventory Updated in PostgreSQL

The listener queries the database, checks current stock levels, and updates the inventory state:

```python
# Query inventory (Assume initial stock quantity was 100)
inventory = db.query(Inventory).filter(Inventory.product_id == "PROD-001").first()

# Deduct stock and confirm order status
inventory.quantity -= 5   # now 95
inventory.updated_at = now
order.status = OrderStatus.confirmed

db.commit()

```

Both modifications occur atomically inside a single database transaction block: the stock count drops to `95`, and the order status updates to `confirmed`.

### Step 6 — `InventoryUpdated` Event Published

Upon successful database commitment, an downstream event is dispatched:

```python
updated_event = InventoryUpdatedEvent(
    order_id="...",
    product_id="PROD-001",
    quantity_deducted=5,
    remaining_quantity=95,
    updated_at="2024-01-01T00:00:01+00:00"
)
publish_event("/queue/inventory.updated", updated_event.model_dump())

```

This re-uses the core STOMP publishing flow to alert downstream services.

### Step 7 — `NotificationListener` Receives the Event

ActiveMQ pushes the message payload from `/queue/inventory.updated` straight out to the `NotificationListener`.

### Step 8 — Notification Logged

The notification worker parses the event structure and writes it to standard output:

```text
[NOTIFICATION] Order abc-123 confirmed. Product 'PROD-001': deducted 5 units, remaining stock: 95.

```

> **Note:** This specific consumer is entirely read-only and performs no database state updates.

#### Final Database State:

* **`orders` table:** `id=abc-123`, `product_id=PROD-001`, `quantity=5`, `status=confirmed`
* **`inventory` table:** `product_id=PROD-001`, `quantity=95`

---

## Production Basics

Moving from a local proof-of-concept to a production environment requires structural improvements to handle failure states gracefully.

### Message Acknowledgement

By default, this development setup relies on `ack="auto"`, meaning ActiveMQ treats a message as successfully processed the millisecond it delivers it to a worker thread. If your service worker crashes mid-execution inside `on_message`, **the message is permanently lost.**

In production environments, you must shift to manual client acknowledgements:

```python
# Subscribe to the queue with client-side management
conn.subscribe(destination=queue, id=1, ack="client")

# Explicitly acknowledge the frame ONLY after successful execution:
conn.ack(frame.headers["message-id"], subscription_id=1)

```

If your consumer process dies abruptly prior to issuing `conn.ack()`, ActiveMQ detects the connection drop and safely queues the message back up for redelivery.

### Retry Handling

ActiveMQ features native redelivery policies. If an item fails processing or is left unacknowledged, ActiveMQ attempts redelivery $N$ times with a configurable backoff mechanism (e.g., exponential backoff).

On your application consumer side, catch errors cleanly using a `try/except` block, allowing you to explicitly negative-acknowledge (`nack`) the message or drop the execution thread to force a retry loop.

### Dead Letter Queue (DLQ)

When a poisoned message exceeds its maximum redelivery threshold ($N$ times), ActiveMQ moves it to a system-wide isolation zone, defaulting to `/queue/ActiveMQ.DLQ`.

* **Production Best Practice:** Configure per-queue DLQs (e.g., `/queue/order.created.DLQ`), monitor the overall depth of these queues closely, and configure alerts to notify developers to inspect payloads, patch underlying bugs, and manually replay messages.

### Idempotency

Our basic project contains no native idempotency layer. If network hiccups cause an `InventoryUpdated` event to deliver twice, your application will deduct the inventory twice.

To build an idempotent system, append a unique `event_id` (UUID) to every single outbound event payload and maintain a dedicated tracking layer in your database:

```sql
CREATE TABLE processed_events (
    event_id UUID PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

```

#### The Idempotent Worker Design Pattern:

1. Receive incoming event message.
2. Read the embedded `event_id`.
3. Check the `processed_events` table.
4. **If found:** Discard the message immediately and call `ack()` safely (it was already processed).
5. **If not found:** Process the business logic, insert the row tracking data, commit your transaction, and call `ack()`.

```

```