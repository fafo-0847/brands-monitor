-- Supabase's API loads pg_safeupdate, which rejects DELETE without a WHERE clause ("DELETE requires a
-- WHERE clause", HTTP 400). claim_moved_watches emptied its table that way, so the phone's call failed
-- twice (2026-11-21 and 2026-11-22) while the same call from the SQL editor worked. Same function,
-- with an explicit WHERE.
create or replace function public.claim_moved_watches() returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_user uuid := auth.uid();
  v_claimed integer;
begin
  if v_user is null then
    raise exception 'sign in first' using errcode = '28000';
  end if;
  with taken as (
    delete from private.moved_watches where true returning *
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
