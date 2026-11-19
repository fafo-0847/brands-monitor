import { useEffect, useState } from 'react';
import { StyleSheet, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ProductFilterPanel } from '@/components/product-filter-panel';
import { ProductGrid } from '@/components/product-grid';
import { FilterButton } from '@/components/side-panel';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, MinTouch, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { SearchParams } from '@/lib/api';
import { activeFilterCount } from '@/lib/filters';

export default function SearchScreen() {
  const theme = useTheme();
  const [text, setText] = useState('');
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<SearchParams>({});
  const [panelOpen, setPanelOpen] = useState(false);

  // Wait for a pause in typing before asking the server.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(text.trim()), 300);
    return () => clearTimeout(timer);
  }, [text]);

  // Best match while there are search words, newest activity otherwise, unless a sort was chosen.
  const params: SearchParams = {
    ...filters,
    query,
    sort: filters.sort && (filters.sort !== 'relevance' || query) ? filters.sort : query ? 'relevance' : 'recent_activity',
  };

  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView style={styles.screen} edges={['top']}>
        <View style={styles.bar}>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="Search articles, brands, types"
            placeholderTextColor={theme.textSecondary}
            accessibilityLabel="Search"
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="search"
            clearButtonMode="while-editing"
            style={[styles.input, { backgroundColor: theme.backgroundElement, color: theme.text }]}
          />
          <FilterButton count={activeFilterCount(filters)} onPress={() => setPanelOpen(true)} />
        </View>
        <View style={styles.list}>
          <ProductGrid
            params={params}
            emptyTitle="No articles match"
            emptyDetail="Words must match exactly. Try fewer words or clear a filter."
          />
        </View>
        <ProductFilterPanel
          visible={panelOpen}
          value={params}
          onClose={() => setPanelOpen(false)}
          onApply={(next) => {
            const { query: _ignored, ...rest } = next;
            setFilters(rest);
          }}
        />
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    padding: Spacing.three,
    paddingBottom: Spacing.two,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  input: { flex: 1, minHeight: MinTouch, borderRadius: Radius.medium, paddingHorizontal: Spacing.three, fontSize: 16 },
  list: { flex: 1, paddingBottom: BottomTabInset },
});
