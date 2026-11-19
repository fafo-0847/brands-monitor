-- Fast sorts on the free plan (2026-11-20). The app's calls are cancelled after about 3 seconds,
-- and sorting every product without an index took longer than that on the live database. Each
-- sort the app offers gets an index in exactly its ORDER BY form, limited to listed products.

drop index if exists public.products_discount_idx;        -- partial (discount_pct > 0): unusable for the sort
drop index if exists public.products_price_change_idx;    -- excluded nulls: unusable for "nulls last"

create index products_discount_sort_idx on public.products (discount_pct desc, id) where removed_at is null;
create index products_price_change_sort_idx on public.products (last_price_change_at desc nulls last, id)
  where removed_at is null;
create index products_activity_sort_idx on public.products
  ((greatest(last_price_change_at, last_restock_at, first_seen_at)) desc, id desc) where removed_at is null;
create index products_price_asc_idx on public.products (price_min asc nulls last, id) where removed_at is null;
create index products_price_desc_idx on public.products (price_min desc nulls last, id) where removed_at is null;

create or replace function public.search_price_stats(
  p_query text default null,
  p_brand_ids smallint[] default null,
  p_categories text[] default null,
  p_genders text[] default null,
  p_sizes text[] default null,
  p_price_min bigint default null,
  p_price_max bigint default null,
  p_in_stock boolean default false,
  p_on_sale boolean default false,
  p_min_discount int default null,
  p_new_within_days int default null,
  p_out_of_stock boolean default false,
  p_types text[] default null,
  p_exclude_brand_ids smallint[] default null,
  p_exclude_categories text[] default null,
  p_changed_day date default null,
  p_change_kinds text[] default null)
returns jsonb
language plpgsql stable security invoker set search_path = public, extensions as $$
declare
  c record;
  v_stats jsonb;
  v_sample text;
begin
  select * into c from private.search_clause(p_query, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min,
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days, p_types,
    p_exclude_brand_ids, p_exclude_categories, p_changed_day, p_change_kinds);
  -- Reading every product takes longer than the app's 3-second limit on the free plan, so broad
  -- results are measured on a random 10% of the table's pages; narrow ones (fewer than 300 in the
  -- sample) are measured in full, which their indexes make quick.
  for v_sample in select unnest(array['tablesample system (10) ', '']) loop
    execute 'select jsonb_build_object(''n'', count(*), ''min'', min(p.price_min), ''max'', max(p.price_min),'
            || ' ''q'', percentile_disc(array[0.2, 0.4, 0.6, 0.8]) within group (order by p.price_min))'
            || ' from products p ' || v_sample || 'join brands b on b.id = p.brand_id where ' || c.where_sql
            || ' and p.price_min is not null'
      into v_stats
      using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
            p_min_discount, p_new_within_days, null::int, null::int, p_types, p_exclude_brand_ids, p_exclude_categories,
            p_changed_day, p_change_kinds;
    exit when (v_stats ->> 'n')::int >= 300;
  end loop;
  return v_stats;
end $$;
