import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { KIND_LABELS } from '@/components/change-row';
import { Chip } from '@/components/chip';
import { PriceSection } from '@/components/price-section';
import { PanelSection, SidePanel } from '@/components/side-panel';
import {
  brandTypes,
  changeDays,
  changeRounds,
  COUNT_CAP,
  listBrands,
  PRODUCT_CHANGE_KINDS,
  searchCount,
  searchPriceStats,
  type SearchParams,
  type SortKey,
} from '@/lib/api';
import { dayLabel, formatCount, roundLabel } from '@/lib/format';
import { cycle, stateOf } from '@/lib/tristate';

export const CATEGORIES = [
  { key: 'unstitched', label: 'Unstitched' },
  { key: 'eastern', label: 'Eastern' },
  { key: 'western', label: 'Western' },
  { key: 'formal', label: 'Formal' },
  { key: 'footwear', label: 'Footwear' },
  { key: 'bags-accessories', label: 'Bags & accessories' },
  { key: 'fragrance-beauty', label: 'Fragrance & beauty' },
  { key: 'home', label: 'Home' },
];

export const GENDERS = [
  { key: 'women', label: 'Women' },
  { key: 'men', label: 'Men' },
  { key: 'kids', label: 'Kids' },
];

const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];
const FEW_TYPES = 12;

const SORTS: { key: SortKey; label: string; needsQuery?: boolean }[] = [
  { key: 'relevance', label: 'Best match', needsQuery: true },
  { key: 'recent_activity', label: 'Recent activity' },
  { key: 'discount', label: 'Biggest discount' },
  { key: 'price_asc', label: 'Price: low to high' },
  { key: 'price_desc', label: 'Price: high to low' },
  { key: 'recent_price_change', label: 'Recent price change' },
  { key: 'newest', label: 'Newest' },
];

type Props = {
  visible: boolean;
  value: SearchParams;
  onClose: () => void;
  onApply: (next: SearchParams) => void;
  /** On a brand page: offer the brand's own categories instead of a brands list. */
  brandId?: number;
  /** Offer size filters (hidden for brands without size data). */
  showSizes?: boolean;
};

function toggle<T>(list: T[] | undefined, key: T): T[] {
  const current = list ?? [];
  return current.includes(key) ? current.filter((item) => item !== key) : [...current, key];
}

/** Everything that keeps the search words and brand page context but no other filter. */
function cleared(value: SearchParams, brandId?: number): SearchParams {
  return { query: value.query, sort: value.sort, ...(brandId ? { brandIds: [brandId] } : {}) };
}

export function ProductFilterPanel(props: Props) {
  // Rebuilt each time the panel opens, so it starts from the filters currently applied.
  return props.visible ? <OpenPanel {...props} /> : null;
}

function OpenPanel({ visible, value, onClose, onApply, brandId, showSizes = true }: Props) {
  const [draft, setDraft] = useState<SearchParams>(value);
  const set = (patch: Partial<SearchParams>) => setDraft((current) => ({ ...current, ...patch }));

  const count = useQuery({ queryKey: ['count', draft], queryFn: () => searchCount(draft) });
  const stats = useQuery({
    queryKey: ['price-stats', { ...draft, priceMin: null, priceMax: null }],
    queryFn: () => searchPriceStats(draft),
  });
  const days = useQuery({ queryKey: ['change-days'], queryFn: changeDays });
  // Older saved state may still hold the single-day form.
  const chosenDays = draft.changedDays ?? (draft.changedDay ? [draft.changedDay] : []);
  const rounds = useQuery({
    queryKey: ['change-rounds', chosenDays],
    queryFn: () => changeRounds(chosenDays),
    enabled: chosenDays.length > 0,
  });
  const brands = useQuery({ queryKey: ['brands'], queryFn: listBrands, enabled: !brandId });
  const types = useQuery({ queryKey: ['brand-types', brandId], queryFn: () => brandTypes(brandId!), enabled: Boolean(brandId) });
  const [allTypes, setAllTypes] = useState(false);

  const sort = draft.sort ?? (draft.query ? 'relevance' : 'recent_activity');
  const changedOn = chosenDays.length > 0 ? 'days' : draft.changedAnyDay ? 'any' : 'off';
  const setDays = (next: string[]) =>
    set({ changedDays: next, changedDay: null, changedRounds: [], changedAnyDay: false });
  const categoryLists = { include: draft.categories ?? [], exclude: draft.excludeCategories ?? [] };
  const brandLists = { include: draft.brandIds ?? [], exclude: draft.excludeBrandIds ?? [] };
  const stock = draft.inStock ? 'in' : draft.outOfStock ? 'out' : 'any';
  const typeList = types.data ?? [];
  const shownTypes = allTypes
    ? typeList
    : typeList.filter((item, index) => index < FEW_TYPES || draft.types?.includes(item.raw_type));

  const applyLabel = count.isPending ? 'Show results'
    : count.isError ? 'Show results'
    : `Show ${formatCount(count.data, COUNT_CAP)} ${count.data === 1 ? 'product' : 'products'}`;

  return (
    <SidePanel
      visible={visible}
      title="Filters & sort"
      onClose={onClose}
      onClear={() => setDraft(cleared(draft, brandId))}
      onApply={() => {
        onApply(draft);
        onClose();
      }}
      applyLabel={applyLabel}>
      <PanelSection title="Sort by">
        {SORTS.filter((item) => !item.needsQuery || draft.query).map((item) => (
          <Chip key={item.key} label={item.label} selected={sort === item.key} onPress={() => set({ sort: item.key })} />
        ))}
      </PanelSection>

      <PanelSection title="In the change log" hint="Only articles that changed on the chosen days (or any day).">
        <Chip label="Off" selected={changedOn === 'off'}
          onPress={() => set({ changedDay: null, changedDays: [], changedRounds: [], changedAnyDay: false, changeKinds: [] })} />
        <Chip label="Any day" selected={changedOn === 'any'}
          onPress={() => set({ changedDay: null, changedDays: [], changedRounds: [], changedAnyDay: true })} />
        {(days.data ?? []).slice(0, 14).map((item) => (
          <Chip
            key={item.day}
            label={dayLabel(item.day)}
            selected={chosenDays.includes(item.day)}
            onPress={() => setDays(toggle(chosenDays, item.day))}
          />
        ))}
      </PanelSection>
      {changedOn === 'days' && (rounds.data?.length ?? 0) > 0 ? (
        <PanelSection title="Checks" hint="Each check looks at every brand once. Whole day shows them all.">
          <Chip label="Whole day" selected={(draft.changedRounds ?? []).length === 0} onPress={() => set({ changedRounds: [] })} />
          {(rounds.data ?? []).map((item) => (
            <Chip
              key={item.round_id}
              label={roundLabel(item.started_at, item.ended_at, chosenDays)}
              selected={draft.changedRounds?.includes(item.round_id)}
              onPress={() => set({ changedRounds: toggle(draft.changedRounds, item.round_id) })}
              accessibilityLabel={`Check ${roundLabel(item.started_at, item.ended_at, chosenDays)}`}
            />
          ))}
        </PanelSection>
      ) : null}
      {changedOn !== 'off' ? (
        <PanelSection title="Kind of change" hint="None selected means any kind.">
          {PRODUCT_CHANGE_KINDS.map((kind) => (
            <Chip
              key={kind}
              label={KIND_LABELS[kind]}
              selected={draft.changeKinds?.includes(kind)}
              onPress={() => set({ changeKinds: toggle(draft.changeKinds, kind) })}
            />
          ))}
        </PanelSection>
      ) : null}

      {brandId && typeList.length >= 2 ? (
        <PanelSection title="Brand's own categories">
          {shownTypes.map((item) => (
            <Chip
              key={item.raw_type}
              label={`${item.raw_type} · ${formatCount(item.products)}`}
              selected={draft.types?.includes(item.raw_type)}
              onPress={() => set({ types: toggle(draft.types, item.raw_type) })}
            />
          ))}
          {typeList.length > FEW_TYPES ? (
            <Chip label={allTypes ? 'Fewer' : `More (${typeList.length - FEW_TYPES})`} onPress={() => setAllTypes(!allTypes)} />
          ) : null}
        </PanelSection>
      ) : null}

      <PanelSection title="Category" hint="Tap once to show only it, twice to hide it.">
        {CATEGORIES.map((item) => (
          <Chip
            key={item.key}
            label={item.label}
            selected={stateOf(categoryLists, item.key) === 'include'}
            excluded={stateOf(categoryLists, item.key) === 'exclude'}
            onPress={() => {
              const next = cycle(categoryLists, item.key);
              set({ categories: next.include, excludeCategories: next.exclude });
            }}
          />
        ))}
      </PanelSection>

      {!brandId && (brands.data?.length ?? 0) > 1 ? (
        <PanelSection title="Brand" hint="Tap once to show only it, twice to hide it.">
          {(brands.data ?? []).map((brand) => (
            <Chip
              key={brand.id}
              label={brand.name}
              selected={stateOf(brandLists, brand.id) === 'include'}
              excluded={stateOf(brandLists, brand.id) === 'exclude'}
              onPress={() => {
                const next = cycle(brandLists, brand.id);
                set({ brandIds: next.include, excludeBrandIds: next.exclude });
              }}
            />
          ))}
        </PanelSection>
      ) : null}

      <PriceSection
        min={draft.priceMin}
        max={draft.priceMax}
        stats={stats.data}
        onChange={(priceMin, priceMax) => set({ priceMin, priceMax })}
      />

      <PanelSection title="Stock and sale">
        <Chip label="Any stock" selected={stock === 'any'} onPress={() => set({ inStock: false, outOfStock: false })} />
        <Chip label="In stock" selected={stock === 'in'} onPress={() => set({ inStock: true, outOfStock: false })} />
        <Chip label="Out of stock" selected={stock === 'out'} onPress={() => set({ inStock: false, outOfStock: true })} />
        <Chip label="On sale" selected={Boolean(draft.onSale)} onPress={() => set({ onSale: !draft.onSale })} />
      </PanelSection>

      <PanelSection title="For">
        {GENDERS.map((item) => (
          <Chip
            key={item.key}
            label={item.label}
            selected={draft.genders?.includes(item.key)}
            onPress={() => set({ genders: toggle(draft.genders, item.key) })}
          />
        ))}
      </PanelSection>

      {showSizes ? (
        <PanelSection title="Size in stock">
          {SIZES.map((size) => (
            <Chip
              key={size}
              label={size}
              selected={draft.sizes?.includes(size)}
              onPress={() => set({ sizes: toggle(draft.sizes, size) })}
              accessibilityLabel={`Size ${size}`}
            />
          ))}
        </PanelSection>
      ) : null}
    </SidePanel>
  );
}
