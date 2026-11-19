// Typed wrappers around the database functions in supabase/migrations/*_api.sql.
// Prices are integers in minor units (199900 = PKR 1,999.00).
import { isConfigured, supabase } from '@/lib/supabase';

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

export type SortKey = 'relevance' | 'price_asc' | 'price_desc' | 'discount' | 'recent_price_change' | 'newest';
export type FeedKind = 'price_drops' | 'back_in_stock' | 'new_arrivals';

export type SearchParams = {
  query?: string;
  brandIds?: number[];
  categories?: string[];
  genders?: string[];
  sizes?: string[];
  inStock?: boolean;
  onSale?: boolean;
  sort?: SortKey;
};

export const PAGE_SIZE = 24;

export class NotConfiguredError extends Error {
  constructor() {
    super('The app is not connected to a database yet.');
  }
}

async function rpc<T>(name: string, args: Record<string, unknown>): Promise<T> {
  if (!isConfigured) throw new NotConfiguredError();
  const { data, error } = await supabase.rpc(name, args);
  if (error) throw new Error(error.message);
  return data as T;
}

const orNull = <T>(list: T[] | undefined) => (list && list.length > 0 ? list : null);

export function searchProducts(params: SearchParams, page: number): Promise<ProductCard[]> {
  return rpc<ProductCard[]>('search_products', {
    p_query: params.query?.trim() || null,
    p_brand_ids: orNull(params.brandIds),
    p_categories: orNull(params.categories),
    p_genders: orNull(params.genders),
    p_sizes: orNull(params.sizes),
    p_in_stock: params.inStock ?? false,
    p_on_sale: params.onSale ?? false,
    p_sort: params.sort ?? 'relevance',
    p_limit: PAGE_SIZE,
    p_offset: page * PAGE_SIZE,
  });
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
