{{ config(materialized='view') }}

select
  event_id,
  aggregate_type,
  aggregate_id,
  event_type,
  payload,
  created_at
from {{ source('raw', 'raw_outbox_events') }} FINAL
where _deleted = 0
