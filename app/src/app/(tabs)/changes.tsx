import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChangeRow, KIND_LABELS, KIND_ORDER } from '@/components/change-row';
import { Chip } from '@/components/chip';
import { CATEGORIES, PriceRow } from '@/components/filter-bar';
import { ErrorMessage, Loading, Message } from '@/components/states';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import {
  changeDays,
  changeSummary,
  CHANGES_PAGE_SIZE,
  recentChanges,
  type ChangeFilter,
  type ChangeKind,
  type ChangeSort,
  type ChangeSummaryRow,
} from '@/lib/api';
import { dayLabel, formatCount } from '@/lib/format';
import { cycle, passes, stateOf, type TriLists } from '@/lib/tristate';

/** Everything that changed across brands in one daily scrape, with earlier days one tap away. */
export default function ChangesScreen() {
  const days = useQuery({ queryKey: ['change-days'], queryFn: changeDays });
  const [picked, setPicked] = useState<string | null>(null);
  const day = picked ?? days.data?.[0]?.day ?? null;

  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView style={styles.screen} edges={['top']}>
        {days.isPending ? <Loading />
          : days.isError ? <ErrorMessage error={days.error} onRetry={() => days.refetch()} />
          : !day ? (
            <Message
              title="No changes yet"
              detail="Changes appear after the second daily check of a brand, when there is something to compare."
            />
          ) : (
            <DayChanges
              day={day}
              days={days.data}
              onPickDay={setPicked}
            />
          )}
      </SafeAreaView>
    </ThemedView>
  );
}

function DayChanges({ day, days, onPickDay }: {
  day: string;
  days: { day: string; changes: number }[];
  onPickDay: (day: string) => void;
}) {
  const theme = useTheme();
  const [brandLists, setBrandLists] = useState<TriLists<number>>({ include: [], exclude: [] });
  const [kinds, setKinds] = useState<ChangeKind[]>([]);
  const [sort, setSort] = useState<ChangeSort>('recent');
  const [filter, setFilter] = useState<ChangeFilter>({});
  const summary = useQuery({ queryKey: ['change-summary', day, filter], queryFn: () => changeSummary(day, filter) });
  const rows = useMemo(() => summary.data ?? [], [summary.data]);

  // Brand include/exclude is applied here, not on the server, so hidden brands keep their chip
  // (with its count) and can be shown again.
  const total = sum(rows, (row) => passes(brandLists, row.brand_id)
    && (kinds.length === 0 || kinds.includes(row.kind)));
  const kindCount = (kind: ChangeKind) => sum(rows, (row) => row.kind === kind && passes(brandLists, row.brand_id));
  const categoryLists = { include: filter.categories ?? [], exclude: filter.excludeCategories ?? [] };
  const brands = useMemo(() => {
    const byBrand = new Map<number, { id: number; name: string; changes: number }>();
    for (const row of rows) {
      if (kinds.length > 0 && !kinds.includes(row.kind)) continue;
      const entry = byBrand.get(row.brand_id) ?? { id: row.brand_id, name: row.brand_name, changes: 0 };
      entry.changes += row.changes;
      byBrand.set(row.brand_id, entry);
    }
    return [...byBrand.values()].sort((a, b) => b.changes - a.changes || a.name.localeCompare(b.name));
  }, [rows, kinds]);

  const list = useInfiniteQuery({
    queryKey: ['changes', day, brandLists, kinds, sort, filter],
    queryFn: ({ pageParam }) =>
      recentChanges({ ...filter, day, brandIds: brandLists.include, excludeBrandIds: brandLists.exclude, kinds, sort }, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.length === CHANGES_PAGE_SIZE ? pages.length : undefined),
  });
  const items = list.data?.pages.flat() ?? [];

  const toggleKind = (kind: ChangeKind) =>
    setKinds((current) => (current.includes(kind) ? current.filter((item) => item !== kind) : [...current, kind]));

  const header = (
    <View style={styles.header}>
      <ThemedText style={styles.heading} accessibilityRole="header">Changes</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        What changed in each daily check. Pick an earlier day to look back.
      </ThemedText>

      <ChipRow label="Day">
        {days.map((item) => (
          <Chip
            key={item.day}
            label={`${dayLabel(item.day)} · ${formatCount(item.changes)}`}
            selected={item.day === day}
            onPress={() => onPickDay(item.day)}
            accessibilityLabel={`${dayLabel(item.day)}, ${item.changes} changes`}
          />
        ))}
      </ChipRow>

      <ChipRow label="Sort">
        {SORTS.map((item) => (
          <Chip key={item.key} label={item.label} selected={sort === item.key} onPress={() => setSort(item.key)} />
        ))}
      </ChipRow>

      <ChipRow label="Kind of change">
        <Chip label="All" selected={kinds.length === 0} onPress={() => setKinds([])} accessibilityLabel="All kinds" />
        {KIND_ORDER.filter((kind) => kindCount(kind) > 0 || kinds.includes(kind)).map((kind) => (
          <Chip
            key={kind}
            label={`${KIND_LABELS[kind]} · ${formatCount(kindCount(kind))}`}
            selected={kinds.includes(kind)}
            onPress={() => toggleKind(kind)}
          />
        ))}
      </ChipRow>

      <ChipRow label="Stock now">
        {STOCK.map((item) => (
          <Chip
            key={item.label}
            label={item.label}
            selected={(filter.stock ?? null) === item.key}
            onPress={() => setFilter({ ...filter, stock: item.key })}
          />
        ))}
        {GENDERS.map((item) => (
          <Chip
            key={item.key}
            label={item.label}
            selected={filter.genders?.includes(item.key)}
            onPress={() => setFilter({ ...filter, genders: toggle(filter.genders, item.key) })}
          />
        ))}
      </ChipRow>

      <ChipRow label="Brand">
        <Chip
          label="All brands"
          selected={brandLists.include.length === 0 && brandLists.exclude.length === 0}
          onPress={() => setBrandLists({ include: [], exclude: [] })}
        />
        {brands.map((brand) => (
          <Chip
            key={brand.id}
            label={`${brand.name} · ${formatCount(brand.changes)}`}
            selected={stateOf(brandLists, brand.id) === 'include'}
            excluded={stateOf(brandLists, brand.id) === 'exclude'}
            onPress={() => setBrandLists(cycle(brandLists, brand.id))}
          />
        ))}
      </ChipRow>

      <ChipRow label="Category">
        <Chip
          label="All categories"
          selected={categoryLists.include.length === 0 && categoryLists.exclude.length === 0}
          onPress={() => setFilter({ ...filter, categories: [], excludeCategories: [] })}
        />
        {CATEGORIES.map((item) => (
          <Chip
            key={item.key}
            label={item.label}
            selected={stateOf(categoryLists, item.key) === 'include'}
            excluded={stateOf(categoryLists, item.key) === 'exclude'}
            onPress={() => {
              const next = cycle(categoryLists, item.key);
              setFilter({ ...filter, categories: next.include, excludeCategories: next.exclude });
            }}
          />
        ))}
      </ChipRow>
      <ThemedText style={styles.hint} themeColor="textSecondary">
        Tap a brand or category once to show only it, twice to hide it.
      </ThemedText>

      <View style={styles.price}>
        <PriceRow value={filter} onChange={setFilter} />
      </View>

      <ThemedText type="smallBold" themeColor="textSecondary" accessibilityLiveRegion="polite">
        {summary.isPending ? 'Counting…' : `${formatCount(total)} ${total === 1 ? 'change' : 'changes'} on ${dayLabel(day)}`}
      </ThemedText>
    </View>
  );

  return (
    <FlatList
      data={items}
      keyExtractor={(item) => String(item.event_id)}
      renderItem={({ item }) => <ChangeRow change={item} />}
      ListHeaderComponent={header}
      ListEmptyComponent={
        list.isPending ? <Loading />
        : list.isError ? <ErrorMessage error={list.error} onRetry={() => list.refetch()} />
        : <Message title="No changes match" detail="Clear a filter or pick another day." />
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
        summary.refetch();
        list.refetch();
      }}
      contentContainerStyle={styles.content}
    />
  );
}

const STOCK: { key: 'in' | 'out' | null; label: string }[] = [
  { key: null, label: 'Any stock' },
  { key: 'in', label: 'In stock now' },
  { key: 'out', label: 'Sold out now' },
];

const GENDERS = [
  { key: 'women', label: 'Women' },
  { key: 'men', label: 'Men' },
  { key: 'kids', label: 'Kids' },
];

const SORTS: { key: ChangeSort; label: string }[] = [
  { key: 'recent', label: 'Newest' },
  { key: 'biggest_drop', label: 'Biggest drop' },
  { key: 'price_asc', label: 'Price: low to high' },
  { key: 'price_desc', label: 'Price: high to low' },
];

function toggle(list: string[] | undefined, key: string): string[] {
  const current = list ?? [];
  return current.includes(key) ? current.filter((item) => item !== key) : [...current, key];
}

function sum(rows: ChangeSummaryRow[], keep: (row: ChangeSummaryRow) => boolean): number {
  return rows.reduce((total, row) => (keep(row) ? total + row.changes : total), 0);
}

function ChipRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.chipRow}
      style={styles.chipScroll}
      accessibilityLabel={label}>
      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: {
    paddingHorizontal: Spacing.three,
    paddingBottom: BottomTabInset + Spacing.five,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  header: { gap: Spacing.two, paddingTop: Spacing.three, paddingBottom: Spacing.two },
  heading: { fontSize: 26, lineHeight: 32, fontWeight: 700 },
  chipScroll: { marginHorizontal: -Spacing.three },
  chipRow: { gap: Spacing.two, paddingHorizontal: Spacing.three },
  price: { marginHorizontal: -Spacing.three },
  hint: { fontSize: 12, lineHeight: 16 },
  footer: { height: Spacing.six },
});
