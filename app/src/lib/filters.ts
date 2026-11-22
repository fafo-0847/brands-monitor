// Filter helpers: price ranges that fit the current results, and how many filters are on.
// Pure: no React or React Native imports, so they run under `node --test`.

/** Price spread from search_price_stats / change_price_stats (minor units). */
export type PriceStats = { n: number; min: number | null; max: number | null; q: number[] | null };

/** A price range in minor units; null means open-ended. */
export type PriceBand = { label: string; min: number | null; max: number | null };

const groupThousands = (value: number) => String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',');

/** Round rupees to a step that reads well for their size: 50, 100, 500, 1,000, 5,000 ... */
export function niceRupees(rupees: number): number {
  if (rupees <= 0) return 0;
  const steps = [50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000, 25_000, 50_000, 100_000];
  const step = steps.find((candidate) => rupees / candidate <= 10) ?? 100_000;
  return Math.max(step, Math.round(rupees / step) * step);
}

/**
 * Up to five ranges from the 20/40/60/80% points of the current results, each edge rounded to a
 * readable number. Fewer when prices bunch together; none when there is nothing to split.
 */
export function priceBands(stats: PriceStats | null | undefined): PriceBand[] {
  if (!stats || stats.n < 2 || stats.min === null || stats.max === null || stats.min === stats.max) return [];
  const lowest = stats.min / 100;
  const highest = stats.max / 100;
  const edges: number[] = [];
  for (const point of stats.q ?? []) {
    // Prefer a round edge; when prices bunch together, round less so the edge stays inside the range.
    const candidates = [niceRupees(point / 100), Math.round(point / 100 / 50) * 50, Math.round(point / 100 / 10) * 10];
    const edge = candidates.find((value) => value > lowest && value < highest);
    if (edge !== undefined && !edges.includes(edge)) edges.push(edge);
  }
  edges.sort((a, b) => a - b);
  if (edges.length === 0) return [];
  const bands: PriceBand[] = [{ label: `Under ${groupThousands(edges[0])}`, min: null, max: edges[0] * 100 - 1 }];
  for (let index = 1; index < edges.length; index += 1) {
    bands.push({
      label: `${groupThousands(edges[index - 1])} – ${groupThousands(edges[index])}`,
      min: edges[index - 1] * 100,
      max: edges[index] * 100 - 1,
    });
  }
  const last = edges[edges.length - 1];
  bands.push({ label: `${groupThousands(last)} and up`, min: last * 100, max: null });
  return bands;
}

/** Parse a typed rupee amount ("2,500", " 2500 ") into minor units; null when empty or not a number. */
export function rupeesInput(text: string): number | null {
  const digits = text.replace(/[^0-9]/g, '');
  return digits ? Number(digits) * 100 : null;
}

const hasList = (list: unknown[] | undefined | null) => Boolean(list && list.length > 0);

/** How many filters are on (sort and the search words are not counted). */
export function activeFilterCount(filters: {
  brandIds?: number[];
  excludeBrandIds?: number[];
  categories?: string[];
  excludeCategories?: string[];
  genders?: string[];
  sizes?: string[];
  types?: string[];
  priceMin?: number | null;
  priceMax?: number | null;
  inStock?: boolean;
  outOfStock?: boolean;
  onSale?: boolean;
  changedDay?: string | null;
  changedDays?: string[];
  changedRounds?: number[];
  changedAnyDay?: boolean;
  changeKinds?: string[];
  stock?: 'in' | 'out' | null;
}): number {
  return [
    hasList(filters.brandIds) || hasList(filters.excludeBrandIds),
    hasList(filters.categories) || hasList(filters.excludeCategories),
    hasList(filters.genders),
    hasList(filters.sizes),
    hasList(filters.types),
    filters.priceMin !== null && filters.priceMin !== undefined
      || (filters.priceMax !== null && filters.priceMax !== undefined),
    Boolean(filters.inStock || filters.outOfStock || filters.stock),
    Boolean(filters.onSale),
    Boolean(filters.changedDay || filters.changedAnyDay || hasList(filters.changedDays) || hasList(filters.changeKinds)),
  ].filter(Boolean).length;
}
