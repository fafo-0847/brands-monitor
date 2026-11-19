import { useQuery } from '@tanstack/react-query';
import { Stack, useLocalSearchParams } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { FilterBar } from '@/components/filter-bar';
import { ProductGrid } from '@/components/product-grid';
import { ErrorMessage, Loading, Message } from '@/components/states';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MinTouch, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { brandBySlug, type Brand, type SearchParams } from '@/lib/api';
import { formatAgo, isStale } from '@/lib/format';

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

const styles = StyleSheet.create({
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
