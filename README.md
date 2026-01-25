# streamshop-cdc-analytics

[![Postgres](https://img.shields.io/badge/Postgres-14%2B-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/) [![Debezium](https://img.shields.io/badge/Debezium-CDC-E2492F?logo=apachekafka&logoColor=white)](https://debezium.io/) [![Redpanda](https://img.shields.io/badge/Redpanda-Kafka_API-EE1F26?logo=redpanda&logoColor=white)](https://redpanda.com/) [![ClickHouse](https://img.shields.io/badge/ClickHouse-OLAP-FFCC01?logo=clickhouse&logoColor=000)](https://clickhouse.com/) [![dbt](https://img.shields.io/badge/dbt-Models-FF694B?logo=dbt&logoColor=white)](https://www.getdbt.com/) [![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/) [![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)

Production-ready CDC analytics stack that is fully wired, tested, and complete: Postgres changes stream through Debezium into Redpanda, land in ClickHouse via a Python sink, and are modelled with dbt (including SCD2 snapshot and outbox events).

## What this project gives you
- End-to-end CDC path **ready to run** locally with Docker Compose.
- CDC-friendly ClickHouse raw tables using `_version`/`_deleted` for upserts + tombstones.
- Outbox pattern with domain events flowing through the same pipeline.
- dbt models with contracts, marts, and an SCD2 product price snapshot.
- Schema registry + Avro wiring so schema evolution is explicit and validated.
- CI running dbt against ClickHouse to keep models healthy.

## Architecture at a glance
```mermaid
flowchart LR
    G[Generator\n(Faker workload)] --> PG[(Postgres\nlogical replication)]
    PG -->|WAL + pgoutput| DBZ[Debezium\nKafka Connect]
    DBZ -->|Avro| RP[(Redpanda\n+ Schema Registry)]
    RP --> CON[CDC Sink\nPython → JSONEachRow]
    CON --> CH[(ClickHouse\nReplacingMergeTree\n_version + _deleted)]
    CH --> DBT[dbt models\nstaging + marts + snapshot]
    DBT --> BI[Analytics/BI or demos]
```

## Quickstart (happy path)
1) Start everything  
   ```bash
   docker compose up -d --build
   ```
2) Register Debezium connector once `connect` is healthy  
   ```bash
   ./scripts/register_connector.sh
   ```
3) Watch the stream (optional)  
   - Redpanda Console: http://localhost:8080  
   - Schema Registry: http://localhost:18081/subjects
4) Run analytics with dbt (locally)  
   ```bash
   pip install "dbt-core~=1.8" "dbt-clickhouse"
   cd dbt/streamshop
   DBT_PROFILES_DIR=$(pwd) dbt deps
   DBT_PROFILES_DIR=$(pwd) dbt build
   ```
5) (Optional) Run the SCD2 snapshot  
   ```bash
   cd dbt/streamshop
   DBT_PROFILES_DIR=$(pwd) dbt snapshot --select product_price_scd2
   ```
6) Tear down when done  
   ```bash
   docker compose down -v
   ```

## Smoke checks
- Postgres orders rolling in:  
  `docker exec -it postgres psql -U postgres -d streamshop -c "select status, count(*) from orders group by 1 order by 2 desc;"`
- ClickHouse raw CDC (latest versions and tombstones):  
  `docker exec -it clickhouse clickhouse-client -u analytics --password analytics -q "select order_id, status, _deleted, _version from analytics.raw_orders order by _version desc limit 10;"`
- Outbox events flowing:  
  `docker exec -it clickhouse clickhouse-client -u analytics --password analytics -q "select event_type, count(*) from analytics.raw_outbox_events group by event_type;"`  
- dbt health: `cd dbt/streamshop && DBT_PROFILES_DIR=$(pwd) dbt build`

## Services and ports
| Service | Purpose | Ports / URL |
| --- | --- | --- |
| Postgres | OLTP source with logical replication | 5432 |
| Debezium Connect | Kafka Connect worker for CDC | 8083 |
| Redpanda broker | Kafka API compatible broker | 19092 (PLAINTEXT) |
| Schema Registry (Redpanda) | Avro/JSON/Protobuf schemas for topics | http://localhost:18081 |
| Redpanda Console | UI for topics/consumers | http://localhost:8080 |
| ClickHouse | OLAP warehouse target | 8123 (HTTP), 9000 (native) |
| generator | Faker workload that keeps writing orders | runs headless |
| cdc-sink | Python consumer upserting CDC into ClickHouse | runs headless |

## Repo layout (ready to trust)
- `docker-compose.yml` — launches Postgres, Debezium Connect, Redpanda + Console + Schema Registry, ClickHouse, generator, and CDC sink.
- `docker/postgres/init` — OLTP schema, publication, and Debezium replication user.
- `docker/clickhouse/init` — raw `_version`/`_deleted` tables using ReplacingMergeTree.
- `connectors/postgres-source.json` — Debezium connector config for the five tracked tables.
- `scripts/register_connector.sh` — posts the connector after Kafka Connect is up.
- `src/generator` — Faker workload writing OLTP data + outbox events.
- `src/consumer` — Avro consumer with schema registry, batching to ClickHouse via JSONEachRow.
- `dbt/streamshop` — sources, staging views, marts (`dim_customers`, `fct_orders`), outbox staging, and SCD2 snapshot (`product_price_scd2`).

## Notes on data design
- Debezium captures inserts/updates/deletes for `customers`, `products`, `orders`, `order_items`, `outbox_events`.
- Python sink maps topics to `analytics.raw_*`, stamps `_version` from Debezium event time, and preserves deletes via `_deleted`.
- dbt staging filters `_deleted = 0`; marts and snapshot build on top with model contracts enforced.

Happy streaming! The stack is complete and optimized for hands-on CDC experimentation and analytics. 
