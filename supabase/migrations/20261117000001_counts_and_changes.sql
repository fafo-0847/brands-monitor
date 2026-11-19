-- Result counts, an out-of-stock filter, and the daily change log (Changes tab).

-- Shared search filter, so the result list and its count can never disagree. It lives in a
-- schema PostgREST does not expose; callers pass the same positional parameters to both queries:
-- $1 tsquery, $2 phrase, $3 brand ids, $4 categories, $5 genders, $6 sizes, $7 price min,
-- $8 price max, $9 min discount, $10 new within days.
create schema if not exists private;
grant usage on schema private to anon, authenticated, service_role;

create function private.search_clause(
  p_query text, p_brand_ids smallint[], p_categories text[], p_genders text[], p_sizes text[],
  p_price_min bigint, p_price_max bigint, p_in_stock boolean, p_out_of_stock boolean, p_on_sale boolean,
  p_min_discount int, p_new_within_days int,
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
    if exists (select 1 from products p where p.search @@ tsq and p.removed_at is null) then
      where_sql := where_sql || ' and p.search @@ $1';
      rank_sql := 'ts_rank(p.search, $1)';
    else
      -- Nothing matched exactly: fall back to fuzzy matching on the title (typos).
      where_sql := where_sql || ' and $2 <% p.title';
      rank_sql := 'word_similarity($2, p.title)';
    end if;
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
end $$;

revoke all on function private.search_clause from public;
grant execute on function private.search_clause to anon, authenticated, service_role;

-- Fuzzy title matching (the <% operator) uses a threshold of 0.4 instead of pg_trgm's 0.6.
-- It cannot be a SET clause on the functions: on Supabase the migration role may not set an
-- extension parameter before the extension's library is loaded in that session. So it is set
-- for the current transaction at call time, after a pg_trgm call has loaded the library.
create function private.use_fuzzy_threshold() returns void
language plpgsql volatile security invoker set search_path = public, extensions as $$
begin
  perform word_similarity('', '');
  perform set_config('pg_trgm.word_similarity_threshold', '0.4', true);
end $$;

revoke all on function private.use_fuzzy_threshold from public;
grant execute on function private.use_fuzzy_threshold to anon, authenticated, service_role;

drop function public.search_products(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean,
                                     int, int, text, int, int);

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
  p_out_of_stock boolean default false)
returns table (
  id bigint, brand_id smallint, brand_slug text, brand_name text, title text, handle text, image text,
  price_min bigint, price_max bigint, compare_at_max bigint, discount_pct smallint, available boolean,
  category text, gender text, first_seen_at timestamptz, last_price_change_at timestamptz)
language plpgsql stable security invoker set search_path = public, extensions as $$
declare
  c record;
  v_order text;
begin
  perform private.use_fuzzy_threshold();
  p_limit := least(greatest(coalesce(p_limit, 24), 1), 50);
  p_offset := least(greatest(coalesce(p_offset, 0), 0), 2000);
  select * into c from private.search_clause(p_query, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min,
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days);

  v_order := case coalesce(p_sort, 'relevance')
    when 'relevance' then coalesce(c.rank_sql || ' desc, ', '') || 'p.first_seen_at desc, p.id desc'
    when 'price_asc' then 'p.price_min asc nulls last, p.id'
    when 'price_desc' then 'p.price_min desc nulls last, p.id'
    when 'discount' then 'p.discount_pct desc, p.id'
    when 'recent_price_change' then 'p.last_price_change_at desc nulls last, p.id'
    when 'newest' then 'p.first_seen_at desc, p.id desc'
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
          p_min_discount, p_new_within_days, p_limit, p_offset;
end $$;

-- How many products match the same filters (shown above the results). Counting stops at 10,001,
-- which the app shows as "10,000+": exact counts of very broad searches are slow and not useful.
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
  p_out_of_stock boolean default false)
returns bigint
language plpgsql stable security invoker set search_path = public, extensions as $$
declare
  c record;
  v_count bigint;
begin
  perform private.use_fuzzy_threshold();
  select * into c from private.search_clause(p_query, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min,
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days);
  execute 'select count(*) from (select 1 from products p join brands b on b.id = p.brand_id where '
          || c.where_sql || ' limit 10001) matches'
    into v_count
    using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days;
  return v_count;
end $$;

-- ------------------------------------------------------------------ change log
-- Days follow Pakistan time, so a scrape that finishes after midnight UTC still counts as that
-- Pakistani day. Only product-level events are listed (variant_id is null).

create index product_events_time_idx on public.product_events (observed_at desc, id desc) where variant_id is null;
create index product_events_brand_time_idx on public.product_events (brand_id, observed_at desc) where variant_id is null;

-- Days that have changes, newest first, with how many changes each. The window counts back from
-- the latest change, not from today, so a pause in scraping does not empty the list.
create function public.change_days(p_days int default 60)
returns table (day date, changes bigint)
language sql stable security invoker set search_path = public as $$
  select (e.observed_at at time zone 'Asia/Karachi')::date, count(*)
  from product_events e
  join brands b on b.id = e.brand_id
  where e.variant_id is null and b.is_visible
    and e.observed_at > (select max(x.observed_at) from product_events x where x.variant_id is null)
                        - make_interval(days => least(greatest(coalesce(p_days, 60), 1), 366))
  group by 1
  order by 1 desc
$$;

-- Changes on one day, per brand and kind (drives the filter chips and the totals).
create function public.change_summary(p_day date)
returns table (brand_id smallint, brand_slug text, brand_name text, kind text, changes bigint)
language sql stable security invoker set search_path = public as $$
  select b.id, b.slug, b.name, e.kind, count(*)
  from product_events e
  join brands b on b.id = e.brand_id
  where e.variant_id is null and b.is_visible
    and e.observed_at >= (p_day::timestamp at time zone 'Asia/Karachi')
    and e.observed_at < ((p_day + 1)::timestamp at time zone 'Asia/Karachi')
  group by b.id, b.slug, b.name, e.kind
  order by b.name, e.kind
$$;

-- The changes themselves, newest first.
create function public.recent_changes(
  p_day date default null,
  p_brand_ids smallint[] default null,
  p_kinds text[] default null,
  p_limit int default 30,
  p_offset int default 0)
returns table (
  event_id bigint, kind text, observed_at timestamptz,
  old_price bigint, new_price bigint, old_discount int, new_discount int,
  id bigint, brand_id smallint, brand_slug text, brand_name text, title text, handle text, image text,
  price_min bigint, price_max bigint, compare_at_max bigint, discount_pct smallint, available boolean,
  removed boolean)
language sql stable security invoker set search_path = public as $$
  select e.id, e.kind, e.observed_at,
         (e.old_value ->> 'price')::bigint, (e.new_value ->> 'price')::bigint,
         (e.old_value ->> 'discount_pct')::int, (e.new_value ->> 'discount_pct')::int,
         p.id, b.id, b.slug, b.name, p.title, p.handle, p.images[1], p.price_min, p.price_max,
         p.compare_at_max, p.discount_pct, p.available, p.removed_at is not null
  from product_events e
  join products p on p.id = e.product_id
  join brands b on b.id = e.brand_id
  where e.variant_id is null and b.is_visible
    and (p_day is null or (e.observed_at >= (p_day::timestamp at time zone 'Asia/Karachi')
                           and e.observed_at < ((p_day + 1)::timestamp at time zone 'Asia/Karachi')))
    and (p_brand_ids is null or e.brand_id = any(p_brand_ids))
    and (p_kinds is null or e.kind = any(p_kinds))
  order by e.observed_at desc, e.id desc
  limit least(greatest(coalesce(p_limit, 30), 1), 50)
  offset least(greatest(coalesce(p_offset, 0), 0), 5000)
$$;

revoke all on function public.search_products, public.search_products_count, public.change_days,
  public.change_summary, public.recent_changes from public;
grant execute on function public.search_products, public.search_products_count, public.change_days,
  public.change_summary, public.recent_changes to anon, authenticated, service_role;
