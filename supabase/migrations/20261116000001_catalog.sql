-- Catalog, history and pipeline bookkeeping (PRD section 7).
-- Money is bigint minor units in PKR; timestamps are UTC.

create extension if not exists pg_trgm with schema extensions;
create extension if not exists vector with schema extensions;

create table public.brands (
  id smallint primary key generated always as identity,
  slug text unique not null,
  name text not null,
  origin_url text not null,
  logo_url text,
  strategy text not null,
  granularity text not null check (granularity in ('variant', 'product')),
  scan_tier text not null default 'daily' check (scan_tier in ('hot', 'daily', 'paused')),
  affiliate_template text,
  is_visible boolean not null default true,
  ingest_enabled boolean not null default true,
  product_count int not null default 0,
  last_scan_at timestamptz,
  last_success_at timestamptz
);

create table public.products (
  id bigint primary key generated always as identity,
  brand_id smallint not null references public.brands,
  external_id text not null,
  title text not null,
  handle text,
  url text not null,
  vendor text,
  raw_type text,
  description text,
  tags text[] not null default '{}',
  images text[] not null default '{}',
  options jsonb,
  category text,
  gender text,
  available boolean not null default false,
  price_min bigint,
  price_max bigint,
  compare_at_max bigint,
  discount_pct smallint not null default 0,
  last_price_change_at timestamptz,
  last_restock_at timestamptz,
  first_seen_at timestamptz not null,
  removed_at timestamptz,
  search tsvector,
  embedding extensions.vector(1024),
  unique (brand_id, external_id)
);

create table public.variants (
  id bigint primary key generated always as identity,
  product_id bigint not null references public.products on delete cascade,
  external_id text not null,
  title text,
  options text[],
  size_norm text,
  sku text,
  available boolean not null,
  price bigint not null,
  compare_at_price bigint,
  first_seen_at timestamptz not null,
  removed_at timestamptz,
  unique (product_id, external_id)
);

-- History is written only when a value changes. A variant with no rows here has had the
-- same price / availability since variants.first_seen_at.
create table public.price_points (
  variant_id bigint not null references public.variants on delete cascade,
  observed_at timestamptz not null,
  price bigint not null,
  compare_at_price bigint,
  primary key (variant_id, observed_at)
);

create table public.stock_points (
  variant_id bigint not null references public.variants on delete cascade,
  observed_at timestamptz not null,
  available boolean not null,
  primary key (variant_id, observed_at)
);

create table public.scans (
  id bigint primary key generated always as identity,
  brand_id smallint not null references public.brands,
  commit_sha text not null,
  checked_at timestamptz,
  product_count int,
  change_count int,
  status text not null check (status in ('ok', 'rejected')),
  error text,
  ingested_at timestamptz not null default now(),
  unique (brand_id, commit_sha)
);

-- variant_id is null for product-level events (the ones feeds use).
-- Variant-level rows exist only for back_in_stock and new_variant.
create table public.product_events (
  id bigint primary key generated always as identity,
  brand_id smallint not null references public.brands,
  product_id bigint not null references public.products on delete cascade,
  variant_id bigint references public.variants on delete cascade,
  kind text not null check (kind in ('new_product', 'removed', 'back_in_stock', 'out_of_stock',
    'price_drop', 'price_rise', 'sale_started', 'sale_ended', 'new_variant')),
  old_value jsonb,
  new_value jsonb,
  observed_at timestamptz not null,
  scan_id bigint not null references public.scans on delete cascade,
  notifiable boolean not null default true
);

create table public.ingest_cursor (
  brand_id smallint primary key references public.brands,
  last_commit_sha text not null,
  updated_at timestamptz not null default now()
);

create function public.product_search_vector(p_title text, p_brand text, p_type text, p_tags text[], p_category text)
returns tsvector language sql stable parallel safe as $$
  select setweight(to_tsvector('english', coalesce(p_title, '')), 'A')
      || setweight(to_tsvector('english', coalesce(p_brand, '')), 'B')
      || setweight(to_tsvector('english', coalesce(p_type, '') || ' ' || coalesce(p_category, '')), 'B')
      || setweight(to_tsvector('english', coalesce(array_to_string(p_tags, ' '), '')), 'C')
$$;

create index products_search_idx on public.products using gin (search);
create index products_title_trgm_idx on public.products using gin (title extensions.gin_trgm_ops);
create index products_brand_live_idx on public.products (brand_id) where removed_at is null;
create index products_discount_idx on public.products (discount_pct desc, id) where removed_at is null and discount_pct > 0;
create index products_price_change_idx on public.products (last_price_change_at desc) where last_price_change_at is not null;
create index products_restock_idx on public.products (last_restock_at desc) where last_restock_at is not null;
create index products_first_seen_idx on public.products (first_seen_at desc, id);
create index products_category_idx on public.products (category, gender) where removed_at is null;
create index variants_size_idx on public.variants (size_norm, product_id) where available and removed_at is null;
create index product_events_feed_idx on public.product_events (kind, observed_at desc) where variant_id is null;
create index product_events_product_idx on public.product_events (product_id, observed_at desc);
create index product_events_scan_idx on public.product_events (scan_id);
create index scans_brand_idx on public.scans (brand_id, ingested_at desc);

create view public.brand_health with (security_invoker = true) as
select b.id, b.slug, b.name, b.scan_tier, b.is_visible, b.ingest_enabled, b.product_count,
       b.last_scan_at, b.last_success_at,
       (select s.change_count from public.scans s
         where s.brand_id = b.id and s.status = 'ok' order by s.ingested_at desc limit 1) as last_change_count,
       (select count(*) from public.scans s
         where s.brand_id = b.id and s.status = 'rejected'
           and s.id > coalesce((select max(ok.id) from public.scans ok
                                 where ok.brand_id = b.id and ok.status = 'ok'), 0)) as rejected_since_success
from public.brands b;

-- Row-level security: the catalog is public read-only; pipeline tables are service-only.
alter table public.brands enable row level security;
alter table public.products enable row level security;
alter table public.variants enable row level security;
alter table public.price_points enable row level security;
alter table public.stock_points enable row level security;
alter table public.product_events enable row level security;
alter table public.scans enable row level security;
alter table public.ingest_cursor enable row level security;

revoke all on public.brands, public.products, public.variants, public.price_points, public.stock_points,
  public.product_events, public.scans, public.ingest_cursor, public.brand_health from anon, authenticated;
grant select on public.brands, public.products, public.variants, public.price_points, public.stock_points,
  public.product_events to anon, authenticated;

create policy brands_read on public.brands for select to anon, authenticated using (is_visible);
create policy products_read on public.products for select to anon, authenticated using (true);
create policy variants_read on public.variants for select to anon, authenticated using (true);
create policy price_points_read on public.price_points for select to anon, authenticated using (true);
create policy stock_points_read on public.stock_points for select to anon, authenticated using (true);
create policy product_events_read on public.product_events for select to anon, authenticated using (true);
