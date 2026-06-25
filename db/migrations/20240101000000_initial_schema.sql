-- migrate:up

CREATE TYPE order_status AS ENUM ('pending', 'confirmed', 'failed');

CREATE TABLE orders (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id  VARCHAR(100) NOT NULL,
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    status      order_status NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE inventory (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id  VARCHAR(100) NOT NULL UNIQUE,
    quantity    INTEGER NOT NULL DEFAULT 100 CHECK (quantity >= 0),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO inventory (product_id, quantity) VALUES
    ('PROD-001', 100),
    ('PROD-002', 50),
    ('PROD-003', 200);

-- migrate:down

DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS orders;
DROP TYPE IF EXISTS order_status;