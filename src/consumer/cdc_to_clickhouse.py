import json
import os
import re
import time
from datetime import datetime, timezone

import requests
from kafka import KafkaConsumer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "cdc-sink")
TOPICS_REGEX = os.getenv("KAFKA_TOPICS_REGEX", r"^streamshop\.public\.(customers|products|orders|order_items)$")

CH_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CH_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CH_USER = os.getenv("CLICKHOUSE_USER", "analytics")
CH_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "analytics")
CH_DB = os.getenv("CLICKHOUSE_DATABASE", "analytics")

TABLE_MAP = {
    "customers": f"{CH_DB}.raw_customers",
    "products": f"{CH_DB}.raw_products",
    "orders": f"{CH_DB}.raw_orders",
    "order_items": f"{CH_DB}.raw_order_items",
}

TS_FIELDS = {
    "customers": ["created_at", "updated_at"],
    "products": ["created_at", "updated_at"],
    "orders": ["created_at", "updated_at"],
    "order_items": ["created_at", "updated_at"],
}

def parse_dt(value):
    if value is None:
        return None
    if isinstance(value, str):
        # Common ISO format with Z
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        # assume ms
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
    return value

def ch_insert(table_fqdn: str, rows: list[dict]):
    if not rows:
        return

    # JSONEachRow is convenient for streaming inserts over HTTP
    url = f"http://{CH_HOST}:{CH_PORT}/?query=" + requests.utils.quote(
        f"INSERT INTO {table_fqdn} FORMAT JSONEachRow"
    )
    payload = "\n".join(json.dumps(r, default=str) for r in rows) + "\n"

    resp = requests.post(url, data=payload.encode("utf-8"), auth=(CH_USER, CH_PASSWORD), timeout=10)
    resp.raise_for_status()

def main():
    consumer = KafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP.split(","),
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
        key_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
    )

    consumer.subscribe(pattern=re.compile(TOPICS_REGEX))

    batch = []
    batch_size = 200
    last_flush = time.time()
    flush_every_s = 1.0

    for msg in consumer:
        if msg.value is None:
            continue

        # Handle both formats:
        # - {"payload": {...}} (schemas enabled)
        # - {...} (schemas disabled)
        payload = msg.value.get("payload", msg.value)

        topic = msg.topic
        table = topic.split(".")[-1]
        if table not in TABLE_MAP:
            continue

        op = payload.get("op")  # c/u/d/r
        after = payload.get("after")
        before = payload.get("before")
        ts_ms = payload.get("ts_ms") or payload.get("source", {}).get("ts_ms") or int(time.time() * 1000)

        # Choose the row state to write
        if op in ("c", "u", "r"):
            if after is None:
                continue
            row = dict(after)
            row["_deleted"] = 0
        elif op == "d":
            if before is None:
                # If before is missing, fall back to key for tombstone-like deletes
                if msg.key is None:
                    continue
                row = dict(msg.key)
            else:
                row = dict(before)
            row["_deleted"] = 1
        else:
            # unknown op
            continue

        row["_version"] = int(ts_ms)

        # Normalize timestamp fields for ClickHouse DateTime64 columns
        for f in TS_FIELDS.get(table, []):
            row[f] = parse_dt(row.get(f))

        batch.append(row)

        now = time.time()
        if len(batch) >= batch_size or (now - last_flush) >= flush_every_s:
            ch_insert(TABLE_MAP[table], batch)
            batch.clear()
            last_flush = now

if __name__ == "__main__":
    main()
