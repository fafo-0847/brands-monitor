-- Read API for the app (PRD 6.2 - 6.5). Clients call these through PostgREST rpc.
-- All are security invoker, so row-level security still applies to the caller.

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
  p_offset int default 0)
returns table (
  id bigint, brand_id smallint, brand_slug text, brand_name text, title text, handle text, image text,
  price_min bigint, price_max bigint, compare_at_max bigint, discount_pct smallint, available boolean,
  category text, gender text, first_seen_at timestamptz, last_price_change_at timestamptz)
language plpgsql stable security invoker set search_path = public, extensions
set pg_trgm.word_similarity_threshold = 0.4 as $$
declare
  v_tokens text[];
  v_last text;
  v_tsq tsquery;
  v_phrase text;
  v_where text := 'p.removed_at is null and b.is_visible';
  v_rank text := null;
  v_order text;
begin
  p_limit := least(greatest(coalesce(p_limit, 24), 1), 50);
  p_offset := least(greatest(coalesce(p_offset, 0), 0), 2000);

  v_tokens := array(select t from regexp_split_to_table(lower(coalesce(p_query, '')), '[^a-z0-9]+') as t where t <> '');
  v_tokens := v_tokens[1:8];
  if cardinality(v_tokens) > 0 then
    v_last := v_tokens[cardinality(v_tokens)];
    v_phrase := array_to_string(v_tokens, ' ');
    -- Every word must match; the last one also matches as a prefix (search as you type).
    v_tsq := plainto_tsquery('english', array_to_string(v_tokens[1:cardinality(v_tokens) - 1], ' '))
             && (plainto_tsquery('english', v_last) || to_tsquery('simple', v_last || ':*'));
    if exists (select 1 from products p where p.search @@ v_tsq and p.removed_at is null) then
      v_where := v_where || ' and p.search @@ $1';
      v_rank := 'ts_rank(p.search, $1)';
    else
      -- Nothing matched exactly: fall back to fuzzy matching on the title (typos).
      v_where := v_where || ' and $2 <% p.title';
      v_rank := 'word_similarity($2, p.title)';
    end if;
  end if;

  if p_brand_ids is not null then v_where := v_where || ' and p.brand_id = any($3)'; end if;
  if p_categories is not null then v_where := v_where || ' and p.category = any($4)'; end if;
  if p_genders is not null then v_where := v_where || ' and p.gender = any($5)'; end if;
  if p_sizes is not null then
    v_where := v_where || ' and exists (select 1 from variants v where v.product_id = p.id and v.available'
                       || ' and v.removed_at is null and v.size_norm = any($6))';
  end if;
  if p_price_min is not null then v_where := v_where || ' and p.price_min >= $7'; end if;
  if p_price_max is not null then v_where := v_where || ' and p.price_min <= $8'; end if;
  if p_in_stock then v_where := v_where || ' and p.available'; end if;
  if p_on_sale then v_where := v_where || ' and p.discount_pct > 0'; end if;
  if p_min_discount is not null then v_where := v_where || ' and p.discount_pct >= $9'; end if;
  if p_new_within_days is not null then
    v_where := v_where || ' and p.first_seen_at >= now() - make_interval(days => $10)';
  end if;

  v_order := case coalesce(p_sort, 'relevance')
    when 'relevance' then coalesce(v_rank || ' desc, ', '') || 'p.first_seen_at desc, p.id desc'
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
    || ' from ' || case when v_rank is not null and coalesce(p_sort, 'relevance') = 'relevance'
                        then '(select p.* from products p join brands b on b.id = p.brand_id where ' || v_where
                             || ' limit 3000) p'
                        else 'products p' end
    || ' join brands b on b.id = p.brand_id where ' || v_where
    || ' order by ' || v_order || ' limit $11 offset $12'
    using v_tsq, v_phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days, p_limit, p_offset;
end $$;

-- Home feeds. p_kind: 'price_drops' (biggest percentage drops in the latest three days of data),
-- 'back_in_stock' and 'new_arrivals' (most recent first).
create function public.home_feed(
  p_kind text,
  p_brand_ids smallint[] default null,
  p_limit int default 20,
  p_offset int default 0)
returns table (
  id bigint, brand_id smallint, brand_slug text, brand_name text, title text, handle text, image text,
  price_min bigint, price_max bigint, compare_at_max bigint, discount_pct smallint, available boolean,
  event_at timestamptz, old_price bigint, new_price bigint)
language plpgsql stable security invoker set search_path = public as $$
declare
  v_kind text;
  v_since timestamptz;
begin
  p_limit := least(greatest(coalesce(p_limit, 20), 1), 50);
  p_offset := least(greatest(coalesce(p_offset, 0), 0), 500);
  v_kind := case p_kind when 'price_drops' then 'price_drop' when 'back_in_stock' then 'back_in_stock'
                        when 'new_arrivals' then 'new_product' end;
  if v_kind is null then
    raise exception 'unknown feed %', p_kind using errcode = '22023';
  end if;
  select max(e.observed_at) - interval '3 days' into v_since
  from product_events e where e.kind = v_kind and e.variant_id is null;

  return query
  select p.id, p.brand_id, b.slug, b.name, p.title, p.handle, p.images[1], p.price_min, p.price_max,
         p.compare_at_max, p.discount_pct, p.available, e.observed_at,
         (e.old_value ->> 'price')::bigint, (e.new_value ->> 'price')::bigint
  from product_events e
  join products p on p.id = e.product_id
  join brands b on b.id = p.brand_id
  where e.kind = v_kind and e.variant_id is null
    and p.removed_at is null and b.is_visible
    and (p_brand_ids is null or p.brand_id = any(p_brand_ids))
    and (v_kind = 'new_product' or p.available)
    and (v_kind <> 'price_drop' or (e.observed_at >= v_since and (e.old_value ->> 'price')::bigint > 0))
  order by
    case when v_kind = 'price_drop'
         then ((e.old_value ->> 'price')::numeric - (e.new_value ->> 'price')::numeric) / (e.old_value ->> 'price')::numeric
    end desc nulls last,
    e.observed_at desc, e.id desc
  limit p_limit offset p_offset;
end $$;

-- Everything the article page needs in one call. Look up by id, or by brand slug + handle (share links).
create function public.product_detail(
  p_id bigint default null,
  p_brand_slug text default null,
  p_handle text default null)
returns jsonb
language sql stable security invoker set search_path = public as $$
  with target as (
    select p.*, b.slug as brand_slug, b.name as brand_name, b.origin_url, b.logo_url, b.granularity,
           b.affiliate_template
    from products p join brands b on b.id = p.brand_id
    where b.is_visible
      and p.id = coalesce(p_id, (
        select p2.id from products p2 join brands b2 on b2.id = p2.brand_id
        where b2.slug = p_brand_slug and p2.handle = p_handle
        order by p2.removed_at nulls first limit 1))),
  vars as (
    select v.* from variants v join target t on t.id = v.product_id where v.removed_at is null),
  history as (
    select min(pp.price) as low, max(pp.price) as high, count(*) filter (where pp.observed_at > v.first_seen_at) as changes
    from vars v join price_points pp on pp.variant_id = v.id)
  select jsonb_build_object(
    'id', t.id, 'title', t.title, 'handle', t.handle, 'url', t.url, 'description', t.description,
    'tags', t.tags, 'images', t.images, 'category', t.category, 'gender', t.gender,
    'available', t.available, 'price_min', t.price_min, 'price_max', t.price_max,
    'compare_at_max', t.compare_at_max, 'discount_pct', t.discount_pct,
    'first_seen_at', t.first_seen_at, 'removed_at', t.removed_at,
    'last_price_change_at', t.last_price_change_at, 'last_restock_at', t.last_restock_at,
    'brand', jsonb_build_object('id', t.brand_id, 'slug', t.brand_slug, 'name', t.brand_name,
                                'origin_url', t.origin_url, 'logo_url', t.logo_url,
                                'tracks_sizes', t.granularity = 'variant',
                                'affiliate_template', t.affiliate_template),
    'variants', coalesce((
      select jsonb_agg(jsonb_build_object('id', v.id, 'title', v.title, 'size', v.size_norm, 'options', v.options,
                                          'available', v.available, 'price', v.price,
                                          'compare_at_price', v.compare_at_price) order by v.id)
      from vars v), '[]'::jsonb),
    'stats', jsonb_build_object(
      'lowest_price', least(h.low, t.price_min),
      'highest_price', greatest(h.high, t.price_max),
      'price_changes', coalesce(h.changes, 0),
      'tracking_since', t.first_seen_at))
  from target t cross join history h
$$;

-- Step series for the chart. With p_variant_id: that size. Without: the product-level price
-- (lowest price over the variants listed at each moment) and whether any size was in stock.
-- Each row is the state from observed_at until the next row.
create function public.price_series(
  p_product_id bigint,
  p_variant_id bigint default null,
  p_since timestamptz default null)
returns table (observed_at timestamptz, price bigint, compare_at_price bigint, available boolean)
language sql stable security invoker set search_path = public as $$
  with vars as (
    select v.id, v.first_seen_at, v.price, v.compare_at_price, v.available, v.removed_at
    from variants v
    where v.product_id = p_product_id and (p_variant_id is null or v.id = p_variant_id)),
  moments as (
    select v.first_seen_at as at from vars v
    union select pp.observed_at from vars v join price_points pp on pp.variant_id = v.id
    union select sp.observed_at from vars v join stock_points sp on sp.variant_id = v.id),
  state as (
    select m.at, v.id,
           coalesce(pp.price, v.price) as price,
           case when pp.variant_id is not null then pp.compare_at_price else v.compare_at_price end as compare_at_price,
           coalesce(sp.available, v.available and v.removed_at is null) as available
    from moments m
    join vars v on v.first_seen_at <= m.at and (v.removed_at is null or m.at < v.removed_at)
    left join lateral (
      select x.variant_id, x.price, x.compare_at_price from price_points x
      where x.variant_id = v.id and x.observed_at <= m.at order by x.observed_at desc limit 1) pp on true
    left join lateral (
      select x.available from stock_points x
      where x.variant_id = v.id and x.observed_at <= m.at order by x.observed_at desc limit 1) sp on true),
  series as (
    select s.at, min(s.price) as price,
           max(s.compare_at_price) filter (where s.compare_at_price > s.price) as compare_at_price,
           bool_or(s.available) as available
    from state s group by s.at),
  windowed as (
    select s.*, row_number() over (order by s.at desc) as recency,
           lead(s.at) over (order by s.at) as next_at
    from series s)
  select w.at, w.price, w.compare_at_price, w.available
  from windowed w
  where w.recency <= 1000 and (p_since is null or coalesce(w.next_at, 'infinity') > p_since)
  order by w.at
$$;

create index products_handle_idx on public.products (brand_id, handle);

revoke all on function public.search_products, public.home_feed, public.product_detail, public.price_series from public;
grant execute on function public.search_products, public.home_feed, public.product_detail, public.price_series
  to anon, authenticated, service_role;
