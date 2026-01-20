# streamshop-cdc-analytics

[![Postgres](https://img.shields.io/badge/Postgres-14%2B-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/) [![Debezium](https://img.shields.io/badge/Debezium-CDC-E2492F?logo=apachekafka&logoColor=white)](https://debezium.io/) [![Redpanda](https://img.shields.io/badge/Redpanda-Kafka_API-EE1F26?logo=redpanda&logoColor=white)](https://redpanda.com/) [![ClickHouse](https://img.shields.io/badge/ClickHouse-OLAP-FFCC01?logo=clickhouse&logoColor=000)](https://clickhouse.com/) [![dbt](https://img.shields.io/badge/dbt-Models-FF694B?logo=dbt&logoColor=white)](https://www.getdbt.com/) [![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/) [![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)

A local, production-style Change Data Capture (CDC) analytics platform:
**Postgres (OLTP) → Debezium (CDC) → Redpanda (Kafka API) → ClickHouse (OLAP) → dbt (marts + tests) → CI**

## Why this repo exists
I built this project to demonstrate real-world data engineering patterns:
- Continuous change data capture (CDC) ingestion, rather than just batch pulls.
- Design for a Streaming-to-OLAP Sink: Incorporating Upserts and Deletes.
- Analytics modelling and testing using dbt with ClickHouse.
- A reproducible local development environment using Docker Compose.
- Continuous Integration (CI) pipeline validating the analytics layer.

## Architecture (high level)
1. A synthetic e-commerce workload writes transactions to Postgres.
2. Debezium captures inserts/updates/deletes and publishes them to Kafka topics.
3. A Python consumer reads CDC events and upserts them into ClickHouse “raw” tables.
4. dbt builds clean staging models and analytics-ready marts in ClickHouse.
5. GitHub Actions runs lint/tests + dbt compile/build checks.

## Tech stack
- Postgres (source OLTP)
- Debezium (CDC via Kafka Connect)
- Redpanda + Console (Kafka API + topic/UI)
- ClickHouse (analytics warehouse)
- dbt Core + dbt-clickhouse (models/tests/docs)
- Python (Faker generator + CDC sink)
- Docker Compose (local platform)
- GitHub Actions (CI)

## Quickstart
### Prereqs
- Docker + Docker Compose
- (Optional) Python 3.10+ if you want to run scripts outside containers

### 1) Start the platform
```bash
cp .env.example .env
docker compose up -d --build
