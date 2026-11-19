import { useQuery } from '@tanstack/react-query';
import { Stack, useLocalSearchParams } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { Chip } from '@/components/chip';
import { FilterBar } from '@/components/filter-bar';
import { ProductGrid } from '@/components/product-grid';
import { ErrorMessage, Loading, Message } from '@/components/states';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MinTouch, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { brandBySlug, brandTypes, type Brand, type SearchParams } from '@/lib/api';
import { formatAgo, formatCount, isStale } from '@/lib/format';

export default function BrandScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const [filters, setFilters] = useState<SearchParams>({ sort: 'discount' });
  const query = useQuery({ queryKey: ['brand', slug], queryFn: () => brandBySlug(slug) });
  const brand = query.data;

  return (
    <ThemedView style={styles.screen}>
      <Stack.Screen options={{ title: brand?.name ?? '' }} />
      {query.isPending ? <Loading />
        : query.isError ? <ErrorMessage error={query.error} onRetry={() => query.refetch()} />
        : !brand ? <Message title="Brand not found" detail="It may have been hidden or is not tracked yet." />
        : (
          <ProductGrid
            params={{ ...filters, brandIds: [brand.id] }}
            header={
              <View>
                <BrandHeader brand={brand} />
                <BrandTypes
                  brandId={brand.id}
                  selected={filters.types ?? []}
                  onChange={(types) => setFilters({ ...filters, types })}
                />
                <FilterBar value={filters} onChange={setFilters} showSizes={brand.granularity === 'variant'} />
              </View>
            }
            emptyTitle="No articles match"
            emptyDetail="Remove a filter to see more."
          />
        )}
    </ThemedView>
  );
}

function BrandHeader({ brand }: { brand: Brand }) {
  const theme = useTheme();
  const stale = isStale(brand.last_success_at);
  return (
    <View style={styles.header}>
      <ThemedText style={styles.name} accessibilityRole="header">{brand.name}</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        {brand.product_count.toLocaleString('en-US')} articles · last checked {formatAgo(brand.last_success_at)}
      </ThemedText>
      {stale ? (
        <View style={[styles.notice, { backgroundColor: theme.backgroundElement }]}>
          <ThemedText type="small">
            ⚠ Data may be out of date: the last successful check was more than two days ago.
          </ThemedText>
        </View>
      ) : null}
      {brand.granularity === 'product' ? (
        <ThemedText type="small" themeColor="textSecondary">Size availability is not tracked for this brand.</ThemedText>
      ) : null}
      <Pressable
        onPress={() => WebBrowser.openBrowserAsync(brand.origin_url)}
        accessibilityRole="link"
        style={({ pressed }) => [styles.store, { borderColor: theme.border, opacity: pressed ? 0.6 : 1 }]}>
        <ThemedText type="smallBold">Visit store ↗</ThemedText>
      </Pressable>
    </View>
  );
}

const FEW_TYPES = 12;

/** The brand's own categories, as the brand names them. Hidden when the brand has none worth showing. */
function BrandTypes({ brandId, selected, onChange }: {
  brandId: number;
  selected: string[];
  onChange: (types: string[]) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const query = useQuery({ queryKey: ['brand-types', brandId], queryFn: () => brandTypes(brandId) });
  const types = query.data ?? [];
  if (types.length < 2) return null;

  const visible = showAll ? types : types.filter((item, index) => index < FEW_TYPES || selected.includes(item.raw_type));
  const toggle = (value: string) =>
    onChange(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value]);

  return (
    <View style={styles.types}>
      <ThemedText type="smallBold" themeColor="textSecondary">Brand&apos;s categories</ThemedText>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.typeScroll}
        contentContainerStyle={styles.typeRow}
        accessibilityLabel="Brand's own categories">
        <Chip label="All" selected={selected.length === 0} onPress={() => onChange([])} accessibilityLabel="All of the brand's categories" />
        {visible.map((item) => (
          <Chip
            key={item.raw_type}
            label={`${item.raw_type} · ${formatCount(item.products)}`}
            selected={selected.includes(item.raw_type)}
            onPress={() => toggle(item.raw_type)}
            accessibilityLabel={`${item.raw_type}, ${item.products} articles`}
          />
        ))}
        {types.length > FEW_TYPES ? (
          <Chip
            label={showAll ? 'Fewer' : `More (${types.length - FEW_TYPES})`}
            onPress={() => setShowAll(!showAll)}
            accessibilityLabel={showAll ? 'Show fewer categories' : 'Show all categories'}
          />
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  types: { gap: Spacing.two, paddingBottom: Spacing.three },
  typeScroll: { marginHorizontal: -Spacing.three },
  typeRow: { gap: Spacing.two, paddingHorizontal: Spacing.three },
  screen: { flex: 1 },
  header: { gap: Spacing.two, paddingTop: Spacing.three, paddingBottom: Spacing.three },
  name: { fontSize: 26, lineHeight: 32, fontWeight: 700 },
  notice: { padding: Spacing.three, borderRadius: Radius.medium },
  store: {
    alignSelf: 'flex-start',
    minHeight: MinTouch,
    justifyContent: 'center',
    paddingHorizontal: Spacing.three,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: Radius.medium,
  },
});
