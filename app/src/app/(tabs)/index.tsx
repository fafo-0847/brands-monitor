import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ProductFilterPanel } from '@/components/product-filter-panel';
import { ProductGrid } from '@/components/product-grid';
import { FilterButton } from '@/components/side-panel';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import type { SearchParams } from '@/lib/api';
import { activeFilterCount } from '@/lib/filters';

/** Every tracked article across brands, newest activity first, with filters and sort in a side panel. */
export default function HomeScreen() {
  const [filters, setFilters] = useState<SearchParams>({ sort: 'recent_activity' });
  const [panelOpen, setPanelOpen] = useState(false);

  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView style={styles.screen} edges={['top']}>
        <View style={styles.header}>
          <View style={styles.titles}>
            <ThemedText style={styles.heading}>StockWatch PK</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">Prices and stock across brands, checked twice a day.</ThemedText>
          </View>
          <FilterButton count={activeFilterCount(filters)} onPress={() => setPanelOpen(true)} />
        </View>
        <View style={styles.list}>
          <ProductGrid
            params={filters}
            emptyTitle="No articles match"
            emptyDetail="Open Filters and clear one, or pick another day."
          />
        </View>
        <ProductFilterPanel
          visible={panelOpen}
          value={filters}
          onClose={() => setPanelOpen(false)}
          onApply={setFilters}
        />
      </SafeAreaView>
    </ThemedView>
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
  titles: { flex: 1 },
  heading: { fontSize: 24, lineHeight: 30, fontWeight: 700 },
  list: { flex: 1, paddingBottom: BottomTabInset },
});
