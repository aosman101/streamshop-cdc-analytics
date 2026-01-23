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

## After-MVP ideas
- Schema registry + contracts: show schema evolution handling (new column in Postgres → Debezium → sink → ClickHouse → dbt contracts). Redpanda Console in this single-broker setup already exposes schema registry endpoints you can lean on.
- Outbox pattern: add an `outbox_events` table in Postgres and route domain events separately for microservice-friendly integrations.
- dbt snapshots: implement SCD2 for product price changes using dbt-clickhouse snapshots.

## How it flows
```
Postgres (Faker workload)
  └─ Debezium + Kafka Connect → Redpanda topics (streamshop.public.*)
       └─ Python CDC sink → ClickHouse analytics.raw_* (ReplacingMergeTree)
            └─ dbt → staging views + marts
```

## Services and ports
| Service | Purpose | Ports / URL |
| --- | --- | --- |
| Postgres | OLTP source with logical replication enabled | 5432 |
| Debezium Connect | Kafka Connect worker for CDC | 8083 |
| Redpanda broker | Kafka API compatible broker | 19092 (PLAINTEXT) |
| Redpanda Console | UI for topics/consumers | http://localhost:8080 |
| ClickHouse | OLAP warehouse target | 8123 (HTTP), 9000 (native) |
| generator | Faker workload that keeps writing orders | runs headless |
| cdc-sink | Python consumer upserting CDC into ClickHouse | runs headless |

## Project layout
- `docker-compose.yml` — brings up Postgres, Debezium Connect, Redpanda, ClickHouse, generator, and CDC sink.
- `docker/postgres/init` — OLTP schema plus Debezium publication and replication user.
- `docker/clickhouse/init` — raw `_version`/`_deleted` tables using ReplacingMergeTree.
- `connectors/postgres-source.json` — Debezium connector config (pgoutput, four tables).
- `scripts/register_connector.sh` — helper to register the connector once Connect is healthy.
- `src/generator` — Faker workload that creates/updates orders and product prices.
- `src/consumer` — Kafka consumer that normalizes Debezium events and writes JSONEachRow to ClickHouse.
- `dbt/streamshop` — sources, staging views, and marts (`dim_customers`, `fct_orders`).

## Quickstart
1) **Start the platform**
```bash
docker compose up -d --build
```
The generator and CDC sink containers will start automatically once dependencies are healthy.

2) **Register the Debezium connector** (wait until `connect` is up)
```bash
./scripts/register_connector.sh
```
The script polls `CONNECT_URL` (defaults to http://localhost:8083) before posting the config in `connectors/postgres-source.json`.

3) **Watch the data flow**
- Redpanda Console: open http://localhost:8080 and inspect `streamshop.public.*` topics.
- Postgres check: `docker exec -it postgres psql -U postgres -d streamshop -c "select status, count(*) from orders group by 1 order by 2 desc;"`
- ClickHouse check: `docker exec -it clickhouse clickhouse-client -u analytics --password analytics -q "select order_id, status, _deleted, _version from analytics.raw_orders order by _version desc limit 10;"`.

4) **Build analytics with dbt** (run locally)
```bash
pip install "dbt-core~=1.8" "dbt-clickhouse"
cd dbt/streamshop
DBT_PROFILES_DIR=$(pwd) dbt deps
DBT_PROFILES_DIR=$(pwd) dbt build
```
Profiles point at the ClickHouse container (`analytics` user/password). `dbt build` will materialize staging views and marts on top of the CDC raw tables.

5) **Tear down when done**
```bash
docker compose down -v
```

## CDC/raw table design
- Debezium captures inserts/updates/deletes from Postgres tables: `customers`, `products`, `orders`, `order_items`.
- The Python sink batches CDC events, maps topics to ClickHouse `analytics.raw_*` tables, and writes with `JSONEachRow`.
- Raw tables use `ReplacingMergeTree(_version, _deleted)` so newer versions replace old ones and tombstones are preserved.
- dbt staging filters `_deleted = 0` to expose only current rows; marts are built on top of those staging views.

Happy streaming!
