CREATE DATABASE IF NOT EXISTS analytics;

-- CDC-friendly raw tables using ReplacingMergeTree(version, deleted)
-- version: monotonically increasing per key (we'll use Debezium event timestamp)
-- deleted: 0/1 marker for deletes

CREATE TABLE IF NOT EXISTS analytics.raw_customers
(
  customer_id UInt64,
  email       String,
  full_name   String,
  created_at  DateTime64(3, 'UTC'),
  updated_at  DateTime64(3, 'UTC'),
  _version    UInt64,
  _deleted    UInt8
)
ENGINE = ReplacingMergeTree(_version, _deleted)
ORDER BY (customer_id);

CREATE TABLE IF NOT EXISTS analytics.raw_products
(
  product_id   UInt64,
  sku          String,
  product_name String,
  category     String,
  price_cents  Int32,
  created_at   DateTime64(3, 'UTC'),
  updated_at   DateTime64(3, 'UTC'),
  _version     UInt64,
  _deleted     UInt8
)
ENGINE = ReplacingMergeTree(_version, _deleted)
ORDER BY (product_id);

CREATE TABLE IF NOT EXISTS analytics.raw_orders
(
  order_id     UInt64,
  customer_id  UInt64,
  status       LowCardinality(String),
  total_cents  Int32,
  currency     FixedString(3),
  created_at   DateTime64(3, 'UTC'),
  updated_at   DateTime64(3, 'UTC'),
  _version     UInt64,
  _deleted     UInt8
)
ENGINE = ReplacingMergeTree(_version, _deleted)
ORDER BY (order_id);

CREATE TABLE IF NOT EXISTS analytics.raw_order_items
(
  order_item_id    UInt64,
  order_id         UInt64,
  product_id       UInt64,
  quantity         Int32,
  unit_price_cents Int32,
  created_at       DateTime64(3, 'UTC'),
  updated_at       DateTime64(3, 'UTC'),
  _version         UInt64,
  _deleted         UInt8
)
ENGINE = ReplacingMergeTree(_version, _deleted)
ORDER BY (order_item_id);
