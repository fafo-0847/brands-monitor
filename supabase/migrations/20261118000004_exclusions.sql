-- Excluding brands and categories (search and the Changes tab), and stock and gender filters on
-- the Changes tab.

drop function public.search_products(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean,
                                     int, int, text, int, int, boolean, text[]);
drop function public.search_products_count(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean,
                                           int, int, boolean, text[]);
drop function private.search_clause(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean, boolean,
                                    int, int, text[]);
drop function public.change_summary(date, bigint, bigint, text[]);
drop function public.recent_changes(date, smallint[], text[], int, int, bigint, bigint, text, text[]);

-- $1 tsquery, $2 phrase, $3 brand ids, $4 categories, $5 genders, $6 sizes, $7 price min,
-- $8 price max, $9 min discount, $10 new within days, ($11 limit, $12 offset), $13 brand types,
-- $14 excluded brand ids, $15 excluded categories.
create function private.search_clause(
  p_query text, p_brand_ids smallint[], p_categories text[], p_genders text[], p_sizes text[],
  p_price_min bigint, p_price_max bigint, p_in_stock boolean, p_out_of_stock boolean, p_on_sale boolean,
  p_min_discount int, p_new_within_days int, p_types text[],
  p_exclude_brand_ids smallint[], p_exclude_categories text[],
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
  if p_types is not null then where_sql := where_sql || ' and p.raw_type = any($13)'; end if;
  if p_exclude_brand_ids is not null then where_sql := where_sql || ' and p.brand_id <> all($14)'; end if;
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
  p_exclude_categories text[] default null)
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
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days, p_types,
    p_exclude_brand_ids, p_exclude_categories);

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
          p_min_discount, p_new_within_days, p_limit, p_offset, p_types, p_exclude_brand_ids, p_exclude_categories;
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
  p_exclude_categories text[] default null)
returns bigint
language plpgsql stable security invoker set search_path = public, extensions as $$
declare
  c record;
  v_count bigint;
begin
  perform private.use_fuzzy_threshold();
  select * into c from private.search_clause(p_query, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min,
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days, p_types,
    p_exclude_brand_ids, p_exclude_categories);
  execute 'select count(*) from (select 1 from products p join brands b on b.id = p.brand_id where '
          || c.where_sql || ' limit 10001) matches'
    into v_count
    using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days, null::int, null::int, p_types, p_exclude_brand_ids, p_exclude_categories;
  return v_count;
end $$;

-- ------------------------------------------------------------------ Changes tab
-- p_stock: 'in' (in stock now) or 'out' (sold out or no longer listed now); null for both.
-- Stock and gender describe the product as it is now, not at the time of the change.

create function public.change_summary(
  p_day date,
  p_price_min bigint default null,
  p_price_max bigint default null,
  p_categories text[] default null,
  p_genders text[] default null,
  p_stock text default null,
  p_exclude_brand_ids smallint[] default null,
  p_exclude_categories text[] default null)
returns table (brand_id smallint, brand_slug text, brand_name text, kind text, changes bigint)
language sql stable security invoker set search_path = public as $$
  select b.id, b.slug, b.name, e.kind, count(*)
  from product_events e
  join brands b on b.id = e.brand_id
  join products p on p.id = e.product_id
  cross join lateral (select coalesce((e.new_value ->> 'price')::bigint, p.price_min) as price) x
  where e.variant_id is null and b.is_visible
    and e.observed_at >= (p_day::timestamp at time zone 'Asia/Karachi')
    and e.observed_at < ((p_day + 1)::timestamp at time zone 'Asia/Karachi')
    and (p_price_min is null or x.price >= p_price_min)
    and (p_price_max is null or x.price <= p_price_max)
    and (p_categories is null or p.category = any(p_categories))
    and (p_genders is null or p.gender = any(p_genders))
    and (p_stock is null
         or (p_stock = 'in' and p.available and p.removed_at is null)
         or (p_stock = 'out' and not (p.available and p.removed_at is null)))
    and (p_exclude_brand_ids is null or e.brand_id <> all(p_exclude_brand_ids))
    and (p_exclude_categories is null or p.category is null or p.category <> all(p_exclude_categories))
  group by b.id, b.slug, b.name, e.kind
  order by b.name, e.kind
$$;

create function public.recent_changes(
  p_day date default null,
  p_brand_ids smallint[] default null,
  p_kinds text[] default null,
  p_limit int default 30,
  p_offset int default 0,
  p_price_min bigint default null,
  p_price_max bigint default null,
  p_sort text default 'recent',
  p_categories text[] default null,
  p_genders text[] default null,
  p_stock text default null,
  p_exclude_brand_ids smallint[] default null,
  p_exclude_categories text[] default null)
returns table (
  event_id bigint, kind text, observed_at timestamptz,
  old_price bigint, new_price bigint, old_discount int, new_discount int,
  id bigint, brand_id smallint, brand_slug text, brand_name text, title text, handle text, image text,
  price_min bigint, price_max bigint, compare_at_max bigint, discount_pct smallint, available boolean,
  removed boolean, price bigint)
language plpgsql stable security invoker set search_path = public as $$
begin
  if coalesce(p_sort, 'recent') not in ('recent', 'biggest_drop', 'price_asc', 'price_desc') then
    raise exception 'unknown sort %', p_sort using errcode = '22023';
  end if;
  if p_stock is not null and p_stock not in ('in', 'out') then
    raise exception 'unknown stock filter %', p_stock using errcode = '22023';
  end if;
  return query
  select e.id, e.kind, e.observed_at,
         (e.old_value ->> 'price')::bigint, (e.new_value ->> 'price')::bigint,
         (e.old_value ->> 'discount_pct')::int, (e.new_value ->> 'discount_pct')::int,
         p.id, b.id, b.slug, b.name, p.title, p.handle, p.images[1], p.price_min, p.price_max,
         p.compare_at_max, p.discount_pct, p.available, p.removed_at is not null, x.price
  from product_events e
  join products p on p.id = e.product_id
  join brands b on b.id = e.brand_id
  cross join lateral (
    select coalesce((e.new_value ->> 'price')::bigint, p.price_min) as price,
           case when e.kind = 'price_drop' and (e.old_value ->> 'price')::numeric > 0
                then ((e.old_value ->> 'price')::numeric - (e.new_value ->> 'price')::numeric)
                     / (e.old_value ->> 'price')::numeric
           end as drop_share) x
  where e.variant_id is null and b.is_visible
    and (p_day is null or (e.observed_at >= (p_day::timestamp at time zone 'Asia/Karachi')
                           and e.observed_at < ((p_day + 1)::timestamp at time zone 'Asia/Karachi')))
    and (p_brand_ids is null or e.brand_id = any(p_brand_ids))
    and (p_kinds is null or e.kind = any(p_kinds))
    and (p_price_min is null or x.price >= p_price_min)
    and (p_price_max is null or x.price <= p_price_max)
    and (p_categories is null or p.category = any(p_categories))
    and (p_genders is null or p.gender = any(p_genders))
    and (p_stock is null
         or (p_stock = 'in' and p.available and p.removed_at is null)
         or (p_stock = 'out' and not (p.available and p.removed_at is null)))
    and (p_exclude_brand_ids is null or e.brand_id <> all(p_exclude_brand_ids))
    and (p_exclude_categories is null or p.category is null or p.category <> all(p_exclude_categories))
  order by
    case when p_sort = 'biggest_drop' then x.drop_share end desc nulls last,
    case when p_sort = 'price_asc' then x.price end asc nulls last,
    case when p_sort = 'price_desc' then x.price end desc nulls last,
    e.observed_at desc, e.id desc
  limit least(greatest(coalesce(p_limit, 30), 1), 50)
  offset least(greatest(coalesce(p_offset, 0), 0), 5000);
end $$;

revoke all on function public.search_products, public.search_products_count, public.change_summary,
  public.recent_changes from public;
grant execute on function public.search_products, public.search_products_count, public.change_summary,
  public.recent_changes to anon, authenticated, service_role;
