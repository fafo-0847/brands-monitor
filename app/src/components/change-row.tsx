import { Image } from 'expo-image';
import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { Change, ChangeKind } from '@/lib/api';
import { formatPrice, percentChange } from '@/lib/format';

export const KIND_LABELS: Record<ChangeKind, string> = {
  price_drop: 'Price drops',
  price_rise: 'Price rises',
  back_in_stock: 'Back in stock',
  out_of_stock: 'Sold out',
  new_product: 'New',
  sale_started: 'Sale started',
  sale_ended: 'Sale ended',
  removed: 'Removed',
};

export const KIND_ORDER: ChangeKind[] = [
  'price_drop', 'back_in_stock', 'new_product', 'sale_started', 'price_rise', 'out_of_stock', 'sale_ended', 'removed',
];

/** One line saying what changed, with a symbol so colour is never the only signal. */
function describe(change: Change): { text: string; tone: 'positive' | 'negative' | 'neutral' } {
  const pct = percentChange(change.old_price, change.new_price);
  const prices = `${formatPrice(change.old_price)} → ${formatPrice(change.new_price)}`;
  switch (change.kind) {
    case 'price_drop':
      return { text: `▼ ${Math.abs(pct ?? 0)}%  ${prices}`, tone: 'positive' };
    case 'price_rise':
      return { text: `▲ ${Math.abs(pct ?? 0)}%  ${prices}`, tone: 'negative' };
    case 'back_in_stock':
      return { text: `● Back in stock · ${formatPrice(change.new_price ?? change.price_min)}`, tone: 'positive' };
    case 'out_of_stock':
      return { text: '○ Sold out', tone: 'negative' };
    case 'new_product':
      return { text: `+ New article · ${formatPrice(change.price_min)}`, tone: 'neutral' };
    case 'sale_started':
      return { text: `% Sale started · ${change.new_discount ?? 0}% off`, tone: 'positive' };
    case 'sale_ended':
      return { text: `Sale ended · was ${change.old_discount ?? 0}% off`, tone: 'neutral' };
    case 'removed':
      return { text: '✕ Removed from the store', tone: 'neutral' };
  }
}

export function ChangeRow({ change }: { change: Change }) {
  const theme = useTheme();
  const { text, tone } = describe(change);
  const color = tone === 'positive' ? theme.positive : tone === 'negative' ? theme.negative : theme.textSecondary;

  return (
    <Pressable
      onPress={() => router.push({ pathname: '/product/[id]', params: { id: String(change.id) } })}
      accessibilityRole="link"
      accessibilityLabel={`${change.brand_name}, ${change.title}: ${text}`}
      style={({ pressed }) => [styles.row, { borderBottomColor: theme.border, opacity: pressed ? 0.6 : 1 }]}>
      <View style={[styles.thumb, { backgroundColor: theme.backgroundElement }]}>
        {change.image ? <Image source={{ uri: change.image }} style={styles.image} contentFit="cover" /> : null}
      </View>
      <View style={styles.text}>
        <ThemedText style={styles.brand} themeColor="textSecondary" numberOfLines={1}>{change.brand_name}</ThemedText>
        <ThemedText style={styles.title} numberOfLines={2}>{change.title}</ThemedText>
        <ThemedText style={[styles.change, { color }]} numberOfLines={1}>{text}</ThemedText>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: Spacing.three,
    paddingVertical: Spacing.three,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  thumb: { width: 64, height: 80, borderRadius: Radius.small, overflow: 'hidden' },
  image: { width: '100%', height: '100%' },
  text: { flex: 1, gap: Spacing.half, justifyContent: 'center' },
  brand: { fontSize: 11, lineHeight: 14, fontWeight: 600, textTransform: 'uppercase' },
  title: { fontSize: 14, lineHeight: 19, fontWeight: 500 },
  change: { fontSize: 13, lineHeight: 18, fontWeight: 700, fontVariant: ['tabular-nums'] },
});
