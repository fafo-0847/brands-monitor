import { useQuery } from '@tanstack/react-query';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ErrorMessage, Loading, Message } from '@/components/states';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, MinTouch, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { listBrands } from '@/lib/api';
import { formatAgo, isStale } from '@/lib/format';

export default function ProfileScreen() {
  const theme = useTheme();
  const query = useQuery({ queryKey: ['brands'], queryFn: listBrands });

  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView style={styles.screen} edges={['top']}>
        <ScrollView contentContainerStyle={styles.content}>
          <ThemedText style={styles.heading} accessibilityRole="header">Profile</ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            Sign-in, alerts and settings are not built yet. The theme follows the light or dark setting of your phone.
          </ThemedText>

          <ThemedText style={styles.section} accessibilityRole="header">Tracked brands</ThemedText>
          {query.isPending ? <Loading />
            : query.isError ? <ErrorMessage error={query.error} onRetry={() => query.refetch()} />
            : query.data.length === 0 ? <Message title="No brands loaded yet" detail="Brands appear after the first data load." />
            : query.data.map((brand) => (
                <Pressable
                  key={brand.slug}
                  onPress={() => router.push({ pathname: '/brand/[slug]', params: { slug: brand.slug } })}
                  accessibilityRole="link"
                  style={({ pressed }) => [styles.row, { borderBottomColor: theme.border, opacity: pressed ? 0.6 : 1 }]}>
                  <View style={styles.rowText}>
                    <ThemedText type="smallBold" numberOfLines={1}>{brand.name}</ThemedText>
                    <ThemedText style={styles.meta} themeColor="textSecondary">
                      {brand.product_count.toLocaleString('en-US')} articles · checked {formatAgo(brand.last_success_at)}
                      {isStale(brand.last_success_at) ? ' · ⚠ out of date' : ''}
                    </ThemedText>
                  </View>
                  <ThemedText themeColor="textSecondary">›</ThemedText>
                </Pressable>
            ))}

          <ThemedText style={styles.note} themeColor="textSecondary">
            StockWatch PK reads public brand websites once a day. It is not affiliated with any listed brand, and
            prices or stock shown here can be out of date. Always confirm on the brand site itself.
          </ThemedText>
        </ScrollView>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: {
    padding: Spacing.three,
    paddingBottom: BottomTabInset + Spacing.five,
    gap: Spacing.two,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  heading: { fontSize: 26, lineHeight: 32, fontWeight: 700 },
  section: { fontSize: 18, lineHeight: 24, fontWeight: 700, marginTop: Spacing.four },
  row: {
    minHeight: MinTouch + 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingVertical: Spacing.two,
  },
  rowText: { flex: 1 },
  meta: { fontSize: 12, lineHeight: 17 },
  note: { fontSize: 12, lineHeight: 17, marginTop: Spacing.four },
});
