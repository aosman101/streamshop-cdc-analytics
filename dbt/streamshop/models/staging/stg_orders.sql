{{ config(materialized='view') }}

select
  order_id,
  customer_id,
  status,
  total_cents,
  currency,
  created_at,
  updated_at
from {{ source('raw', 'raw_orders') }} FINAL
where _deleted = 0
