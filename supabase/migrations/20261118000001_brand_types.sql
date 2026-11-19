-- Brands' own product types: a filter on brand pages, and the bookkeeping for re-labelling.

-- Set from pipeline/brand_types.json on every ingest. False hides a brand's own types (colours,
-- seasons, stock codes) from its brand page.
alter table public.brands add column show_types boolean not null default true;

-- Small key/value store for the pipeline (for example the version of the labelling rules).
create table public.pipeline_meta (
  key text primary key,
  value text not null,
  updated_at timestamptz not null default now()
);
alter table public.pipeline_meta enable row level security;
revoke all on public.pipeline_meta from anon, authenticated;

create index products_brand_type_idx on public.products (brand_id, raw_type) where removed_at is null;

-- A brand's own product types with how many live products each has, most common first.
-- Empty when the brand's types are switched off. Types with fewer than 3 products are left out.
create function public.brand_types(p_brand_id smallint)
returns table (raw_type text, products bigint)
language sql stable security invoker set search_path = public as $$
  select p.raw_type, count(*)
  from products p
  join brands b on b.id = p.brand_id
  where p.brand_id = p_brand_id and b.show_types and b.is_visible
    and p.removed_at is null and coalesce(p.raw_type, '') <> ''
  group by p.raw_type
  having count(*) >= 3
  order by 2 desc, 1
  limit 80
$$;

-- Search gains p_types (exact brand product types, $13). The filter builder, the list and the
-- count are recreated together so they keep sharing one definition.
drop function public.search_products(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean,
                                     int, int, text, int, int, boolean);
drop function public.search_products_count(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean,
                                           int, int, boolean);
drop function private.search_clause(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean, boolean,
                                    int, int);

-- $1 tsquery, $2 phrase, $3 brand ids, $4 categories, $5 genders, $6 sizes, $7 price min,
-- $8 price max, $9 min discount, $10 new within days, ($11 limit, $12 offset), $13 brand types.
create function private.search_clause(
  p_query text, p_brand_ids smallint[], p_categories text[], p_genders text[], p_sizes text[],
  p_price_min bigint, p_price_max bigint, p_in_stock boolean, p_out_of_stock boolean, p_on_sale boolean,
  p_min_discount int, p_new_within_days int, p_types text[],
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
  p_types text[] default null)
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
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days, p_types);

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
          p_min_discount, p_new_within_days, p_limit, p_offset, p_types;
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
  p_out_of_stock boolean default false,
  p_types text[] default null)
returns bigint
language plpgsql stable security invoker set search_path = public, extensions as $$
declare
  c record;
  v_count bigint;
begin
  perform private.use_fuzzy_threshold();
  select * into c from private.search_clause(p_query, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min,
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days, p_types);
  execute 'select count(*) from (select 1 from products p join brands b on b.id = p.brand_id where '
          || c.where_sql || ' limit 10001) matches'
    into v_count
    using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days, null::int, null::int, p_types;
  return v_count;
end $$;

revoke all on function public.search_products, public.search_products_count, public.brand_types from public;
grant execute on function public.search_products, public.search_products_count, public.brand_types
  to anon, authenticated, service_role;
