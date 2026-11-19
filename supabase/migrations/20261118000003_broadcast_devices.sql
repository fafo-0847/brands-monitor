-- Phones that receive the "new data is in" notification after each ingest run.
-- There are no accounts yet, so a phone registers anonymously with its Expo push token. The
-- table is not readable by the app; the pipeline reads it with the database owner role.
create table public.broadcast_devices (
  push_token text primary key
    check (push_token ~ '^Expo(nent)?PushToken\[[A-Za-z0-9_-]{8,200}\]$'),
  platform text check (platform in ('android', 'ios')),
  app_version text check (length(app_version) <= 40),
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);
alter table public.broadcast_devices enable row level security;
revoke all on public.broadcast_devices from anon, authenticated;

-- Called by the app on start. Re-registering only refreshes last_seen_at. New registrations stop
-- at 500 phones, which is far beyond a private test and limits what a misused anon key can add.
create function public.register_device(p_token text, p_platform text default null, p_app_version text default null)
returns void
language plpgsql volatile security definer set search_path = '' as $$
begin
  if p_token is null or p_token !~ '^Expo(nent)?PushToken\[[A-Za-z0-9_-]{8,200}\]$' then
    raise exception 'not an Expo push token' using errcode = '22023';
  end if;
  update public.broadcast_devices
     set last_seen_at = now(), platform = coalesce(p_platform, platform), app_version = left(p_app_version, 40)
   where push_token = p_token;
  if found then
    return;
  end if;
  if (select count(*) from public.broadcast_devices) >= 500 then
    raise exception 'device limit reached' using errcode = '54000';
  end if;
  insert into public.broadcast_devices (push_token, platform, app_version)
  values (p_token, case when p_platform in ('android', 'ios') then p_platform end, left(p_app_version, 40))
  on conflict (push_token) do update set last_seen_at = now();
end $$;

revoke all on function public.register_device from public;
grant execute on function public.register_device to anon, authenticated, service_role;
