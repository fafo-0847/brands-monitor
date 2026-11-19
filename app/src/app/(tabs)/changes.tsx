import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChangeRow, KIND_LABELS, KIND_ORDER } from '@/components/change-row';
import { Chip } from '@/components/chip';
import { PriceSection } from '@/components/price-section';
import { CATEGORIES, GENDERS } from '@/components/product-filter-panel';
import { FilterButton, PanelSection, SidePanel } from '@/components/side-panel';
import { ErrorMessage, Loading, Message } from '@/components/states';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import {
  changeDays,
  changePriceStats,
  changeSummary,
  CHANGES_PAGE_SIZE,
  recentChanges,
  type ChangeDay,
  type ChangeFilter,
  type ChangeKind,
  type ChangeSort,
  type ChangeSummaryRow,
} from '@/lib/api';
import { activeFilterCount } from '@/lib/filters';
import { dayLabel, formatCount } from '@/lib/format';
import { cycle, passes, stateOf, type TriLists } from '@/lib/tristate';

/** Everything the Changes tab is filtered by. The day is chosen in the panel like any other filter. */
type ChangeState = {
  day: string | null;
  sort: ChangeSort;
  kinds: ChangeKind[];
  brands: TriLists<number>;
  filter: ChangeFilter;
};

const EMPTY: Omit<ChangeState, 'day'> = { sort: 'recent', kinds: [], brands: { include: [], exclude: [] }, filter: {} };

const SORTS: { key: ChangeSort; label: string }[] = [
  { key: 'recent', label: 'Newest' },
  { key: 'biggest_drop', label: 'Biggest drop' },
  { key: 'price_asc', label: 'Price: low to high' },
  { key: 'price_desc', label: 'Price: high to low' },
];

const STOCK: { key: 'in' | 'out' | null; label: string }[] = [
  { key: null, label: 'Any stock' },
  { key: 'in', label: 'In stock now' },
  { key: 'out', label: 'Sold out now' },
];

function sum(rows: ChangeSummaryRow[], keep: (row: ChangeSummaryRow) => boolean): number {
  return rows.reduce((total, row) => (keep(row) ? total + row.changes : total), 0);
}

function toggle<T>(list: T[] | undefined, key: T): T[] {
  const current = list ?? [];
  return current.includes(key) ? current.filter((item) => item !== key) : [...current, key];
}

/** Counts for a state: the server applies price, category, gender and stock; brand and kind are applied here. */
function useSummary(day: string | null, filter: ChangeFilter) {
  return useQuery({
    queryKey: ['change-summary', day, filter],
    queryFn: () => changeSummary(day!, filter),
    enabled: Boolean(day),
  });
}

/** Everything that changed across brands in each check, with earlier days in the filter panel. */
export default function ChangesScreen() {
  const days = useQuery({ queryKey: ['change-days'], queryFn: changeDays });
  const [state, setState] = useState<ChangeState>({ day: null, ...EMPTY });
  const [panelOpen, setPanelOpen] = useState(false);
  const day = state.day ?? days.data?.[0]?.day ?? null;
  const theme = useTheme();

  const summary = useSummary(day, state.filter);
  const total = sum(summary.data ?? [], (row) => passes(state.brands, row.brand_id)
    && (state.kinds.length === 0 || state.kinds.includes(row.kind)));

  const list = useInfiniteQuery({
    queryKey: ['changes', day, state],
    queryFn: ({ pageParam }) => recentChanges({
      ...state.filter,
      day: day!,
      brandIds: state.brands.include,
      excludeBrandIds: state.brands.exclude,
      kinds: state.kinds,
      sort: state.sort,
    }, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.length === CHANGES_PAGE_SIZE ? pages.length : undefined),
    enabled: Boolean(day),
  });
  const items = list.data?.pages.flat() ?? [];
  const filterCount = activeFilterCount({
    ...state.filter,
    brandIds: state.brands.include,
    excludeBrandIds: state.brands.exclude,
    changeKinds: state.kinds,
  });

  if (days.isPending) return <Screen><Loading /></Screen>;
  if (days.isError) return <Screen><ErrorMessage error={days.error} onRetry={() => days.refetch()} /></Screen>;
  if (!day) {
    return (
      <Screen>
        <Message
          title="No changes yet"
          detail="Changes appear after the second check of a brand, when there is something to compare."
        />
      </Screen>
    );
  }

  return (
    <Screen>
      <View style={styles.header}>
        <View style={styles.titles}>
          <ThemedText style={styles.heading} accessibilityRole="header">Changes</ThemedText>
          <ThemedText type="smallBold" themeColor="textSecondary" accessibilityLiveRegion="polite">
            {dayLabel(day)} · {summary.isPending ? 'counting…' : `${formatCount(total)} ${total === 1 ? 'change' : 'changes'}`}
            {state.sort !== 'recent' ? ` · ${SORTS.find((item) => item.key === state.sort)?.label}` : ''}
          </ThemedText>
        </View>
        <FilterButton count={filterCount} onPress={() => setPanelOpen(true)} />
      </View>
      <FlatList
        data={items}
        keyExtractor={(item) => String(item.event_id)}
        renderItem={({ item }) => <ChangeRow change={item} />}
        ListEmptyComponent={
          list.isPending ? <Loading />
          : list.isError ? <ErrorMessage error={list.error} onRetry={() => list.refetch()} />
          : <Message title="No changes match" detail="Open Filters to clear one or pick another day." />
        }
        ListFooterComponent={
          list.isFetchingNextPage ? <ActivityIndicator style={styles.footer} color={theme.textSecondary} /> : <View style={styles.footer} />
        }
        onEndReached={() => {
          if (list.hasNextPage && !list.isFetchingNextPage) list.fetchNextPage();
        }}
        onEndReachedThreshold={0.6}
        refreshing={list.isRefetching && !list.isFetchingNextPage}
        onRefresh={() => {
          days.refetch();
          summary.refetch();
          list.refetch();
        }}
        contentContainerStyle={styles.content}
      />
      {panelOpen ? (
        <ChangeFilterPanel
          days={days.data}
          value={{ ...state, day }}
          onClose={() => setPanelOpen(false)}
          onApply={setState}
        />
      ) : null}
    </Screen>
  );
}

function Screen({ children }: { children: React.ReactNode }) {
  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView style={styles.screen} edges={['top']}>{children}</SafeAreaView>
    </ThemedView>
  );
}

function ChangeFilterPanel({ days, value, onClose, onApply }: {
  days: ChangeDay[];
  value: ChangeState;
  onClose: () => void;
  onApply: (next: ChangeState) => void;
}) {
  const [draft, setDraft] = useState<ChangeState>(value);
  const set = (patch: Partial<ChangeState>) => setDraft((current) => ({ ...current, ...patch }));
  const setFilter = (patch: Partial<ChangeFilter>) => setDraft((current) => ({ ...current, filter: { ...current.filter, ...patch } }));

  const summary = useSummary(draft.day, draft.filter);
  const rows = useMemo(() => summary.data ?? [], [summary.data]);
  const stats = useQuery({ queryKey: ['change-price-stats', draft.day], queryFn: () => changePriceStats(draft.day!), enabled: Boolean(draft.day) });

  const total = sum(rows, (row) => passes(draft.brands, row.brand_id) && (draft.kinds.length === 0 || draft.kinds.includes(row.kind)));
  const kindCount = (kind: ChangeKind) => sum(rows, (row) => row.kind === kind && passes(draft.brands, row.brand_id));
  const brands = useMemo(() => {
    const byBrand = new Map<number, { id: number; name: string; changes: number }>();
    for (const row of rows) {
      if (draft.kinds.length > 0 && !draft.kinds.includes(row.kind)) continue;
      const entry = byBrand.get(row.brand_id) ?? { id: row.brand_id, name: row.brand_name, changes: 0 };
      entry.changes += row.changes;
      byBrand.set(row.brand_id, entry);
    }
    // Hidden brands keep their chip so they can be shown again.
    for (const id of draft.brands.exclude) {
      if (!byBrand.has(id)) {
        const name = rows.find((row) => row.brand_id === id)?.brand_name ?? `Brand ${id}`;
        byBrand.set(id, { id, name, changes: 0 });
      }
    }
    return [...byBrand.values()].sort((a, b) => b.changes - a.changes || a.name.localeCompare(b.name));
  }, [rows, draft.kinds, draft.brands.exclude]);
  const categoryLists = { include: draft.filter.categories ?? [], exclude: draft.filter.excludeCategories ?? [] };

  return (
    <SidePanel
      visible
      title="Filters & sort"
      onClose={onClose}
      onClear={() => setDraft({ day: draft.day, ...EMPTY })}
      onApply={() => {
        onApply(draft);
        onClose();
      }}
      applyLabel={summary.isPending ? 'Show changes' : `Show ${formatCount(total)} ${total === 1 ? 'change' : 'changes'}`}>
      <PanelSection title="Day">
        {days.map((item) => (
          <Chip
            key={item.day}
            label={`${dayLabel(item.day)} · ${formatCount(item.changes)}`}
            selected={item.day === draft.day}
            onPress={() => set({ day: item.day })}
            accessibilityLabel={`${dayLabel(item.day)}, ${item.changes} changes`}
          />
        ))}
      </PanelSection>

      <PanelSection title="Sort by">
        {SORTS.map((item) => (
          <Chip key={item.key} label={item.label} selected={draft.sort === item.key} onPress={() => set({ sort: item.key })} />
        ))}
      </PanelSection>

      <PanelSection title="Kind of change" hint="None selected means every kind.">
        {KIND_ORDER.filter((kind) => kindCount(kind) > 0 || draft.kinds.includes(kind)).map((kind) => (
          <Chip
            key={kind}
            label={`${KIND_LABELS[kind]} · ${formatCount(kindCount(kind))}`}
            selected={draft.kinds.includes(kind)}
            onPress={() => set({ kinds: toggle(draft.kinds, kind) })}
          />
        ))}
      </PanelSection>

      <PanelSection title="Stock now">
        {STOCK.map((item) => (
          <Chip
            key={item.label}
            label={item.label}
            selected={(draft.filter.stock ?? null) === item.key}
            onPress={() => setFilter({ stock: item.key })}
          />
        ))}
      </PanelSection>

      <PanelSection title="For">
        {GENDERS.map((item) => (
          <Chip
            key={item.key}
            label={item.label}
            selected={draft.filter.genders?.includes(item.key)}
            onPress={() => setFilter({ genders: toggle(draft.filter.genders, item.key) })}
          />
        ))}
      </PanelSection>

      <PanelSection title="Brand" hint="Tap once to show only it, twice to hide it.">
        {brands.map((brand) => (
          <Chip
            key={brand.id}
            label={`${brand.name} · ${formatCount(brand.changes)}`}
            selected={stateOf(draft.brands, brand.id) === 'include'}
            excluded={stateOf(draft.brands, brand.id) === 'exclude'}
            onPress={() => set({ brands: cycle(draft.brands, brand.id) })}
          />
        ))}
      </PanelSection>

      <PanelSection title="Category" hint="Tap once to show only it, twice to hide it.">
        {CATEGORIES.map((item) => (
          <Chip
            key={item.key}
            label={item.label}
            selected={stateOf(categoryLists, item.key) === 'include'}
            excluded={stateOf(categoryLists, item.key) === 'exclude'}
            onPress={() => {
              const next = cycle(categoryLists, item.key);
              setFilter({ categories: next.include, excludeCategories: next.exclude });
            }}
          />
        ))}
      </PanelSection>

      <PriceSection
        min={draft.filter.priceMin}
        max={draft.filter.priceMax}
        stats={stats.data}
        onChange={(priceMin, priceMax) => setFilter({ priceMin, priceMax })}
      />
    </SidePanel>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    paddingHorizontal: Spacing.three,
    paddingTop: Spacing.three,
    paddingBottom: Spacing.two,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  titles: { flex: 1, gap: Spacing.half },
  heading: { fontSize: 26, lineHeight: 32, fontWeight: 700 },
  content: {
    paddingHorizontal: Spacing.three,
    paddingBottom: BottomTabInset + Spacing.five,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  footer: { height: Spacing.six },
});
