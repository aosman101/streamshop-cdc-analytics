-- Dedicated replication user (recommended practice).
-- Debezium docs advise using a dedicated user with the required privileges rather than superuser.
CREATE ROLE debezium WITH LOGIN PASSWORD 'debezium' REPLICATION;

GRANT CONNECT ON DATABASE streamshop TO debezium;

\c streamshop
GRANT USAGE ON SCHEMA public TO debezium;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium;
