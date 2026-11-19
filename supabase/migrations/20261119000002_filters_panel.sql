-- Filters panel (2026-11-19): products that appeared in a day's change log, a "recent activity"
-- sort, and price statistics so the app can offer price ranges that fit the current results.

drop function public.search_products(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean,
                                     int, int, text, int, int, boolean, text[], smallint[], text[]);
drop function public.search_products_count(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean,
                                           int, int, boolean, text[], smallint[], text[]);
drop function private.search_clause(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean, boolean,
                                    int, int, text[], smallint[], text[]);

-- $1 tsquery, $2 phrase, $3 brand ids, $4 categories, $5 genders, $6 sizes, $7 price min,
-- $8 price max, $9 min discount, $10 new within days, ($11 limit, $12 offset), $13 brand types,
-- $14 excluded brand ids, $15 excluded categories, $16 changed on day, $17 change kinds.
create function private.search_clause(
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
    where_sql := where_sql || ' and exists (select 1 from product_events e where e.product_id = p.id'
      || ' and e.variant_id is null'
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

revoke all on function private.search_clause from public;
grant execute on function private.search_clause to anon, authenticated, service_role;

create function public.search_products(
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
  p_sort text default 'relevance',
  p_limit int default 24,
  p_offset int default 0,
  p_out_of_stock boolean default false,
  p_types text[] default null,
  p_exclude_brand_ids smallint[] default null,
  p_exclude_categories text[] default null,
  p_changed_day date default null,
  p_change_kinds text[] default null)
returns table (
  id bigint, brand_id smallint, brand_slug text, brand_name text, title text, handle text, image text,
  price_min bigint, price_max bigint, compare_at_max bigint, discount_pct smallint, available boolean,
  category text, gender text, first_seen_at timestamptz, last_price_change_at timestamptz)
language plpgsql stable security invoker set search_path = public, extensions as $$
declare
  c record;
  v_order text;
begin
  p_limit := least(greatest(coalesce(p_limit, 24), 1), 50);
  p_offset := least(greatest(coalesce(p_offset, 0), 0), 2000);
  select * into c from private.search_clause(p_query, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min,
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days, p_types,
    p_exclude_brand_ids, p_exclude_categories, p_changed_day, p_change_kinds);

  v_order := case coalesce(p_sort, 'relevance')
    when 'relevance' then coalesce(c.rank_sql || ' desc, ', '') || 'p.first_seen_at desc, p.id desc'
    when 'price_asc' then 'p.price_min asc nulls last, p.id'
    when 'price_desc' then 'p.price_min desc nulls last, p.id'
    when 'discount' then 'p.discount_pct desc, p.id'
    when 'recent_price_change' then 'p.last_price_change_at desc nulls last, p.id'
    when 'newest' then 'p.first_seen_at desc, p.id desc'
    -- Most recent price change, restock or first appearance.
    when 'recent_activity' then 'greatest(p.last_price_change_at, p.last_restock_at, p.first_seen_at) desc, p.id desc'
  end;
  if v_order is null then
    raise exception 'unknown sort %', p_sort using errcode = '22023';
  end if;

  -- Ranking every match of a very common word is slow and adds nothing, so relevance is
  -- computed over at most 3000 matches.
  return query execute
    'select p.id, p.brand_id, b.slug, b.name, p.title, p.handle, p.images[1], p.price_min, p.price_max,'
    || ' p.compare_at_max, p.discount_pct, p.available, p.category, p.gender, p.first_seen_at, p.last_price_change_at'
    || ' from ' || case when c.rank_sql is not null and coalesce(p_sort, 'relevance') = 'relevance'
                        then '(select p.* from products p join brands b on b.id = p.brand_id where ' || c.where_sql
                             || ' limit 3000) p'
                        else 'products p' end
    || ' join brands b on b.id = p.brand_id where ' || c.where_sql
    || ' order by ' || v_order || ' limit $11 offset $12'
    using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days, p_limit, p_offset, p_types, p_exclude_brand_ids, p_exclude_categories,
          p_changed_day, p_change_kinds;
end $$;

create function public.search_products_count(
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
returns bigint
language plpgsql stable security invoker set search_path = public, extensions as $$
declare
  c record;
  v_count bigint;
begin
  select * into c from private.search_clause(p_query, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min,
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days, p_types,
    p_exclude_brand_ids, p_exclude_categories, p_changed_day, p_change_kinds);
  execute 'select count(*) from (select 1 from products p join brands b on b.id = p.brand_id where '
          || c.where_sql || ' limit 10001) matches'
    into v_count
    using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days, null::int, null::int, p_types, p_exclude_brand_ids, p_exclude_categories,
          p_changed_day, p_change_kinds;
  return v_count;
end $$;

-- Price spread of the matching products: count, min, max and the 20/40/60/80% points.
create function public.search_price_stats(
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
begin
  select * into c from private.search_clause(p_query, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min,
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days, p_types,
    p_exclude_brand_ids, p_exclude_categories, p_changed_day, p_change_kinds);
  execute 'select jsonb_build_object(''n'', count(*), ''min'', min(p.price_min), ''max'', max(p.price_min),'
          || ' ''q'', percentile_disc(array[0.2, 0.4, 0.6, 0.8]) within group (order by p.price_min))'
          || ' from products p join brands b on b.id = p.brand_id where ' || c.where_sql || ' and p.price_min is not null'
    into v_stats
    using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days, null::int, null::int, p_types, p_exclude_brand_ids, p_exclude_categories,
          p_changed_day, p_change_kinds;
  return v_stats;
end $$;

-- Price spread of one day's changes, for the Changes panel. Same price rule as recent_changes.
create function public.change_price_stats(p_day date)
returns jsonb
language sql stable security invoker set search_path = public as $$
  select jsonb_build_object('n', count(*), 'min', min(x.price), 'max', max(x.price),
                            'q', percentile_disc(array[0.2, 0.4, 0.6, 0.8]) within group (order by x.price))
  from product_events e
  join brands b on b.id = e.brand_id
  join products p on p.id = e.product_id
  cross join lateral (select coalesce((e.new_value ->> 'price')::bigint, p.price_min) as price) x
  where e.variant_id is null and b.is_visible and x.price is not null
    and e.observed_at >= (p_day::timestamp at time zone 'Asia/Karachi')
    and e.observed_at < ((p_day + 1)::timestamp at time zone 'Asia/Karachi')
$$;

revoke all on function public.search_products, public.search_products_count, public.search_price_stats,
  public.change_price_stats from public;
grant execute on function public.search_products, public.search_products_count, public.search_price_stats,
  public.change_price_stats to anon, authenticated, service_role;
