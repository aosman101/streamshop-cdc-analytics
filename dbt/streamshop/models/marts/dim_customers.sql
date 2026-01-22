{{ config(materialized='table') }}

select
  customer_id,
  email,
  full_name,
  created_at
from {{ ref('stg_customers') }}
