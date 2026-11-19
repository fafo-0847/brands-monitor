-- Two calls still near or over the app's 3-second limit on the hosted database (2026-11-20):
-- counting products that changed on a busy day, and price statistics.
create or replace function private.search_clause(
  p_query text, p_brand_ids smallint[], p_categories text[], p_genders text[], p_sizes text[],
  p_price_min bigint, p_price_max bigint, p_in_stock boolean, p_out_of_stock boolean, p_on_sale boolean,
  p_min_discount int, p_new_within_days int, p_types text[],
  p_exclude_brand_ids smallint[], p_exclude_categories text[],
  p_changed_day date, p_change_kinds text[],
  out where_sql text, out rank_sql text, out tsq tsquery, out phrase text)
language plpgsql stable security invoker set search_path = public, extensions as $$
declare
  v_tokens text[];
  v_last text;
begin
  where_sql := 'p.removed_at is null and b.is_visible';
  v_tokens := array(select t from regexp_split_to_table(lower(coalesce(p_query, '')), '[^a-z0-9]+') as t where t <> '');
  v_tokens := v_tokens[1:8];
  if cardinality(v_tokens) > 0 then
    v_last := v_tokens[cardinality(v_tokens)];
    phrase := array_to_string(v_tokens, ' ');
    -- Every word must match; the last one also matches as a prefix (search as you type).
    tsq := plainto_tsquery('english', v_last) || to_tsquery('simple', v_last || ':*');
    if cardinality(v_tokens) > 1 then
      tsq := plainto_tsquery('english', array_to_string(v_tokens[1:cardinality(v_tokens) - 1], ' ')) && tsq;
    end if;
    -- No fuzzy (typo) fallback since 20261119000001: its trigram index was dropped to save space.
    where_sql := where_sql || ' and p.search @@ $1';
    rank_sql := 'ts_rank(p.search, $1)';
  end if;
  if p_brand_ids is not null then where_sql := where_sql || ' and p.brand_id = any($3)'; end if;
  if p_categories is not null then where_sql := where_sql || ' and p.category = any($4)'; end if;
  if p_genders is not null then where_sql := where_sql || ' and p.gender = any($5)'; end if;
  if p_sizes is not null then
    where_sql := where_sql || ' and exists (select 1 from variants v where v.product_id = p.id and v.available'
                           || ' and v.removed_at is null and v.size_norm = any($6))';
  end if;
  if p_price_min is not null then where_sql := where_sql || ' and p.price_min >= $7'; end if;
  if p_price_max is not null then where_sql := where_sql || ' and p.price_min <= $8'; end if;
  if coalesce(p_in_stock, false) then where_sql := where_sql || ' and p.available'; end if;
  if coalesce(p_out_of_stock, false) then where_sql := where_sql || ' and not p.available'; end if;
  if coalesce(p_on_sale, false) then where_sql := where_sql || ' and p.discount_pct > 0'; end if;
  if p_min_discount is not null then where_sql := where_sql || ' and p.discount_pct >= $9'; end if;
  if p_new_within_days is not null then
    where_sql := where_sql || ' and p.first_seen_at >= now() - make_interval(days => $10)';
  end if;
  if p_types is not null then where_sql := where_sql || ' and p.raw_type = any($13)'; end if;
  if p_exclude_brand_ids is not null then where_sql := where_sql || ' and p.brand_id <> all($14)'; end if;
  -- Products that appeared in a day's change log ($16, a Pakistan calendar day; null = any day),
  -- optionally only for some kinds of change ($17).
  if p_changed_day is not null or p_change_kinds is not null then
    -- A semi-join from the day's changes (IN) instead of an EXISTS probe per product, which took over
    -- 3 seconds on a busy day on the hosted database.
    where_sql := where_sql || ' and p.id in (select e.product_id from product_events e'
      || ' where e.variant_id is null'
      || case when p_changed_day is not null
              then ' and e.observed_at >= ($16::timestamp at time zone ''Asia/Karachi'')'
                   || ' and e.observed_at < (($16 + 1)::timestamp at time zone ''Asia/Karachi'')'
              else '' end
      || case when p_change_kinds is not null then ' and e.kind = any($17)' else '' end
      || ')';
  end if;
  if p_exclude_categories is not null then
    where_sql := where_sql || ' and (p.category is null or p.category <> all($15))';
  end if;
end $$;

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
  v_count int;
begin
  select * into c from private.search_clause(p_query, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min,
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days, p_types,
    p_exclude_brand_ids, p_exclude_categories, p_changed_day, p_change_kinds);
  -- Under 3,000 matches: measure them all (their indexes make that quick). More: measure a 3% page
  -- sample, because reading every product exceeds the app's 3-second limit on the free plan.
  execute 'select count(*) from (select 1 from products p join brands b on b.id = p.brand_id where '
          || c.where_sql || ' limit 3000) m'
    into v_count
    using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days, null::int, null::int, p_types, p_exclude_brand_ids, p_exclude_categories,
          p_changed_day, p_change_kinds;
  v_sample := case when v_count < 3000 then '' else 'tablesample system (3) ' end;
  execute 'select jsonb_build_object(''n'', count(*), ''min'', min(p.price_min), ''max'', max(p.price_min),'
          || ' ''q'', percentile_disc(array[0.2, 0.4, 0.6, 0.8]) within group (order by p.price_min))'
          || ' from products p ' || v_sample || 'join brands b on b.id = p.brand_id where ' || c.where_sql
          || ' and p.price_min is not null'
    into v_stats
    using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days, null::int, null::int, p_types, p_exclude_brand_ids, p_exclude_categories,
          p_changed_day, p_change_kinds;
  return v_stats;
end $$;
