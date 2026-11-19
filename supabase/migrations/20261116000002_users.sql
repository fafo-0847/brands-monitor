-- User-owned tables (PRD section 7). Every row is visible only to its owner.

create table public.profiles (
  id uuid primary key references auth.users on delete cascade,
  display_name text,
  quiet_start time not null default '23:00',
  quiet_end time not null default '08:00',
  timezone text not null default 'Asia/Karachi',
  prefs jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table public.brand_follows (
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  brand_id smallint not null references public.brands on delete cascade,
  muted boolean not null default false,
  created_at timestamptz not null default now(),
  primary key (user_id, brand_id)
);

create table public.watches (
  id bigint primary key generated always as identity,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  product_id bigint not null references public.products on delete cascade,
  variant_id bigint references public.variants on delete cascade,
  on_restock boolean not null default true,
  on_price_drop boolean not null default true,
  on_any_price boolean not null default false,
  price_at_watch bigint,
  created_at timestamptz not null default now(),
  unique nulls not distinct (user_id, product_id, variant_id)
);

create table public.devices (
  id bigint primary key generated always as identity,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  push_token text unique not null,
  platform text,
  app_version text,
  last_seen_at timestamptz not null default now()
);

create table public.notifications (
  id bigint primary key generated always as identity,
  user_id uuid not null references auth.users on delete cascade,
  event_id bigint references public.product_events on delete set null,
  kind text not null,
  title text not null,
  body text,
  deep_link text,
  created_at timestamptz not null default now(),
  sent_at timestamptz,
  read_at timestamptz,
  status text not null default 'pending' check (status in ('pending', 'sent', 'failed', 'expired', 'held')),
  unique (user_id, event_id)
);

create index watches_product_idx on public.watches (product_id);
create index watches_variant_idx on public.watches (variant_id) where variant_id is not null;
create index brand_follows_brand_idx on public.brand_follows (brand_id);
create index devices_user_idx on public.devices (user_id);
create index notifications_inbox_idx on public.notifications (user_id, created_at desc);
create index notifications_pending_idx on public.notifications (status) where status in ('pending', 'held');

create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id) values (new.id) on conflict do nothing;
  return new;
end $$;
revoke all on function public.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

alter table public.profiles enable row level security;
alter table public.brand_follows enable row level security;
alter table public.watches enable row level security;
alter table public.devices enable row level security;
alter table public.notifications enable row level security;

revoke all on public.profiles, public.brand_follows, public.watches, public.devices, public.notifications
  from anon, authenticated;
grant select on public.profiles to authenticated;
grant update (display_name, quiet_start, quiet_end, timezone, prefs) on public.profiles to authenticated;
grant select, insert, update, delete on public.brand_follows, public.watches, public.devices to authenticated;
grant select on public.notifications to authenticated;
grant update (read_at) on public.notifications to authenticated;

create policy profiles_own on public.profiles for all to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));
create policy brand_follows_own on public.brand_follows for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy watches_own on public.watches for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy devices_own on public.devices for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy notifications_own on public.notifications for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
