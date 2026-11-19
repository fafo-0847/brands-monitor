-- Watchlist alerts. Each phone signs in anonymously (Supabase anonymous sign-ins), so watches,
-- devices and the alert inbox use the user tables and row-level security from 20261116000002.
-- An anonymous account can later be linked to Google or email without losing its watchlist.

-- Register this phone's push token for the signed-in user. A token moves to the newest user that
-- registers it (for example after a reinstall created a new anonymous account).
create function public.register_my_device(p_token text, p_platform text default null, p_app_version text default null)
returns void
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_user uuid := auth.uid();
begin
  if v_user is null then
    raise exception 'sign in first' using errcode = '28000';
  end if;
  if p_token is null or p_token !~ '^Expo(nent)?PushToken\[[A-Za-z0-9_-]{8,200}\]$' then
    raise exception 'not an Expo push token' using errcode = '22023';
  end if;
  insert into public.devices (user_id, push_token, platform, app_version, last_seen_at)
  values (v_user, p_token, case when p_platform in ('android', 'ios') then p_platform end, left(p_app_version, 40), now())
  on conflict (push_token) do update
    set user_id = excluded.user_id, platform = excluded.platform, app_version = excluded.app_version,
        last_seen_at = now();
end $$;

revoke all on function public.register_my_device from public;
grant execute on function public.register_my_device to authenticated;

-- Remember the price when an article is added, for "since you started watching" on the watchlist.
create function public.watches_fill_price() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.price_at_watch is null then
    select p.price_min into new.price_at_watch from public.products p where p.id = new.product_id;
  end if;
  return new;
end $$;
revoke all on function public.watches_fill_price() from public, anon, authenticated;

create trigger watches_fill_price before insert on public.watches
  for each row execute function public.watches_fill_price();

-- At most 300 watched articles per account.
create function public.watches_limit() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if (select count(*) from public.watches w where w.user_id = new.user_id) >= 300 then
    raise exception 'watchlist is full (300 articles)' using errcode = '54000';
  end if;
  return new;
end $$;
revoke all on function public.watches_limit() from public, anon, authenticated;

create trigger watches_limit before insert on public.watches
  for each row execute function public.watches_limit();

-- Inbox rows are written by the pipeline; the user only marks them read.
create index notifications_event_idx on public.notifications (event_id);
create index watches_user_idx on public.watches (user_id, created_at desc);
