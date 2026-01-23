import json
import os
import re
import time
from datetime import datetime, timezone

import requests
from confluent_kafka import KafkaError
from confluent_kafka.avro import AvroConsumer, SerializerError

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "cdc-sink")
TOPICS_REGEX = os.getenv(
    "KAFKA_TOPICS_REGEX", r"^streamshop\.public\.(customers|products|orders|order_items|outbox_events)$"
)
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:18081")

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
    "outbox_events": f"{CH_DB}.raw_outbox_events",
}

TS_FIELDS = {
    "customers": ["created_at", "updated_at"],
    "products": ["created_at", "updated_at"],
    "orders": ["created_at", "updated_at"],
    "order_items": ["created_at", "updated_at"],
    "outbox_events": ["created_at"],
}

def parse_dt(value):
    if value is None:
        return None
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
    return value

def ch_insert(table_fqdn: str, rows: list[dict]):
    if not rows:
        return

    url = f"http://{CH_HOST}:{CH_PORT}/?query=" + requests.utils.quote(
        f"INSERT INTO {table_fqdn} FORMAT JSONEachRow"
    )
    payload = "\n".join(json.dumps(r, default=str) for r in rows) + "\n"

    resp = requests.post(url, data=payload.encode("utf-8"), auth=(CH_USER, CH_PASSWORD), timeout=10)
    resp.raise_for_status()

def get_consumer():
    consumer_conf = {
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
        "schema.registry.url": SCHEMA_REGISTRY_URL,
        "enable.auto.commit": True,
    }
    consumer = AvroConsumer(consumer_conf)
    consumer.subscribe([TOPICS_REGEX])
    return consumer

def normalize_payload(record: dict, table: str, key: dict | None) -> dict | None:
    # Debezium envelope with Avro converter
    if record is None:
        return None

    op = record.get("op")
    after = record.get("after")
    before = record.get("before")
    ts_ms = record.get("ts_ms") or record.get("source", {}).get("ts_ms") or int(time.time() * 1000)

    if op in ("c", "u", "r"):
        if after is None:
            return None
        row = dict(after)
        row["_deleted"] = 0
    elif op == "d":
        row = dict(before or key or {})
        row["_deleted"] = 1
    else:
        return None

    row["_version"] = int(ts_ms)

    for f in TS_FIELDS.get(table, []):
        row[f] = parse_dt(row.get(f))

    if table == "outbox_events":
        payload_val = row.get("payload")
        if isinstance(payload_val, dict):
            row["payload"] = json.dumps(payload_val)
        elif payload_val is None:
            row["payload"] = ""
    return row

def main():
    consumer = get_consumer()

    batches: dict[str, list[dict]] = {}
    batch_size = 200
    last_flush: dict[str, float] = {}
    flush_every_s = 1.0

    try:
        while True:
            try:
                msg = consumer.poll(1.0)
            except SerializerError as e:
                print(f"Serializer error: {e}")
                continue

            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"Kafka error: {msg.error()}")
                continue

            value = msg.value()
            topic = msg.topic()
            table = topic.split(".")[-1]
            if table not in TABLE_MAP:
                continue

            record = value.get("payload", value)
            row = normalize_payload(record, table, msg.key())
            if not row:
                continue

            table_batch = batches.setdefault(table, [])
            table_batch.append(row)

            now = time.time()
            last_flush.setdefault(table, now)

            if len(table_batch) >= batch_size or (now - last_flush[table]) >= flush_every_s:
                ch_insert(TABLE_MAP[table], table_batch)
                table_batch.clear()
                last_flush[table] = now
    finally:
        # Flush any remaining rows
        for table, rows in batches.items():
            if rows:
                ch_insert(TABLE_MAP[table], rows)
        consumer.close()

if __name__ == "__main__":
    main()
