{{ config(materialized='table') }}

select
  o.order_id,
  o.customer_id,
  o.status,
  o.total_cents,
  o.currency,
  o.channel,
  o.created_at,
  o.updated_at
from {{ ref('stg_orders') }} o
