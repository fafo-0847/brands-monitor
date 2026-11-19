import { Image } from 'expo-image';
import { router } from 'expo-router';
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { ProductCard as Product } from '@/lib/api';
import { formatPrice } from '@/lib/format';

type Props = {
  product: Product;
  /** Shown instead of the sale price pair, for feeds: the price before the event. */
  previousPrice?: number | null;
  style?: StyleProp<ViewStyle>;
};

export function ProductCard({ product, previousPrice, style }: Props) {
  const theme = useTheme();
  const was = previousPrice ?? (product.discount_pct > 0 ? product.compare_at_max : null);
  const dropped = was !== null && product.price_min !== null && product.price_min < was;
  const rose = was !== null && product.price_min !== null && product.price_min > was;
  const percent = was && product.price_min !== null ? Math.round(((product.price_min - was) / was) * 100) : null;

  return (
    <View style={[styles.card, style]}>
      <Pressable
        onPress={() => router.push({ pathname: '/product/[id]', params: { id: String(product.id) } })}
        accessibilityRole="link"
        accessibilityLabel={`${product.brand_name}, ${product.title}, ${formatPrice(product.price_min)}${product.available ? '' : ', out of stock'}`}
        style={({ pressed }) => [styles.inner, { opacity: pressed ? 0.7 : 1 }]}>
        <View style={[styles.imageBox, { backgroundColor: theme.backgroundElement }]}>
          {product.image ? (
            <Image source={{ uri: product.image }} style={styles.image} contentFit="cover" transition={150} />
          ) : null}
          {!product.available ? (
            <View style={[styles.badge, { backgroundColor: theme.background }]}>
              <ThemedText style={styles.badgeText} themeColor="textSecondary">Out of stock</ThemedText>
            </View>
          ) : null}
        </View>
        <ThemedText style={styles.brand} themeColor="textSecondary" numberOfLines={1}>{product.brand_name}</ThemedText>
        <ThemedText style={styles.title} numberOfLines={2}>{product.title}</ThemedText>
        <View style={styles.priceRow}>
          <ThemedText style={styles.price}>{formatPrice(product.price_min)}</ThemedText>
          {percent !== null && (dropped || rose) ? (
            <ThemedText style={[styles.change, { color: dropped ? theme.positive : theme.negative }]}>
              {dropped ? '▼' : '▲'} {Math.abs(percent)}%
            </ThemedText>
          ) : null}
        </View>
        {was !== null && (dropped || rose) ? (
          <ThemedText style={styles.was} themeColor="textSecondary">{formatPrice(was)}</ThemedText>
        ) : null}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { overflow: 'hidden' },
  inner: { gap: Spacing.half },
  imageBox: { width: '100%', aspectRatio: 3 / 4, borderRadius: Radius.medium, overflow: 'hidden' },
  image: { width: '100%', height: '100%' },
  badge: {
    position: 'absolute',
    left: Spacing.two,
    bottom: Spacing.two,
    paddingHorizontal: Spacing.two,
    paddingVertical: Spacing.half,
    borderRadius: Radius.small,
  },
  badgeText: { fontSize: 11, lineHeight: 14, fontWeight: 600 },
  brand: { fontSize: 11, lineHeight: 14, fontWeight: 600, marginTop: Spacing.one, textTransform: 'uppercase' },
  title: { fontSize: 13, lineHeight: 17, fontWeight: 500 },
  priceRow: { flexDirection: 'row', alignItems: 'baseline', gap: Spacing.two, flexWrap: 'wrap' },
  price: { fontSize: 14, lineHeight: 18, fontWeight: 700, fontVariant: ['tabular-nums'] },
  change: { fontSize: 12, lineHeight: 16, fontWeight: 700, fontVariant: ['tabular-nums'] },
  was: { fontSize: 12, lineHeight: 15, textDecorationLine: 'line-through', fontVariant: ['tabular-nums'] },
});
