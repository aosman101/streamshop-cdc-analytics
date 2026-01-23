{% snapshot product_price_scd2 %}
{{
  config(
    target_database='analytics',
    target_schema='snapshots',
    unique_key='product_id',
    strategy='check',
    check_cols=['price_cents'],
    invalidate_hard_deletes=True
  )
}}

select
  product_id,
  sku,
  product_name,
  category,
  price_cents,
  updated_at
from {{ source('raw', 'raw_products') }} FINAL
where _deleted = 0

{% endsnapshot %}
