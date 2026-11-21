-- Moving the database to a new Supabase project (pipeline/copy_db.py). Anonymous accounts belong
-- to the old project and cannot come along, so the watched articles wait here and the first
-- account to open the watchlist on the new project takes them over. This is a single-owner test
-- app; the table is empty except right after a move.
create table private.moved_watches (
  product_id bigint not null references public.products on delete cascade,
  variant_id bigint references public.variants on delete cascade,
  on_restock boolean not null,
  on_price_drop boolean not null,
  on_any_price boolean not null,
  price_at_watch bigint,
  created_at timestamptz not null
);
alter table private.moved_watches enable row level security;
revoke all on private.moved_watches from public, anon, authenticated;

-- True while moved watches are waiting, so the app only creates an account when there is
-- something to take over.
create function public.moved_watches_waiting() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from private.moved_watches)
$$;
revoke all on function public.moved_watches_waiting() from public;
grant execute on function public.moved_watches_waiting() to anon, authenticated, service_role;

-- Gives every waiting watch to the calling account and empties the table. Returns how many.
create function public.claim_moved_watches() returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_user uuid := auth.uid();
  v_claimed integer;
begin
  if v_user is null then
    raise exception 'sign in first' using errcode = '28000';
  end if;
  with taken as (
    delete from private.moved_watches returning *
  )
  insert into public.watches (user_id, product_id, variant_id, on_restock, on_price_drop, on_any_price,
                              price_at_watch, created_at)
  select distinct on (product_id, variant_id) v_user, product_id, variant_id, on_restock, on_price_drop,
         on_any_price, price_at_watch, created_at
    from taken
   order by product_id, variant_id, created_at
   limit greatest(0, 300 - (select count(*) from public.watches w where w.user_id = v_user))
  on conflict do nothing;
  get diagnostics v_claimed = row_count;
  return v_claimed;
end $$;
revoke all on function public.claim_moved_watches() from public, anon;
grant execute on function public.claim_moved_watches() to authenticated, service_role;
