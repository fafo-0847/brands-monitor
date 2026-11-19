import { useMutation, useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query';
import { Image } from 'expo-image';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { FlatList, Pressable, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Chip } from '@/components/chip';
import { ErrorMessage, Loading, Message } from '@/components/states';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, MinTouch, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { listAlerts, listWatches, markAlertsRead, removeWatch, type Alert, type WatchedProduct } from '@/lib/api';
import { formatAgo, formatPrice, percentChange } from '@/lib/format';

type Segment = 'watching' | 'alerts';

export default function WatchlistScreen() {
  const [segment, setSegment] = useState<Segment>('watching');
  const queryClient = useQueryClient();
  const watches = useQuery({ queryKey: ['watches'], queryFn: listWatches });
  const alerts = useQuery({ queryKey: ['alerts'], queryFn: listAlerts });
  const unread = alerts.data?.filter((alert) => !alert.read_at).length ?? 0;

  // Coming back to the tab refreshes both lists (a watch may have been added on an article page).
  useFocusEffect(
    useCallback(() => {
      queryClient.invalidateQueries({ queryKey: ['watches'] });
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    }, [queryClient]),
  );

  const markRead = useMutation({
    mutationFn: markAlertsRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  });

  const open = (next: Segment) => {
    setSegment(next);
    if (next === 'alerts' && unread > 0) markRead.mutate();
  };

  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView style={styles.screen} edges={['top']}>
        <View style={styles.header}>
          <ThemedText style={styles.heading} accessibilityRole="header">Watchlist</ThemedText>
          <View style={styles.segments}>
            <Chip label={`Watching · ${watches.data?.length ?? 0}`} selected={segment === 'watching'} onPress={() => open('watching')} />
            <Chip label={unread > 0 ? `Alerts · ${unread} new` : 'Alerts'} selected={segment === 'alerts'} onPress={() => open('alerts')} />
          </View>
        </View>
        {segment === 'watching' ? <Watching query={watches} /> : <Alerts query={alerts} />}
      </SafeAreaView>
    </ThemedView>
  );
}

function Watching({ query }: { query: UseQueryResult<WatchedProduct[]> }) {
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: (productId: number) => removeWatch(productId),
    onSuccess: (_, productId) => {
      queryClient.invalidateQueries({ queryKey: ['watches'] });
      queryClient.invalidateQueries({ queryKey: ['watch', productId] });
    },
  });
  return (
    <FlatList
      data={query.data ?? []}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => <WatchRow watch={item} onRemove={() => remove.mutate(item.product.id)} />}
      contentContainerStyle={styles.content}
      refreshing={query.isRefetching}
      onRefresh={() => query.refetch()}
      ListEmptyComponent={
        query.isPending ? <Loading />
        : query.isError ? <ErrorMessage error={query.error} onRetry={() => query.refetch()} />
        : (
          <Message
            title="Nothing watched yet"
            detail="Open any article and tap ☆ Watch. You get a notification when its price, stock or sale changes."
          />
        )
      }
    />
  );
}

function WatchRow({ watch, onRemove }: { watch: WatchedProduct; onRemove: () => void }) {
  const theme = useTheme();
  const { product } = watch;
  const change = percentChange(watch.price_at_watch, product.price_min);
  const removed = product.removed_at !== null;
  const stock = removed ? '✕ No longer listed' : product.available ? '● In stock' : '○ Sold out';
  return (
    <Pressable
      onPress={() => router.push({ pathname: '/product/[id]', params: { id: String(product.id) } })}
      accessibilityRole="link"
      accessibilityLabel={`${product.brand.name}, ${product.title}, ${formatPrice(product.price_min)}, ${stock}`}
      style={({ pressed }) => [styles.row, { borderBottomColor: theme.border, opacity: pressed ? 0.6 : 1 }]}>
      <View style={[styles.thumb, { backgroundColor: theme.backgroundElement }]}>
        {product.images[0] ? <Image source={{ uri: product.images[0] }} style={styles.image} contentFit="cover" /> : null}
      </View>
      <View style={styles.text}>
        <ThemedText style={styles.brand} themeColor="textSecondary" numberOfLines={1}>{product.brand.name}</ThemedText>
        <ThemedText style={styles.title} numberOfLines={2}>{product.title}</ThemedText>
        <View style={styles.priceLine}>
          <ThemedText style={styles.price}>{formatPrice(product.price_min)}</ThemedText>
          {change ? (
            <ThemedText style={[styles.change, { color: change < 0 ? theme.positive : theme.negative }]}>
              {change < 0 ? '▼' : '▲'} {Math.abs(change)}% since watched
            </ThemedText>
          ) : null}
        </View>
        <ThemedText style={[styles.meta, { color: removed || !product.available ? theme.negative : theme.positive }]}>
          {stock}
          <ThemedText style={styles.meta} themeColor="textSecondary">{`  ·  watched ${formatAgo(watch.created_at)}`}</ThemedText>
        </ThemedText>
      </View>
      <Pressable
        onPress={onRemove}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel={`Stop watching ${product.title}`}
        style={({ pressed }) => [styles.remove, { borderColor: theme.border, opacity: pressed ? 0.5 : 1 }]}>
        <ThemedText type="smallBold" themeColor="textSecondary">Remove</ThemedText>
      </Pressable>
    </Pressable>
  );
}

function Alerts({ query }: { query: UseQueryResult<Alert[]> }) {
  const theme = useTheme();
  return (
    <FlatList
      data={query.data ?? []}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => (
        <Pressable
          onPress={() => {
            const link = item.deep_link;
            if (link && /^\/product\/\d+$/.test(link)) {
              router.push({ pathname: '/product/[id]', params: { id: link.split('/')[2] } });
            }
          }}
          accessibilityRole="link"
          style={({ pressed }) => [styles.alert, { borderBottomColor: theme.border, opacity: pressed ? 0.6 : 1 }]}>
          <View style={styles.text}>
            <ThemedText style={styles.title} numberOfLines={2}>
              {item.read_at ? '' : '● '}
              {item.title}
            </ThemedText>
            {item.body ? <ThemedText style={styles.alertBody}>{item.body}</ThemedText> : null}
            <ThemedText style={styles.meta} themeColor="textSecondary">{formatAgo(item.created_at)}</ThemedText>
          </View>
        </Pressable>
      )}
      contentContainerStyle={styles.content}
      refreshing={query.isRefetching}
      onRefresh={() => query.refetch()}
      ListEmptyComponent={
        query.isPending ? <Loading />
        : query.isError ? <ErrorMessage error={query.error} onRetry={() => query.refetch()} />
        : <Message title="No alerts yet" detail="Changes to watched articles appear here after each price and stock check." />
      }
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  header: {
    paddingHorizontal: Spacing.three,
    paddingTop: Spacing.three,
    gap: Spacing.two,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  heading: { fontSize: 26, lineHeight: 32, fontWeight: 700 },
  segments: { flexDirection: 'row', gap: Spacing.two, paddingBottom: Spacing.two },
  content: {
    paddingHorizontal: Spacing.three,
    paddingBottom: BottomTabInset + Spacing.five,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three, paddingVertical: Spacing.three, borderBottomWidth: StyleSheet.hairlineWidth },
  thumb: { width: 64, height: 80, borderRadius: Radius.small, overflow: 'hidden' },
  image: { width: '100%', height: '100%' },
  text: { flex: 1, gap: Spacing.half },
  brand: { fontSize: 11, lineHeight: 14, fontWeight: 600, textTransform: 'uppercase' },
  title: { fontSize: 14, lineHeight: 19, fontWeight: 500 },
  priceLine: { flexDirection: 'row', alignItems: 'baseline', flexWrap: 'wrap', gap: Spacing.two },
  price: { fontSize: 14, lineHeight: 19, fontWeight: 700, fontVariant: ['tabular-nums'] },
  change: { fontSize: 12, lineHeight: 16, fontWeight: 700, fontVariant: ['tabular-nums'] },
  meta: { fontSize: 12, lineHeight: 16 },
  remove: {
    minHeight: MinTouch - 8,
    justifyContent: 'center',
    paddingHorizontal: Spacing.two,
    borderRadius: Radius.small,
    borderWidth: StyleSheet.hairlineWidth,
  },
  alert: { paddingVertical: Spacing.three, borderBottomWidth: StyleSheet.hairlineWidth },
  alertBody: { fontSize: 13, lineHeight: 18, fontWeight: 600, fontVariant: ['tabular-nums'] },
});
