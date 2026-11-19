import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Image } from 'expo-image';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { Alert, Pressable, ScrollView, Share, StyleSheet, useWindowDimensions, View } from 'react-native';

import { Chip } from '@/components/chip';
import { PriceChart } from '@/components/price-chart';
import { ErrorMessage, Loading, Message } from '@/components/states';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, MinTouch, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { addWatch, isWatching, priceSeries, productDetail, removeWatch, type ProductDetail, type Variant } from '@/lib/api';
import { AnonymousSignInDisabledError } from '@/lib/session';
import { formatAgo, formatDate, formatPrice } from '@/lib/format';

export default function ProductScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = Number(params.id);
  const query = useQuery({ queryKey: ['product', id], queryFn: () => productDetail(id), enabled: Number.isFinite(id) });

  return (
    <ThemedView style={styles.screen}>
      <Stack.Screen options={{ title: query.data?.brand.name ?? '' }} />
      {!Number.isFinite(id) ? <Message title="Article not found" />
        : query.isPending ? <Loading />
        : query.isError ? <ErrorMessage error={query.error} onRetry={() => query.refetch()} />
        : !query.data ? <Message title="Article not found" detail="It may no longer be tracked." />
        : <Article product={query.data} />}
    </ThemedView>
  );
}

function Article({ product }: { product: ProductDetail }) {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const [variantId, setVariantId] = useState<number | null>(null);
  const [expanded, setExpanded] = useState(false);

  const variant = product.variants.find((item) => item.id === variantId) ?? null;
  const sizes = product.brand.tracks_sizes && product.variants.length > 1 ? product.variants : [];
  const price = variant ? variant.price : product.price_min;
  const compareAt = variant ? variant.compare_at_price : product.compare_at_max;
  const onSale = compareAt !== null && price !== null && compareAt > price;
  const available = variant ? variant.available : product.available;
  const removed = product.removed_at !== null;

  const series = useQuery({
    queryKey: ['series', product.id, variantId],
    queryFn: () => priceSeries(product.id, variantId),
  });

  const imageWidth = Math.min(width, 520);

  return (
    <ScrollView contentContainerStyle={styles.content}>
      {product.images.length > 0 ? (
        <ScrollView
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          style={{ width: imageWidth, alignSelf: 'center' }}
          accessibilityLabel={`${product.images.length} photos`}>
          {product.images.map((uri) => (
            <Image
              key={uri}
              source={{ uri }}
              style={{ width: imageWidth, height: imageWidth * 1.25, backgroundColor: theme.backgroundElement }}
              contentFit="cover"
              transition={150}
              accessibilityIgnoresInvertColors
            />
          ))}
        </ScrollView>
      ) : null}

      <View style={styles.body}>
          <Pressable
            onPress={() => router.push({ pathname: '/brand/[slug]', params: { slug: product.brand.slug } })}
            accessibilityRole="link"
            hitSlop={8}
            style={styles.brandLink}>
            <ThemedText style={[styles.brand, { color: theme.accent }]}>{product.brand.name}</ThemedText>
          </Pressable>
        <ThemedText style={styles.title} accessibilityRole="header">{product.title}</ThemedText>

        <View style={styles.priceRow}>
          <ThemedText style={styles.price}>{formatPrice(price)}</ThemedText>
          {onSale ? <ThemedText style={styles.was} themeColor="textSecondary">{formatPrice(compareAt)}</ThemedText> : null}
          {onSale && compareAt ? (
            <ThemedText style={[styles.off, { color: theme.positive }]}>
              ▼ {Math.round(((compareAt - (price ?? 0)) / compareAt) * 100)}% off
            </ThemedText>
          ) : null}
        </View>
        <ThemedText type="small" style={{ color: removed || !available ? theme.negative : theme.positive }}>
          {removed ? `✕ No longer listed (since ${formatDate(product.removed_at!)})` : available ? '● In stock' : '○ Out of stock'}
        </ThemedText>

        {sizes.length > 0 ? (
          <View style={styles.block}>
            <ThemedText type="smallBold">Size</ThemedText>
            <View style={styles.chips}>
              <Chip label="All" selected={variantId === null} onPress={() => setVariantId(null)} accessibilityLabel="All sizes" />
              {sizes.map((item) => (
                <Chip
                  key={item.id}
                  label={`${sizeLabel(item)}${item.available ? '' : ' · out'}`}
                  selected={item.id === variantId}
                  onPress={() => setVariantId(item.id === variantId ? null : item.id)}
                  accessibilityLabel={`${sizeLabel(item)}, ${item.available ? 'in stock' : 'out of stock'}, ${formatPrice(item.price)}`}
                />
              ))}
            </View>
          </View>
        ) : null}
        {!product.brand.tracks_sizes ? (
          <ThemedText type="small" themeColor="textSecondary">Size availability is not tracked for this brand.</ThemedText>
        ) : null}

        <View style={styles.actions}>
          <Pressable
            onPress={() => WebBrowser.openBrowserAsync(product.url)}
            accessibilityRole="link"
            style={({ pressed }) => [styles.buy, { backgroundColor: theme.accent, opacity: pressed ? 0.8 : 1 }]}>
            <ThemedText style={[styles.buyText, { color: theme.onAccent }]}>Buy on {product.brand.name} ↗</ThemedText>
          </Pressable>
        </View>
        <View style={styles.secondary}>
          <WatchButton productId={product.id} />
          <Pressable
            onPress={() => Share.share({ message: `${product.title} — ${formatPrice(price)}\n${product.url}` })}
            accessibilityRole="button"
            style={({ pressed }) => [styles.share, { borderColor: theme.border, opacity: pressed ? 0.6 : 1 }]}>
            <ThemedText type="smallBold">Share</ThemedText>
          </Pressable>
        </View>

        <View style={styles.block}>
          <ThemedText style={styles.sectionTitle} accessibilityRole="header">
            Price history{variant ? ` · ${sizeLabel(variant)}` : ''}
          </ThemedText>
          {series.isPending ? <Loading />
            : series.isError ? <ErrorMessage error={series.error} onRetry={() => series.refetch()} />
            : <PriceChart series={series.data} />}
        </View>

        <View style={[styles.stats, { borderColor: theme.border }]}>
          <Stat label="Lowest" value={formatPrice(product.stats.lowest_price)} />
          <Stat label="Highest" value={formatPrice(product.stats.highest_price)} />
          <Stat label="Price changes" value={String(product.stats.price_changes)} />
          <Stat label="Tracked since" value={formatDate(product.stats.tracking_since)} />
          <Stat label="Last price change" value={product.last_price_change_at ? formatAgo(product.last_price_change_at) : 'none yet'} />
          <Stat label="Last restock" value={product.last_restock_at ? formatAgo(product.last_restock_at) : 'none yet'} />
        </View>

        {product.description ? (
          <View style={styles.block}>
            <ThemedText style={styles.sectionTitle} accessibilityRole="header">Details</ThemedText>
            <ThemedText type="small" themeColor="textSecondary" numberOfLines={expanded ? undefined : 4}>
              {product.description}
            </ThemedText>
            {product.description.length > 180 ? (
              <Pressable onPress={() => setExpanded(!expanded)} accessibilityRole="button" hitSlop={10}>
                <ThemedText type="smallBold" style={{ color: theme.accent }}>{expanded ? 'Show less' : 'Show more'}</ThemedText>
              </Pressable>
            ) : null}
          </View>
        ) : null}

        <ThemedText style={styles.disclaimer} themeColor="textSecondary">
          Prices and stock are read from the brand&apos;s public site once a day and can be out of date. This app is not
          affiliated with {product.brand.name}.
        </ThemedText>
      </View>
    </ScrollView>
  );
}

/** Add to or remove from the watchlist. Any change to a watched article sends an alert. */
function WatchButton({ productId }: { productId: number }) {
  const theme = useTheme();
  const queryClient = useQueryClient();
  const watching = useQuery({ queryKey: ['watch', productId], queryFn: () => isWatching(productId) });
  const toggle = useMutation({
    mutationFn: (watch: boolean) => (watch ? addWatch(productId) : removeWatch(productId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watch', productId] });
      queryClient.invalidateQueries({ queryKey: ['watches'] });
    },
    onError: (error) => {
      Alert.alert(
        'Could not update the watchlist',
        error instanceof AnonymousSignInDisabledError
          ? 'Anonymous sign-ins are switched off in Supabase (Authentication → Sign In / Providers).'
          : error instanceof Error ? error.message : 'Please try again.',
      );
    },
  });
  const on = Boolean(watching.data);
  return (
    <Pressable
      onPress={() => toggle.mutate(!on)}
      disabled={watching.isPending || toggle.isPending}
      accessibilityRole="button"
      accessibilityState={{ selected: on, busy: toggle.isPending }}
      accessibilityLabel={on ? 'Watching. Tap to stop watching' : 'Watch this article for changes'}
      style={({ pressed }) => [
        styles.share,
        { borderColor: on ? theme.accent : theme.border, opacity: pressed || toggle.isPending ? 0.6 : 1 },
      ]}>
      <ThemedText type="smallBold" style={on ? { color: theme.accent } : undefined}>{on ? '★ Watching' : '☆ Watch'}</ThemedText>
    </Pressable>
  );
}

function sizeLabel(variant: Variant): string {
  return variant.size ?? variant.title ?? 'Option';
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <ThemedText style={styles.statLabel} themeColor="textSecondary">{label}</ThemedText>
      <ThemedText style={styles.statValue}>{value}</ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { paddingBottom: Spacing.six },
  body: { padding: Spacing.three, gap: Spacing.two, width: '100%', maxWidth: MaxContentWidth, alignSelf: 'center' },
  brandLink: { alignSelf: 'flex-start' },
  brand: { fontSize: 13, lineHeight: 18, fontWeight: 700, textTransform: 'uppercase' },
  title: { fontSize: 20, lineHeight: 26, fontWeight: 700 },
  priceRow: { flexDirection: 'row', alignItems: 'baseline', flexWrap: 'wrap', gap: Spacing.two, marginTop: Spacing.one },
  price: { fontSize: 24, lineHeight: 30, fontWeight: 700, fontVariant: ['tabular-nums'] },
  was: { fontSize: 15, lineHeight: 20, textDecorationLine: 'line-through', fontVariant: ['tabular-nums'] },
  off: { fontSize: 14, lineHeight: 20, fontWeight: 700 },
  block: { gap: Spacing.two, marginTop: Spacing.three },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  actions: { flexDirection: 'row', marginTop: Spacing.three },
  secondary: { flexDirection: 'row', gap: Spacing.two },
  buy: { flex: 1, minHeight: MinTouch + 4, alignItems: 'center', justifyContent: 'center', borderRadius: Radius.medium, paddingHorizontal: Spacing.three },
  buyText: { fontSize: 15, lineHeight: 20, fontWeight: 700 },
  share: {
    flex: 1,
    alignItems: 'center',
    minHeight: MinTouch + 4,
    justifyContent: 'center',
    paddingHorizontal: Spacing.four,
    borderRadius: Radius.medium,
    borderWidth: StyleSheet.hairlineWidth,
  },
  sectionTitle: { fontSize: 17, lineHeight: 22, fontWeight: 700 },
  stats: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: Spacing.three,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingVertical: Spacing.two,
  },
  stat: { width: '50%', paddingVertical: Spacing.two },
  statLabel: { fontSize: 12, lineHeight: 16 },
  statValue: { fontSize: 15, lineHeight: 20, fontWeight: 600, fontVariant: ['tabular-nums'] },
  disclaimer: { fontSize: 12, lineHeight: 17, marginTop: Spacing.four },
});
