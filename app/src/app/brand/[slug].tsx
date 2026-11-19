import { useQuery } from '@tanstack/react-query';
import { Stack, useLocalSearchParams } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { ProductFilterPanel } from '@/components/product-filter-panel';
import { ProductGrid } from '@/components/product-grid';
import { FilterButton } from '@/components/side-panel';
import { ErrorMessage, Loading, Message } from '@/components/states';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MinTouch, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { brandBySlug, type Brand, type SearchParams } from '@/lib/api';
import { activeFilterCount } from '@/lib/filters';
import { formatAgo, isStale } from '@/lib/format';

export default function BrandScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const [filters, setFilters] = useState<SearchParams>({ sort: 'recent_activity' });
  const [panelOpen, setPanelOpen] = useState(false);
  const query = useQuery({ queryKey: ['brand', slug], queryFn: () => brandBySlug(slug) });
  const brand = query.data;

  return (
    <ThemedView style={styles.screen}>
      <Stack.Screen options={{ title: brand?.name ?? '' }} />
      {query.isPending ? <Loading />
        : query.isError ? <ErrorMessage error={query.error} onRetry={() => query.refetch()} />
        : !brand ? <Message title="Brand not found" detail="It may have been hidden or is not tracked yet." />
        : (
          <>
            <ProductGrid
              params={{ ...filters, brandIds: [brand.id], excludeBrandIds: [] }}
              header={
                <BrandHeader
                  brand={brand}
                  action={<FilterButton count={activeFilterCount({ ...filters, brandIds: [] })} onPress={() => setPanelOpen(true)} />}
                />
              }
              emptyTitle="No articles match"
              emptyDetail="Open Filters and clear one to see more."
            />
            <ProductFilterPanel
              visible={panelOpen}
              value={{ ...filters, brandIds: [brand.id] }}
              brandId={brand.id}
              showSizes={brand.granularity === 'variant'}
              onClose={() => setPanelOpen(false)}
              onApply={setFilters}
            />
          </>
        )}
    </ThemedView>
  );
}

function BrandHeader({ brand, action }: { brand: Brand; action: React.ReactNode }) {
  const theme = useTheme();
  const stale = isStale(brand.last_success_at);
  return (
    <View style={styles.header}>
      <View style={styles.titleRow}>
        <ThemedText style={styles.name} accessibilityRole="header">{brand.name}</ThemedText>
        {action}
      </View>
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
  titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: Spacing.three },
  screen: { flex: 1 },
  header: { gap: Spacing.two, paddingTop: Spacing.three, paddingBottom: Spacing.three },
  name: { flex: 1, fontSize: 26, lineHeight: 32, fontWeight: 700 },
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
