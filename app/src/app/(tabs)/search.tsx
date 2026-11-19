import { useEffect, useState } from 'react';
import { StyleSheet, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { FilterBar } from '@/components/filter-bar';
import { ProductGrid } from '@/components/product-grid';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, MinTouch, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { SearchParams } from '@/lib/api';

export default function SearchScreen() {
  const theme = useTheme();
  const [text, setText] = useState('');
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<SearchParams>({});

  // Wait for a pause in typing before asking the server.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(text.trim()), 300);
    return () => clearTimeout(timer);
  }, [text]);

  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView style={styles.screen} edges={['top']}>
        <View style={styles.inputWrap}>
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
        </View>
        <View style={styles.list}>
          <ProductGrid
            params={{ ...filters, query }}
            header={<FilterBar value={filters} onChange={setFilters} />}
            emptyTitle="No articles match"
            emptyDetail="Try fewer words or remove a filter."
          />
        </View>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  inputWrap: {
    padding: Spacing.three,
    paddingBottom: Spacing.two,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  input: { minHeight: MinTouch, borderRadius: Radius.medium, paddingHorizontal: Spacing.three, fontSize: 16 },
  list: { flex: 1, paddingBottom: BottomTabInset },
});
