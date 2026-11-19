import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import type { ReactElement } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, useWindowDimensions, View } from 'react-native';

import { ProductCard } from '@/components/product-card';
import { ErrorMessage, Loading, Message } from '@/components/states';
import { ThemedText } from '@/components/themed-text';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { COUNT_CAP, PAGE_SIZE, searchCount, searchProducts, type SearchParams } from '@/lib/api';
import { formatCount } from '@/lib/format';

type Props = {
  params: SearchParams;
  header?: ReactElement;
  emptyTitle?: string;
  emptyDetail?: string;
};

/** Paged, pull-to-refresh product grid driven by search_products. Two columns on phones, more on tablets. */
export function ProductGrid({ params, header, emptyTitle = 'Nothing found', emptyDetail }: Props) {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const columns = width >= 900 ? 4 : width >= 600 ? 3 : 2;
  // Fixed cell width so a short last row keeps the same card size as full rows.
  const cellWidth = (Math.min(width, MaxContentWidth) - Spacing.three * 2 - Spacing.three * (columns - 1)) / columns;
  const query = useInfiniteQuery({
    queryKey: ['search', params],
    queryFn: ({ pageParam }) => searchProducts(params, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.length === PAGE_SIZE ? pages.length : undefined),
  });
  const items = query.data?.pages.flat() ?? [];

  return (
    <FlatList
      key={columns}
      data={items}
      numColumns={columns}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => <ProductCard product={item} style={{ width: cellWidth }} />}
      columnWrapperStyle={styles.row}
      contentContainerStyle={styles.content}
      ListHeaderComponent={
        <View>
          {header}
          <ResultCount params={params} />
        </View>
      }
      ListEmptyComponent={
        query.isPending ? <Loading />
        : query.isError ? <ErrorMessage error={query.error} onRetry={() => query.refetch()} />
        : <Message title={emptyTitle} detail={emptyDetail} />
      }
      ListFooterComponent={
        query.isFetchingNextPage ? <ActivityIndicator style={styles.footer} color={theme.textSecondary} /> : <View style={styles.footer} />
      }
      onEndReached={() => {
        if (query.hasNextPage && !query.isFetchingNextPage) query.fetchNextPage();
      }}
      onEndReachedThreshold={0.6}
      refreshing={query.isRefetching && !query.isFetchingNextPage}
      onRefresh={() => query.refetch()}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
    />
  );
}

/** "1,234 products" for the current filters; shown above the grid. */
function ResultCount({ params }: { params: SearchParams }) {
  const query = useQuery({ queryKey: ['count', params], queryFn: () => searchCount(params) });
  const text = query.isPending ? 'Counting…'
    : query.isError ? ''
    : `${formatCount(query.data, COUNT_CAP)} ${query.data === 1 ? 'product' : 'products'}`;
  return (
    <ThemedText type="smallBold" themeColor="textSecondary" style={styles.count} accessibilityLiveRegion="polite">
      {text}
    </ThemedText>
  );
}

const styles = StyleSheet.create({
  count: { minHeight: 20, marginBottom: Spacing.three },
  content: {
    paddingHorizontal: Spacing.three,
    paddingBottom: Spacing.six,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  row: { gap: Spacing.three, marginBottom: Spacing.four },
  footer: { height: Spacing.six },
});
