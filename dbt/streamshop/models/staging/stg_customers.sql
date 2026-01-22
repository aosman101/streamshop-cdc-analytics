{{ config(materialized='view') }}

select
  customer_id,
  email,
  full_name,
  created_at,
  updated_at
from {{ source('raw', 'raw_customers') }} FINAL
where _deleted = 0
