// Typed wrappers around the database functions in supabase/migrations/*_api.sql.
// Prices are integers in minor units (199900 = PKR 1,999.00).
import { NotConfiguredError } from '@/lib/api-errors';
import type { PriceStats } from '@/lib/filters';
import { currentUserId, ensureSession } from '@/lib/session';
import { isConfigured, supabase } from '@/lib/supabase';

export { NotConfiguredError };

export type Brand = {
  id: number;
  slug: string;
  name: string;
  origin_url: string;
  logo_url: string | null;
  granularity: 'variant' | 'product';
  product_count: number;
  last_success_at: string | null;
};

export type ProductCard = {
  id: number;
  brand_id: number;
  brand_slug: string;
  brand_name: string;
  title: string;
  handle: string | null;
  image: string | null;
  price_min: number | null;
  price_max: number | null;
  compare_at_max: number | null;
  discount_pct: number;
  available: boolean;
};

export type FeedItem = ProductCard & {
  event_at: string;
  old_price: number | null;
  new_price: number | null;
};

export type Variant = {
  id: number;
  title: string | null;
  size: string | null;
  options: string[] | null;
  available: boolean;
  price: number;
  compare_at_price: number | null;
};

export type ProductDetail = {
  id: number;
  title: string;
  handle: string | null;
  url: string;
  description: string | null;
  tags: string[];
  images: string[];
  category: string | null;
  gender: string | null;
  available: boolean;
  price_min: number | null;
  price_max: number | null;
  compare_at_max: number | null;
  discount_pct: number;
  first_seen_at: string;
  removed_at: string | null;
  last_price_change_at: string | null;
  last_restock_at: string | null;
  brand: {
    id: number;
    slug: string;
    name: string;
    origin_url: string;
    logo_url: string | null;
    tracks_sizes: boolean;
    affiliate_template: string | null;
  };
  variants: Variant[];
  stats: {
    lowest_price: number | null;
    highest_price: number | null;
    price_changes: number;
    tracking_since: string;
  };
};

export type SeriesPoint = {
  observed_at: string;
  price: number;
  compare_at_price: number | null;
  available: boolean;
};

export type SortKey =
  | 'relevance' | 'price_asc' | 'price_desc' | 'discount' | 'recent_price_change' | 'newest' | 'recent_activity';
export type FeedKind = 'price_drops' | 'back_in_stock' | 'new_arrivals';

/** Kinds of change a product can have appeared with in the change log (removed products are not listed). */
export const PRODUCT_CHANGE_KINDS = [
  'price_drop', 'price_rise', 'back_in_stock', 'out_of_stock', 'new_product', 'sale_started', 'sale_ended',
] as const;

export type SearchParams = {
  /** Only products that appeared in this day's change log (YYYY-MM-DD, Pakistan time). */
  changedDay?: string | null;
  /** Only products that appeared in the change log on any day. */
  changedAnyDay?: boolean;
  /** ...with one of these kinds of change. */
  changeKinds?: string[];
  query?: string;
  brandIds?: number[];
  categories?: string[];
  genders?: string[];
  sizes?: string[];
  /** Lowest price bounds in minor units (PKR x 100), inclusive. */
  priceMin?: number | null;
  priceMax?: number | null;
  inStock?: boolean;
  outOfStock?: boolean;
  /** The brand's own product types (exact values); only offered on a brand page. */
  types?: string[];
  excludeBrandIds?: number[];
  excludeCategories?: string[];
  onSale?: boolean;
  sort?: SortKey;
};

export const PAGE_SIZE = 24;


async function rpc<T>(name: string, args: Record<string, unknown>): Promise<T> {
  if (!isConfigured) throw new NotConfiguredError();
  const { data, error } = await supabase.rpc(name, args);
  if (error) throw new Error(error.message);
  return data as T;
}

const orNull = <T>(list: T[] | undefined) => (list && list.length > 0 ? list : null);

/**
 * Drop arguments that are at their default (null, undefined or false). Besides keeping requests
 * small, an older database that lacks a newer parameter still answers as long as it is unused.
 */
function compact(args: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(args).filter(([, value]) => value !== null && value !== undefined && value !== false));
}

function filterArgs(params: SearchParams) {
  return {
    p_query: params.query?.trim() || null,
    p_brand_ids: orNull(params.brandIds),
    p_categories: orNull(params.categories),
    p_genders: orNull(params.genders),
    p_sizes: orNull(params.sizes),
    p_price_min: params.priceMin ?? null,
    p_price_max: params.priceMax ?? null,
    p_in_stock: params.inStock ?? false,
    p_out_of_stock: params.outOfStock ?? false,
    p_on_sale: params.onSale ?? false,
    p_types: orNull(params.types),
    p_exclude_brand_ids: orNull(params.excludeBrandIds),
    p_exclude_categories: orNull(params.excludeCategories),
    p_changed_day: params.changedDay ?? null,
    // "Any day" without chosen kinds means any kind of change.
    p_change_kinds: orNull(params.changeKinds) ?? (params.changedAnyDay ? [...PRODUCT_CHANGE_KINDS] : null),
  };
}

export function searchProducts(params: SearchParams, page: number): Promise<ProductCard[]> {
  return rpc<ProductCard[]>('search_products', compact({
    ...filterArgs(params),
    p_sort: params.sort ?? 'relevance',
    p_limit: PAGE_SIZE,
    p_offset: page * PAGE_SIZE,
  }));
}

/** Number of matching products; the server stops counting at COUNT_CAP + 1. */
export const COUNT_CAP = 10_000;

/** Price spread of the products matching everything except their own price limits. */
export function searchPriceStats(params: SearchParams): Promise<PriceStats> {
  return rpc<PriceStats>('search_price_stats', compact(filterArgs({ ...params, priceMin: null, priceMax: null })));
}

/** Price spread of one day's changes. */
export function changePriceStats(day: string): Promise<PriceStats> {
  return rpc<PriceStats>('change_price_stats', { p_day: day });
}

export function searchCount(params: SearchParams): Promise<number> {
  return rpc<number>('search_products_count', compact(filterArgs(params)));
}

export type BrandType = { raw_type: string; products: number };

/** The brand's own product types, most common first; empty when they are switched off for the brand. */
export function brandTypes(brandId: number): Promise<BrandType[]> {
  return rpc<BrandType[]>('brand_types', { p_brand_id: brandId });
}

// ------------------------------------------------------------------ change log

export type ChangeKind =
  | 'price_drop' | 'price_rise' | 'back_in_stock' | 'out_of_stock'
  | 'new_product' | 'sale_started' | 'sale_ended' | 'removed';

export type ChangeDay = { day: string; changes: number };

export type ChangeSummaryRow = {
  brand_id: number;
  brand_slug: string;
  brand_name: string;
  kind: ChangeKind;
  changes: number;
};

export type Change = ProductCard & {
  event_id: number;
  kind: ChangeKind;
  observed_at: string;
  old_price: number | null;
  new_price: number | null;
  old_discount: number | null;
  new_discount: number | null;
  removed: boolean;
  /** Price right after the change (price events) or the product's current lowest price. */
  price: number | null;
};

export type ChangeSort = 'recent' | 'biggest_drop' | 'price_asc' | 'price_desc';

export type ChangeFilter = {
  priceMin?: number | null;
  priceMax?: number | null;
  categories?: string[];
  excludeCategories?: string[];
  genders?: string[];
  /** Stock now: 'in' or 'out'; unset for both. */
  stock?: 'in' | 'out' | null;
};

export const CHANGES_PAGE_SIZE = 30;

export function changeDays(): Promise<ChangeDay[]> {
  return rpc<ChangeDay[]>('change_days', {});
}

export function changeSummary(day: string, filter: ChangeFilter = {}): Promise<ChangeSummaryRow[]> {
  return rpc<ChangeSummaryRow[]>('change_summary', compact({
    p_day: day,
    p_price_min: filter.priceMin ?? null,
    p_price_max: filter.priceMax ?? null,
    p_categories: orNull(filter.categories),
    p_exclude_categories: orNull(filter.excludeCategories),
    p_genders: orNull(filter.genders),
    p_stock: filter.stock ?? null,
  }));
}

export function recentChanges(
  filter: ChangeFilter & {
    day: string;
    brandIds: number[];
    excludeBrandIds: number[];
    kinds: ChangeKind[];
    sort: ChangeSort;
  },
  page: number,
): Promise<Change[]> {
  return rpc<Change[]>('recent_changes', compact({
    p_day: filter.day,
    p_brand_ids: orNull(filter.brandIds),
    p_exclude_brand_ids: orNull(filter.excludeBrandIds),
    p_exclude_categories: orNull(filter.excludeCategories),
    p_genders: orNull(filter.genders),
    p_stock: filter.stock ?? null,
    p_kinds: orNull(filter.kinds),
    p_price_min: filter.priceMin ?? null,
    p_price_max: filter.priceMax ?? null,
    p_categories: orNull(filter.categories),
    p_sort: filter.sort,
    p_limit: CHANGES_PAGE_SIZE,
    p_offset: page * CHANGES_PAGE_SIZE,
  }));
}

export function homeFeed(kind: FeedKind, limit = 12): Promise<FeedItem[]> {
  return rpc<FeedItem[]>('home_feed', { p_kind: kind, p_limit: limit });
}

export function productDetail(id: number): Promise<ProductDetail | null> {
  return rpc<ProductDetail | null>('product_detail', { p_id: id });
}

export function priceSeries(productId: number, variantId: number | null): Promise<SeriesPoint[]> {
  return rpc<SeriesPoint[]>('price_series', { p_product_id: productId, p_variant_id: variantId });
}

export async function listBrands(): Promise<Brand[]> {
  if (!isConfigured) throw new NotConfiguredError();
  const { data, error } = await supabase
    .from('brands')
    .select('id, slug, name, origin_url, logo_url, granularity, product_count, last_success_at')
    .gt('product_count', 0)
    .order('name');
  if (error) throw new Error(error.message);
  return data as Brand[];
}

export async function brandBySlug(slug: string): Promise<Brand | null> {
  if (!isConfigured) throw new NotConfiguredError();
  const { data, error } = await supabase
    .from('brands')
    .select('id, slug, name, origin_url, logo_url, granularity, product_count, last_success_at')
    .eq('slug', slug)
    .maybeSingle();
  if (error) throw new Error(error.message);
  return data as Brand | null;
}

// ------------------------------------------------------------------ watchlist and alerts
// Rows are private to the signed-in (anonymous) account through row-level security.

export type WatchedProduct = {
  id: number;
  created_at: string;
  price_at_watch: number | null;
  product: {
    id: number;
    title: string;
    images: string[];
    price_min: number | null;
    compare_at_max: number | null;
    discount_pct: number;
    available: boolean;
    removed_at: string | null;
    brand: { slug: string; name: string };
  };
};

export type Alert = {
  id: number;
  kind: string;
  title: string;
  body: string | null;
  deep_link: string | null;
  created_at: string;
  read_at: string | null;
};

export async function isWatching(productId: number): Promise<boolean> {
  if (!(await currentUserId())) return false;
  const { data, error } = await supabase
    .from('watches')
    .select('id')
    .eq('product_id', productId)
    .is('variant_id', null)
    .maybeSingle();
  if (error) throw new Error(error.message);
  return Boolean(data);
}

export async function addWatch(productId: number): Promise<void> {
  await ensureSession();
  const { error } = await supabase.from('watches').insert({ product_id: productId });
  // 23505: already watching (for example a double tap) is fine.
  if (error && error.code !== '23505') throw new Error(error.message);
}

export async function removeWatch(productId: number): Promise<void> {
  if (!(await currentUserId())) return;
  const { error } = await supabase.from('watches').delete().eq('product_id', productId).is('variant_id', null);
  if (error) throw new Error(error.message);
}

export async function listWatches(): Promise<WatchedProduct[]> {
  if (!(await currentUserId())) return [];
  const { data, error } = await supabase
    .from('watches')
    .select('id, created_at, price_at_watch, product:products(id, title, images, price_min, compare_at_max, '
      + 'discount_pct, available, removed_at, brand:brands(slug, name))')
    .order('created_at', { ascending: false });
  if (error) throw new Error(error.message);
  return (data ?? []) as unknown as WatchedProduct[];
}

export async function listAlerts(): Promise<Alert[]> {
  if (!(await currentUserId())) return [];
  const { data, error } = await supabase
    .from('notifications')
    .select('id, kind, title, body, deep_link, created_at, read_at')
    .order('created_at', { ascending: false })
    .limit(100);
  if (error) throw new Error(error.message);
  return (data ?? []) as Alert[];
}

export async function markAlertsRead(): Promise<void> {
  if (!(await currentUserId())) return;
  const { error } = await supabase.from('notifications').update({ read_at: new Date().toISOString() }).is('read_at', null);
  if (error) throw new Error(error.message);
}
