import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'expo-router';
import { useState } from 'react';
import { FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ProductCard } from '@/components/product-card';
import { ErrorMessage, Loading, Message } from '@/components/states';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, MinTouch, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { homeFeed, listBrands, type FeedKind } from '@/lib/api';

const SECTIONS: { kind: FeedKind; title: string; empty: string }[] = [
  { kind: 'price_drops', title: 'Biggest price drops', empty: 'No price drops in the latest scans.' },
  { kind: 'back_in_stock', title: 'Back in stock', empty: 'Nothing has come back in stock yet.' },
  { kind: 'new_arrivals', title: 'New arrivals', empty: 'No new articles since tracking began.' },
];

export default function HomeScreen() {
  const theme = useTheme();
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);

  const refresh = async () => {
    setRefreshing(true);
    await Promise.all([
      queryClient.refetchQueries({ queryKey: ['feed'] }),
      queryClient.refetchQueries({ queryKey: ['brands'] }),
    ]);
    setRefreshing(false);
  };

  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView style={styles.screen} edges={['top']}>
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.textSecondary} />}>
          <ThemedText style={styles.heading}>StockWatch PK</ThemedText>
          <ThemedText type="small" themeColor="textSecondary" style={styles.sub}>
            Prices and stock across Pakistani fashion brands, checked daily.
          </ThemedText>
          <BrandRow />
          {SECTIONS.map((section) => (
            <FeedSection key={section.kind} {...section} />
          ))}
        </ScrollView>
      </SafeAreaView>
    </ThemedView>
  );
}

function FeedSection({ kind, title, empty }: { kind: FeedKind; title: string; empty: string }) {
  const query = useQuery({ queryKey: ['feed', kind], queryFn: () => homeFeed(kind) });
  return (
    <View style={styles.section}>
      <ThemedText style={styles.sectionTitle} accessibilityRole="header">{title}</ThemedText>
      {query.isPending ? <Loading />
        : query.isError ? <ErrorMessage error={query.error} onRetry={() => query.refetch()} />
        : query.data.length === 0 ? <Message title={empty} />
        : (
          <FlatList
            horizontal
            data={query.data}
            keyExtractor={(item, index) => `${item.id}-${index}`}
            renderItem={({ item }) => (
              <ProductCard product={item} previousPrice={kind === 'price_drops' ? item.old_price : undefined} style={styles.card} />
            )}
            contentContainerStyle={styles.row}
            showsHorizontalScrollIndicator={false}
          />
        )}
    </View>
  );
}

function BrandRow() {
  const theme = useTheme();
  const query = useQuery({ queryKey: ['brands'], queryFn: listBrands });
  if (query.isPending || query.isError || query.data.length === 0) return null;
  return (
    <View style={styles.section}>
      <ThemedText style={styles.sectionTitle} accessibilityRole="header">Brands</ThemedText>
      <FlatList
        horizontal
        data={query.data}
        keyExtractor={(item) => item.slug}
        renderItem={({ item }) => (
          <Link href={{ pathname: '/brand/[slug]', params: { slug: item.slug } }} asChild>
            <Pressable
              accessibilityRole="link"
              style={({ pressed }) => [styles.brand, { backgroundColor: theme.backgroundElement, opacity: pressed ? 0.7 : 1 }]}>
              <ThemedText type="smallBold" numberOfLines={1}>{item.name}</ThemedText>
            </Pressable>
          </Link>
        )}
        contentContainerStyle={styles.row}
        showsHorizontalScrollIndicator={false}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: {
    paddingTop: Spacing.three,
    paddingBottom: BottomTabInset + Spacing.five,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  heading: { fontSize: 26, lineHeight: 32, fontWeight: 700, paddingHorizontal: Spacing.three },
  sub: { paddingHorizontal: Spacing.three, marginTop: Spacing.one },
  section: { marginTop: Spacing.four, gap: Spacing.two },
  sectionTitle: { fontSize: 18, lineHeight: 24, fontWeight: 700, paddingHorizontal: Spacing.three },
  row: { paddingHorizontal: Spacing.three, gap: Spacing.three },
  card: { width: 148 },
  brand: {
    minHeight: MinTouch,
    justifyContent: 'center',
    paddingHorizontal: Spacing.three,
    borderRadius: Radius.medium,
    maxWidth: 200,
  },
});
