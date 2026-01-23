# streamshop-cdc-analytics

[![Postgres](https://img.shields.io/badge/Postgres-14%2B-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/) [![Debezium](https://img.shields.io/badge/Debezium-CDC-E2492F?logo=apachekafka&logoColor=white)](https://debezium.io/) [![Redpanda](https://img.shields.io/badge/Redpanda-Kafka_API-EE1F26?logo=redpanda&logoColor=white)](https://redpanda.com/) [![ClickHouse](https://img.shields.io/badge/ClickHouse-OLAP-FFCC01?logo=clickhouse&logoColor=000)](https://clickhouse.com/) [![dbt](https://img.shields.io/badge/dbt-Models-FF694B?logo=dbt&logoColor=white)](https://www.getdbt.com/) [![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/) [![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)

Hands-on, production-style Change Data Capture (CDC) analytics stack for streaming OLTP changes into ClickHouse and modelling them with dbt.
**Postgres (OLTP) → Debezium (CDC) → Redpanda (Kafka API) → ClickHouse (OLAP) → dbt (marts + tests) → CI**

## Why this repo exists
- Demonstrate a realistic CDC ingestion pattern (upserts and deletes) instead of batch pulls.
- Show how to land CDC into ClickHouse using ReplacingMergeTree with `_version` and `_deleted`.
- Provide dbt models/tests for analytics-ready marts on top of streaming sinks.
- Make the whole workflow reproducible locally with Docker Compose.

## MVP (what you get out of the box)
- Local CDC pipeline from Postgres → Debezium → Redpanda → ClickHouse → dbt, fully containerized.
- dbt build + tests wired to CI for fast feedback.

## Stretch goals implemented
- Schema registry + contracts: Debezium emits Avro via Redpanda’s schema registry (http://localhost:18081/subjects), and dbt contracts enforce model schemas so evolution is explicit end-to-end (example: new `orders.channel` column flows through ClickHouse + dbt).
- Outbox pattern: Postgres now writes domain events to `outbox_events`, Debezium streams `streamshop.public.outbox_events`, and the CDC sink lands them in `analytics.raw_outbox_events` + `stg_outbox_events`.
- dbt snapshots: SCD2 snapshot of product prices (`product_price_scd2`) tracks price history in ClickHouse using `dbt snapshot`.

## How it flows
```
Postgres (Faker workload + outbox_events)
  └─ Debezium + Kafka Connect (Avro + Schema Registry) → Redpanda topics (streamshop.public.*)
       ├─ Python CDC sink → ClickHouse analytics.raw_* (ReplacingMergeTree)
       └─ Outbox events → ClickHouse analytics.raw_outbox_events
            └─ dbt → staging views + marts + snapshot (product_price_scd2)
```

## Services and ports
| Service | Purpose | Ports / URL |
| --- | --- | --- |
| Postgres | OLTP source with logical replication enabled | 5432 |
| Debezium Connect | Kafka Connect worker for CDC | 8083 |
| Redpanda broker | Kafka API compatible broker | 19092 (PLAINTEXT) |
| Schema Registry (Redpanda) | Avro/JSON/Protobuf schemas for topics | http://localhost:18081 |
| Redpanda Console | UI for topics/consumers | http://localhost:8080 |
| ClickHouse | OLAP warehouse target | 8123 (HTTP), 9000 (native) |
| generator | Faker workload that keeps writing orders | runs headless |
| cdc-sink | Python consumer upserting CDC into ClickHouse | runs headless |

## Project layout
- `docker-compose.yml` — brings up Postgres, Debezium Connect, Redpanda, ClickHouse, generator, and CDC sink.
- `docker/postgres/init` — OLTP schema plus Debezium publication and replication user.
- `docker/clickhouse/init` — raw `_version`/`_deleted` tables using ReplacingMergeTree.
- `connectors/postgres-source.json` — Debezium connector config (pgoutput, five tables including outbox events).
- `scripts/register_connector.sh` — helper to register the connector once Connect is healthy.
- `src/generator` — Faker workload that creates/updates orders, adjusts prices, and writes domain events into `outbox_events`.
- `src/consumer` — Kafka consumer (Avro + schema registry) that normalizes Debezium events and writes JSONEachRow to ClickHouse.
- `dbt/streamshop` — sources, staging views, marts (`dim_customers`, `fct_orders`), outbox staging, and SCD2 snapshot of product prices.
- `dbt/streamshop/snapshots` — dbt snapshot definitions (product price SCD2).

## Quickstart
1) **Start the platform**
```bash
docker compose up -d --build
```
The generator and CDC sink containers will start automatically once dependencies are healthy.
If you previously ran an older version, do a clean start first: `docker compose down -v`.

2) **Register the Debezium connector** (wait until `connect` is up)
```bash
./scripts/register_connector.sh
```
The script polls `CONNECT_URL` (defaults to http://localhost:8083) before posting the config in `connectors/postgres-source.json`. Debezium is configured with Avro converters and Redpanda’s schema registry, so schemas will appear under `http://localhost:18081/subjects`.

3) **Watch the data flow**
- Redpanda Console: open http://localhost:8080 and inspect `streamshop.public.*` topics.
- Schema Registry: verify schemas at http://localhost:18081/subjects.
- Postgres check: `docker exec -it postgres psql -U postgres -d streamshop -c "select status, count(*) from orders group by 1 order by 2 desc;"`
- ClickHouse check: `docker exec -it clickhouse clickhouse-client -u analytics --password analytics -q "select order_id, status, _deleted, _version from analytics.raw_orders order by _version desc limit 10;"`.
- Outbox events: `docker exec -it clickhouse clickhouse-client -u analytics --password analytics -q "select event_type, count(*) from analytics.raw_outbox_events group by event_type;"`.

4) **Build analytics with dbt** (run locally)
```bash
pip install "dbt-core~=1.8" "dbt-clickhouse"
cd dbt/streamshop
DBT_PROFILES_DIR=$(pwd) dbt deps
DBT_PROFILES_DIR=$(pwd) dbt build
```
Profiles point at the ClickHouse container (`analytics` user/password). `dbt build` will materialize staging views and marts on top of the CDC raw tables.

5) **Run the SCD2 snapshot (product price history)**
```bash
cd dbt/streamshop
DBT_PROFILES_DIR=$(pwd) dbt snapshot --select product_price_scd2
```
Query history: `docker exec -it clickhouse clickhouse-client -u analytics --password analytics -q "select product_id, price_cents, dbt_valid_from, dbt_valid_to from analytics.product_price_scd2 order by product_id, dbt_valid_from limit 20;"`.

6) **Tear down when done**
```bash
docker compose down -v
```

## CDC/raw table design
- Debezium captures inserts/updates/deletes from Postgres tables: `customers`, `products`, `orders`, `order_items`, `outbox_events`.
- The Python sink consumes Avro with Redpanda’s schema registry, batches CDC events, maps topics to ClickHouse `analytics.raw_*` tables, and writes with `JSONEachRow`.
- Raw tables use `ReplacingMergeTree(_version, _deleted)` so newer versions replace old ones and tombstones are preserved.
- dbt staging filters `_deleted = 0` to expose only current rows; marts are built on top of those staging views.
- Contracts: dbt model contracts are enabled with explicit column data types; schema changes become visible/managed instead of silent.

Happy streaming!
