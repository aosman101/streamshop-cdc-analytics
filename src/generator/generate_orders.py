import os
import random
import time
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import Json
from faker import Faker

fake = Faker()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "streamshop")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

STATUSES = ["created", "paid", "shipped", "delivered", "cancelled"]
CHANNELS = ["web", "mobile", "store", "social"]

def now_utc():
    return datetime.now(timezone.utc)

def get_conn():
    return psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD,
    )

def seed_reference_data(cur, n_customers=50, n_products=30):
    # Customers
    cur.execute("SELECT count(*) FROM customers;")
    if cur.fetchone()[0] < n_customers:
        for _ in range(n_customers):
            cur.execute(
                """
                INSERT INTO customers (email, full_name, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (email) DO NOTHING;
                """,
                (fake.unique.email(), fake.name(), now_utc(), now_utc()),
            )

    # Products
    cur.execute("SELECT count(*) FROM products;")
    if cur.fetchone()[0] < n_products:
        for _ in range(n_products):
            cur.execute(
                """
                INSERT INTO products (sku, product_name, category, price_cents, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (sku) DO NOTHING;
                """,
                (
                    fake.unique.bothify(text="SKU-#####"),
                    fake.word().title(),
                    random.choice(["fitness", "tech", "home", "food"]),
                    random.randint(199, 19999),
                    now_utc(),
                    now_utc(),
                ),
            )

def create_order(cur):
    cur.execute("SELECT customer_id FROM customers ORDER BY random() LIMIT 1;")
    customer_id = cur.fetchone()[0]

    cur.execute("SELECT product_id, price_cents FROM products ORDER BY random() LIMIT 3;")
    picks = cur.fetchall()

    total = 0
    items = []
    for product_id, price in picks:
        qty = random.randint(1, 3)
        total += price * qty
        items.append((product_id, qty, price))

    now_ts = now_utc()
    channel = random.choice(CHANNELS)

    cur.execute(
        """
        INSERT INTO orders (customer_id, status, total_cents, currency, channel, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING order_id;
        """,
        (customer_id, "created", total, "GBP", channel, now_ts, now_ts),
    )
    order_id = cur.fetchone()[0]

    for product_id, qty, price in items:
        cur.execute(
            """
            INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (order_id, product_id, qty, price, now_ts, now_ts),
        )

    emit_outbox_event(
        cur,
        aggregate_type="order",
        aggregate_id=order_id,
        event_type="order_created",
        payload={
            "customer_id": customer_id,
            "status": "created",
            "total_cents": total,
            "currency": "GBP",
            "channel": channel,
            "items": [
                {"product_id": pid, "quantity": qty, "unit_price_cents": price} for pid, qty, price in items
            ],
            "created_at": now_ts.isoformat(),
        },
    )

def randomly_update_order(cur):
    cur.execute("SELECT order_id, status FROM orders ORDER BY random() LIMIT 1;")
    row = cur.fetchone()
    if not row:
        return
    order_id, status = row

    new_status = random.choice(STATUSES)
    if new_status == status:
        return

    new_ts = now_utc()

    cur.execute(
        """
        UPDATE orders
        SET status = %s, updated_at = %s
        WHERE order_id = %s;
        """,
        (new_status, new_ts, order_id),
    )

    emit_outbox_event(
        cur,
        aggregate_type="order",
        aggregate_id=order_id,
        event_type="order_status_updated",
        payload={
            "previous_status": status,
            "new_status": new_status,
            "updated_at": new_ts.isoformat(),
        },
    )

def randomly_update_product_price(cur):
    cur.execute("SELECT product_id, price_cents FROM products ORDER BY random() LIMIT 1;")
    row = cur.fetchone()
    if not row:
        return
    product_id, price = row
    delta = random.randint(-200, 500)
    new_price = max(99, price + delta)

    new_ts = now_utc()

    cur.execute(
        """
        UPDATE products
        SET price_cents = %s, updated_at = %s
        WHERE product_id = %s;
        """,
        (new_price, new_ts, product_id),
    )

    emit_outbox_event(
        cur,
        aggregate_type="product",
        aggregate_id=product_id,
        event_type="product_price_changed",
        payload={
            "previous_price_cents": price,
            "new_price_cents": new_price,
            "updated_at": new_ts.isoformat(),
        },
    )

def emit_outbox_event(cur, aggregate_type: str, aggregate_id: int, event_type: str, payload: dict):
    cur.execute(
        """
        INSERT INTO outbox_events (aggregate_type, aggregate_id, event_type, payload, created_at)
        VALUES (%s, %s, %s, %s, %s);
        """,
        (aggregate_type, aggregate_id, event_type, Json(payload), now_utc()),
    )

def main():
    with get_conn() as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            seed_reference_data(cur)
        conn.commit()

    while True:
        with get_conn() as conn:
            conn.autocommit = False
            with conn.cursor() as cur:
                action = random.random()
                if action < 0.70:
                    create_order(cur)
                elif action < 0.90:
                    randomly_update_order(cur)
                else:
                    randomly_update_product_price(cur)
            conn.commit()

        time.sleep(1.0)

if __name__ == "__main__":
    main()
