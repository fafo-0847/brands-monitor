-- Smaller database (owner's request, 2026-11-19; the free plan stops writes above 500 MB).
-- Rows are trimmed and old data removed by pipeline/maintain.py in small batches, outside a
-- transaction, so the database does not grow while it happens. This migration only drops
-- indexes, which frees their space at once, and adds what maintain.py needs.

-- Typo-tolerant search: about 25 MB for the selected brands. Search now needs the words to match.
drop index if exists public.products_title_trgm_idx;
-- Nothing sorts or filters by last_restock_at.
drop index if exists public.products_restock_idx;
-- Covered by the unique (brand_id, external_id) index.
drop index if exists public.products_brand_live_idx;

-- Same rule as normalize.clean_image_url: drop Shopify's changing ?v=<digits> parameter.
create function private.clean_image_url(p_url text) returns text
language sql immutable parallel safe as $$
  select regexp_replace(regexp_replace(p_url, '([?&])v=[0-9]+(?=&|$)&?', '\1', 'g'), '[?&]$', '')
$$;
revoke all on function private.clean_image_url from public;

create or replace function private.search_clause(
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
    -- No fuzzy (typo) fallback since 20261119000001: its trigram index was dropped to save space.
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
  if p_exclude_categories is not null then
    where_sql := where_sql || ' and (p.category is null or p.category <> all($15))';
  end if;
end $$;
