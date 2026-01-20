-- Core OLTP schema (normalized) for a tiny e-commerce app.

CREATE TABLE IF NOT EXISTS customers (
  customer_id BIGSERIAL PRIMARY KEY,
  email       TEXT NOT NULL UNIQUE,
  full_name   TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
  product_id       BIGSERIAL PRIMARY KEY,
  sku              TEXT NOT NULL UNIQUE,
  product_name     TEXT NOT NULL,
  category         TEXT NOT NULL,
  price_cents      INT  NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
  order_id     BIGSERIAL PRIMARY KEY,
  customer_id  BIGINT NOT NULL REFERENCES customers(customer_id),
  status       TEXT NOT NULL,
  total_cents  INT  NOT NULL,
  currency     TEXT NOT NULL DEFAULT 'GBP',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_items (
  order_item_id    BIGSERIAL PRIMARY KEY,
  order_id         BIGINT NOT NULL REFERENCES orders(order_id),
  product_id       BIGINT NOT NULL REFERENCES products(product_id),
  quantity         INT NOT NULL,
  unit_price_cents INT NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional but useful for delete events (captures full row state)
ALTER TABLE customers    REPLICA IDENTITY FULL;
ALTER TABLE products     REPLICA IDENTITY FULL;
ALTER TABLE orders       REPLICA IDENTITY FULL;
ALTER TABLE order_items  REPLICA IDENTITY FULL;

-- Publication for pgoutput (Debezium will read from this publication)
DROP PUBLICATION IF EXISTS dbz_publication;
CREATE PUBLICATION dbz_publication FOR TABLE
  customers, products, orders, order_items;
