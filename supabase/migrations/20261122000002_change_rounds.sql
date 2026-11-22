-- Scrape rounds and several days at once in the change log.
--
-- A round is one run of the scrape workflow. New snapshot commits name their GitHub run
-- ("Update <brand> catalog state (run <id>)") and ingest stores it in scans.run_id. Older scans have
-- no run id; they are grouped by time instead: a gap of more than 60 minutes between consecutive
-- scans (any brand) starts a new round. Rounds are identified by the run id, or for time-grouped
-- rounds by minus the epoch seconds of their first scan, so the app treats the id as opaque.
--
-- Every change-log filter that took one day (p_day / p_changed_day) now also takes several days
-- (p_days / p_changed_days, Pakistan calendar days) and rounds (p_rounds / p_changed_rounds). Days
-- and rounds combine with AND: rounds narrow the chosen days down to some checks. The old single-day
-- parameters still work for app builds that send them.

alter table public.scans add column run_id bigint;

create function private.scan_rounds()
returns table (scan_id bigint, brand_id smallint, round_id bigint, checked_at timestamptz)
language sql stable security definer set search_path = '' as $$
  with untagged as (
    select s.id, s.brand_id, s.checked_at,
           case when s.checked_at - lag(s.checked_at) over (order by s.checked_at, s.id) <= interval '60 minutes'
                then 0 else 1 end as starts_round
    from public.scans s
    where s.run_id is null and s.checked_at is not null
  ), numbered as (
    select u.*, sum(u.starts_round) over (order by u.checked_at, u.id) as round_no from untagged u
  )
  select n.id, n.brand_id, -extract(epoch from min(n.checked_at) over (partition by n.round_no))::bigint, n.checked_at
  from numbered n
  union all
  select s.id, s.brand_id, s.run_id, s.checked_at
  from public.scans s
  where s.run_id is not null and s.checked_at is not null
$$;
revoke all on function private.scan_rounds() from public;
grant execute on function private.scan_rounds() to anon, authenticated, service_role;

-- Rounds that checked at least one brand on the given days (default: the last 14 days), newest first,
-- with how many product-level changes they found on those days.
create function public.change_rounds(p_days date[] default null)
returns table (round_id bigint, started_at timestamptz, ended_at timestamptz, brands int, changes bigint)
language sql stable security invoker set search_path = public as $$
  with r as (
    select r.round_id, min(r.checked_at) as started_at, max(r.checked_at) as ended_at,
           count(distinct r.brand_id)::int as brands, array_agg(r.scan_id) as scan_ids
    from private.scan_rounds() r
    group by r.round_id
    having case when p_days is null then max(r.checked_at) >= now() - interval '14 days'
                else bool_or((r.checked_at at time zone 'Asia/Karachi')::date = any(p_days)) end
  )
  select r.round_id, r.started_at, r.ended_at, r.brands,
         (select count(*) from product_events e join brands b on b.id = e.brand_id
           where e.variant_id is null and b.is_visible and e.scan_id = any(r.scan_ids)
             and (p_days is null or (e.observed_at at time zone 'Asia/Karachi')::date = any(p_days)))
  from r
  order by r.started_at desc
  limit 100
$$;
revoke all on function public.change_rounds(date[]) from public;
grant execute on function public.change_rounds(date[]) to anon, authenticated, service_role;

-- ------------------------------------------------------------------ products that changed

drop function public.search_products(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean,
  int, int, text, int, int, boolean, text[], smallint[], text[], date, text[]);
drop function public.search_products_count(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean,
  int, int, boolean, text[], smallint[], text[], date, text[]);
drop function public.search_price_stats(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean,
  int, int, boolean, text[], smallint[], text[], date, text[]);
drop function private.search_clause(text, smallint[], text[], text[], text[], bigint, bigint, boolean, boolean, boolean,
  int, int, text[], smallint[], text[], date, text[]);

create function private.search_clause(
  p_query text, p_brand_ids smallint[], p_categories text[], p_genders text[], p_sizes text[],
  p_price_min bigint, p_price_max bigint, p_in_stock boolean, p_out_of_stock boolean, p_on_sale boolean,
  p_min_discount int, p_new_within_days int, p_types text[],
  p_exclude_brand_ids smallint[], p_exclude_categories text[],
  p_changed_day date, p_change_kinds text[], p_changed_days date[], p_changed_rounds bigint[],
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
  -- Products in the change log: on the chosen days ($18, or the single day $16), in the chosen
  -- rounds ($19), with the chosen kinds of change ($17). A semi-join from the changes (IN), which
  -- stays fast on busy days.
  if p_changed_day is not null or p_changed_days is not null or p_changed_rounds is not null
     or p_change_kinds is not null then
    where_sql := where_sql || ' and p.id in (select e.product_id from product_events e where e.variant_id is null'
      || case when p_changed_days is not null
              then ' and e.observed_at >= ((select min(d) from unnest($18) d)::timestamp at time zone ''Asia/Karachi'')'
                   || ' and e.observed_at < (((select max(d) from unnest($18) d) + 1)::timestamp at time zone ''Asia/Karachi'')'
                   || ' and (e.observed_at at time zone ''Asia/Karachi'')::date = any($18)'
              when p_changed_day is not null
              then ' and e.observed_at >= ($16::timestamp at time zone ''Asia/Karachi'')'
                   || ' and e.observed_at < (($16 + 1)::timestamp at time zone ''Asia/Karachi'')'
              else '' end
      || case when p_changed_rounds is not null
              then ' and e.scan_id in (select r.scan_id from private.scan_rounds() r where r.round_id = any($19))'
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
  p_change_kinds text[] default null,
  p_changed_days date[] default null,
  p_changed_rounds bigint[] default null)
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
    p_exclude_brand_ids, p_exclude_categories, p_changed_day, p_change_kinds, p_changed_days, p_changed_rounds);

  v_order := case coalesce(p_sort, 'relevance')
    when 'relevance' then coalesce(c.rank_sql || ' desc, ', '') || 'p.first_seen_at desc, p.id desc'
    when 'price_asc' then 'p.price_min asc nulls last, p.id'
    when 'price_desc' then 'p.price_min desc nulls last, p.id'
    when 'discount' then 'p.discount_pct desc, p.id'
    when 'recent_price_change' then 'p.last_price_change_at desc nulls last, p.id'
    when 'newest' then 'p.first_seen_at desc, p.id desc'
    when 'recent_activity' then 'greatest(p.last_price_change_at, p.last_restock_at, p.first_seen_at) desc, p.id desc'
  end;
  if v_order is null then
    raise exception 'unknown sort %', p_sort using errcode = '22023';
  end if;

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
          p_changed_day, p_change_kinds, p_changed_days, p_changed_rounds;
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
  p_change_kinds text[] default null,
  p_changed_days date[] default null,
  p_changed_rounds bigint[] default null)
returns bigint
language plpgsql stable security invoker set search_path = public, extensions as $$
declare
  c record;
  v_count bigint;
begin
  select * into c from private.search_clause(p_query, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min,
    p_price_max, p_in_stock, p_out_of_stock, p_on_sale, p_min_discount, p_new_within_days, p_types,
    p_exclude_brand_ids, p_exclude_categories, p_changed_day, p_change_kinds, p_changed_days, p_changed_rounds);
  execute 'select count(*) from (select 1 from products p join brands b on b.id = p.brand_id where '
          || c.where_sql || ' limit 10001) matches'
    into v_count
    using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days, null::int, null::int, p_types, p_exclude_brand_ids, p_exclude_categories,
          p_changed_day, p_change_kinds, p_changed_days, p_changed_rounds;
  return v_count;
end $$;

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
  p_change_kinds text[] default null,
  p_changed_days date[] default null,
  p_changed_rounds bigint[] default null)
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
    p_exclude_brand_ids, p_exclude_categories, p_changed_day, p_change_kinds, p_changed_days, p_changed_rounds);
  -- Under 3,000 matches: measure them all. More: measure a 3% page sample.
  execute 'select count(*) from (select 1 from products p join brands b on b.id = p.brand_id where '
          || c.where_sql || ' limit 3000) m'
    into v_count
    using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days, null::int, null::int, p_types, p_exclude_brand_ids, p_exclude_categories,
          p_changed_day, p_change_kinds, p_changed_days, p_changed_rounds;
  v_sample := case when v_count < 3000 then '' else 'tablesample system (3) ' end;
  execute 'select jsonb_build_object(''n'', count(*), ''min'', min(p.price_min), ''max'', max(p.price_min),'
          || ' ''q'', percentile_disc(array[0.2, 0.4, 0.6, 0.8]) within group (order by p.price_min))'
          || ' from products p ' || v_sample || 'join brands b on b.id = p.brand_id where ' || c.where_sql
          || ' and p.price_min is not null'
    into v_stats
    using c.tsq, c.phrase, p_brand_ids, p_categories, p_genders, p_sizes, p_price_min, p_price_max,
          p_min_discount, p_new_within_days, null::int, null::int, p_types, p_exclude_brand_ids, p_exclude_categories,
          p_changed_day, p_change_kinds, p_changed_days, p_changed_rounds;
  return v_stats;
end $$;

revoke all on function public.search_products, public.search_products_count, public.search_price_stats from public;
grant execute on function public.search_products, public.search_products_count, public.search_price_stats
  to anon, authenticated, service_role;

-- ------------------------------------------------------------------ the change log itself

drop function public.change_summary(date, bigint, bigint, text[], text[], text, smallint[], text[]);
drop function public.recent_changes(date, smallint[], text[], int, int, bigint, bigint, text, text[], text[], text,
  smallint[], text[]);
drop function public.change_price_stats(date);

-- Day bounds and the scans of the chosen rounds, shared by the three functions below.
create function private.change_window(p_day date, p_days date[], p_rounds bigint[],
  out days date[], out from_at timestamptz, out to_at timestamptz, out scan_ids bigint[])
language plpgsql stable security invoker set search_path = public as $$
begin
  days := coalesce(p_days, case when p_day is not null then array[p_day] end);
  if days is not null then
    from_at := (select min(d) from unnest(days) d)::timestamp at time zone 'Asia/Karachi';
    to_at := ((select max(d) from unnest(days) d) + 1)::timestamp at time zone 'Asia/Karachi';
  end if;
  if p_rounds is not null then
    scan_ids := array(select r.scan_id from private.scan_rounds() r where r.round_id = any(p_rounds));
  end if;
end $$;
revoke all on function private.change_window from public;
grant execute on function private.change_window to anon, authenticated, service_role;

create function public.change_summary(
  p_day date default null,
  p_price_min bigint default null,
  p_price_max bigint default null,
  p_categories text[] default null,
  p_genders text[] default null,
  p_stock text default null,
  p_exclude_brand_ids smallint[] default null,
  p_exclude_categories text[] default null,
  p_days date[] default null,
  p_rounds bigint[] default null)
returns table (brand_id smallint, brand_slug text, brand_name text, kind text, changes bigint)
language plpgsql stable security invoker set search_path = public as $$
declare
  w record;
begin
  select * into w from private.change_window(p_day, p_days, p_rounds);
  return query
  select b.id, b.slug, b.name, e.kind, count(*)
  from product_events e
  join brands b on b.id = e.brand_id
  join products p on p.id = e.product_id
  cross join lateral (select coalesce((e.new_value ->> 'price')::bigint, p.price_min) as price) x
  where e.variant_id is null and b.is_visible
    and (w.days is null or (e.observed_at >= w.from_at and e.observed_at < w.to_at
                            and (e.observed_at at time zone 'Asia/Karachi')::date = any(w.days)))
    and (w.scan_ids is null or e.scan_id = any(w.scan_ids))
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
  order by b.name, e.kind;
end $$;

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
  p_exclude_categories text[] default null,
  p_days date[] default null,
  p_rounds bigint[] default null)
returns table (
  event_id bigint, kind text, observed_at timestamptz,
  old_price bigint, new_price bigint, old_discount int, new_discount int,
  id bigint, brand_id smallint, brand_slug text, brand_name text, title text, handle text, image text,
  price_min bigint, price_max bigint, compare_at_max bigint, discount_pct smallint, available boolean,
  removed boolean, price bigint)
language plpgsql stable security invoker set search_path = public as $$
declare
  w record;
begin
  if coalesce(p_sort, 'recent') not in ('recent', 'biggest_drop', 'price_asc', 'price_desc') then
    raise exception 'unknown sort %', p_sort using errcode = '22023';
  end if;
  if p_stock is not null and p_stock not in ('in', 'out') then
    raise exception 'unknown stock filter %', p_stock using errcode = '22023';
  end if;
  select * into w from private.change_window(p_day, p_days, p_rounds);
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
    and (w.days is null or (e.observed_at >= w.from_at and e.observed_at < w.to_at
                            and (e.observed_at at time zone 'Asia/Karachi')::date = any(w.days)))
    and (w.scan_ids is null or e.scan_id = any(w.scan_ids))
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

create function public.change_price_stats(
  p_day date default null,
  p_days date[] default null,
  p_rounds bigint[] default null)
returns jsonb
language plpgsql stable security invoker set search_path = public as $$
declare
  w record;
  v_stats jsonb;
begin
  select * into w from private.change_window(p_day, p_days, p_rounds);
  select jsonb_build_object('n', count(*), 'min', min(x.price), 'max', max(x.price),
                            'q', percentile_disc(array[0.2, 0.4, 0.6, 0.8]) within group (order by x.price))
    into v_stats
  from product_events e
  join brands b on b.id = e.brand_id
  join products p on p.id = e.product_id
  cross join lateral (select coalesce((e.new_value ->> 'price')::bigint, p.price_min) as price) x
  where e.variant_id is null and b.is_visible and x.price is not null
    and (w.days is null or (e.observed_at >= w.from_at and e.observed_at < w.to_at
                            and (e.observed_at at time zone 'Asia/Karachi')::date = any(w.days)))
    and (w.scan_ids is null or e.scan_id = any(w.scan_ids));
  return v_stats;
end $$;

revoke all on function public.change_summary, public.recent_changes, public.change_price_stats from public;
grant execute on function public.change_summary, public.recent_changes, public.change_price_stats
  to anon, authenticated, service_role;
