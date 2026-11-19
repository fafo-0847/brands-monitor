-- Changes tab: sorting, a price filter and a category filter (the shared categories). A change's price is the price right after it (for price
-- events) or the product's current lowest price (for every other kind of change).

drop function public.change_summary(date);
drop function public.recent_changes(date, smallint[], text[], int, int);

-- Changes on one day, per brand and kind, within an optional price range and categories.
create function public.change_summary(
  p_day date,
  p_price_min bigint default null,
  p_price_max bigint default null,
  p_categories text[] default null)
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
  group by b.id, b.slug, b.name, e.kind
  order by b.name, e.kind
$$;

-- The changes themselves. p_sort: 'recent' (default), 'biggest_drop' (largest percentage drop first;
-- other kinds of change after), 'price_asc', 'price_desc'.
create function public.recent_changes(
  p_day date default null,
  p_brand_ids smallint[] default null,
  p_kinds text[] default null,
  p_limit int default 30,
  p_offset int default 0,
  p_price_min bigint default null,
  p_price_max bigint default null,
  p_sort text default 'recent',
  p_categories text[] default null)
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
  order by
    case when p_sort = 'biggest_drop' then x.drop_share end desc nulls last,
    case when p_sort = 'price_asc' then x.price end asc nulls last,
    case when p_sort = 'price_desc' then x.price end desc nulls last,
    e.observed_at desc, e.id desc
  limit least(greatest(coalesce(p_limit, 30), 1), 50)
  offset least(greatest(coalesce(p_offset, 0), 0), 5000);
end $$;

revoke all on function public.change_summary, public.recent_changes from public;
grant execute on function public.change_summary, public.recent_changes to anon, authenticated, service_role;
