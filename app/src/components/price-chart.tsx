import { useMemo, useState } from 'react';
import { StyleSheet, View, type GestureResponderEvent } from 'react-native';
import Svg, { Circle, Line, Path, Rect } from 'react-native-svg';

import { Chip } from '@/components/chip';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { SeriesPoint } from '@/lib/api';
import { formatDate, formatPrice, formatPriceShort } from '@/lib/format';
import { clip, extremes, isFlat, outOfStockBands, pointAt, RANGES, scale, stepPath, toPoints, type RangeKey } from '@/lib/series';

const HEIGHT = 200;
const AXIS = 44;

type Props = { series: SeriesPoint[]; now?: number };

/**
 * Step line of price over time. Prices change in steps, so nothing is smoothed.
 * Out-of-stock periods are shaded; the compare-at ("was") price is a dashed line.
 * Press and drag to read a date.
 */
export function PriceChart({ series, now }: Props) {
  const theme = useTheme();
  const [range, setRange] = useState<RangeKey>('All');
  const [width, setWidth] = useState(0);
  const [cursor, setCursor] = useState<number | null>(null);

  const all = useMemo(() => toPoints(series), [series]);
  const [openedAt] = useState(() => Date.now());
  const clock = now ?? openedAt;
  const view = useMemo(() => clip(all, range, clock), [all, range, clock]);
  const plotWidth = Math.max(width - AXIS, 0);
  const s = useMemo(() => scale(view.points, view.start, view.end, plotWidth, HEIGHT), [view, plotWidth]);

  if (all.length === 0) return null;

  const first = all[0];
  if (isFlat(all)) {
    return (
      <View style={[styles.flat, { borderColor: theme.border }]}>
        <ThemedText type="smallBold">Tracking since {formatDate(first.t)}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
          No price or stock change recorded yet. The chart appears after the first change.
        </ThemedText>
      </View>
    );
  }

  const found = extremes(view.points);
  const bands = outOfStockBands(view.points, view.end);
  const active = cursor === null ? null : pointAt(view.points, s.timeAt(cursor));
  const hasCompare = view.points.some((point) => point.compareAt !== null && point.compareAt > point.price);

  const track = (event: GestureResponderEvent) => setCursor(Math.min(Math.max(event.nativeEvent.locationX, 0), plotWidth));

  return (
    <View style={styles.wrap}>
      <View style={styles.readout} accessibilityLiveRegion="polite">
        {active && cursor !== null ? (
          <>
            <ThemedText style={styles.readoutPrice}>{formatPrice(active.price)}</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              {formatDate(s.timeAt(cursor))} · {active.available ? 'In stock' : 'Out of stock'}
            </ThemedText>
          </>
        ) : (
          <ThemedText type="small" themeColor="textSecondary">
            {found ? `Low ${formatPrice(found.low.price)} · High ${formatPrice(found.high.price)}` : ''}
            {'  ·  '}Press and drag to inspect
          </ThemedText>
        )}
      </View>

      <View
        style={styles.plot}
        onLayout={(event) => setWidth(event.nativeEvent.layout.width)}
        accessible
        accessibilityRole="image"
        accessibilityLabel={
          found
            ? `Price history from ${formatDate(view.start)} to ${formatDate(view.end)}. Lowest ${formatPrice(found.low.price)}, highest ${formatPrice(found.high.price)}.`
            : 'Price history'
        }>
        {plotWidth > 0 ? (
          <>
            <Svg width={plotWidth} height={HEIGHT}>
              {bands.map((band) => (
                <Rect
                  key={band.from}
                  x={s.x(band.from)}
                  y={0}
                  width={Math.max(s.x(band.to) - s.x(band.from), 1)}
                  height={HEIGHT}
                  fill={theme.band}
                />
              ))}
              {[s.max, (s.max + s.min) / 2, s.min].map((value, index) => (
                <Line key={index} x1={0} x2={plotWidth} y1={s.y(value)} y2={s.y(value)} stroke={theme.border} strokeWidth={StyleSheet.hairlineWidth} />
              ))}
              {hasCompare ? (
                <Path
                  d={stepPath(view.points, view.end, s, (point) => (point.compareAt !== null && point.compareAt > point.price ? point.compareAt : null))}
                  stroke={theme.textSecondary}
                  strokeWidth={1.25}
                  strokeDasharray="4 4"
                  fill="none"
                />
              ) : null}
              <Path d={stepPath(view.points, view.end, s, (point) => point.price)} stroke={theme.accent} strokeWidth={2} fill="none" />
              {found && found.low.price !== found.high.price ? (
                <>
                  <Circle cx={s.x(found.low.t)} cy={s.y(found.low.price)} r={3.5} fill={theme.positive} />
                  <Circle cx={s.x(found.high.t)} cy={s.y(found.high.price)} r={3.5} fill={theme.negative} />
                </>
              ) : null}
              {active && cursor !== null ? (
                <>
                  <Line x1={cursor} x2={cursor} y1={0} y2={HEIGHT} stroke={theme.textSecondary} strokeWidth={1} />
                  <Circle cx={cursor} cy={s.y(active.price)} r={5} fill={theme.accent} stroke={theme.background} strokeWidth={2} />
                </>
              ) : null}
            </Svg>
            <View
              style={[styles.touch, { width: plotWidth }]}
              onStartShouldSetResponder={() => true}
              onMoveShouldSetResponder={() => true}
              onResponderGrant={track}
              onResponderMove={track}
              onResponderRelease={() => setCursor(null)}
              onResponderTerminate={() => setCursor(null)}
            />
            <View style={styles.axis} pointerEvents="none">
              {[s.max, (s.max + s.min) / 2, s.min].map((value, index) => (
                <ThemedText key={index} style={[styles.tick, { top: s.y(value) - 8 }]} themeColor="textSecondary">
                  {formatPriceShort(value)}
                </ThemedText>
              ))}
            </View>
          </>
        ) : null}
      </View>

      <View style={styles.dates}>
        <ThemedText style={styles.dateLabel} themeColor="textSecondary">{formatDate(view.start)}</ThemedText>
        <ThemedText style={styles.dateLabel} themeColor="textSecondary">{formatDate(view.end)}</ThemedText>
      </View>

      <View style={styles.legend}>
        <LegendItem color={theme.accent} label="Price" />
        {hasCompare ? <LegendItem color={theme.textSecondary} label="Was price" dashed /> : null}
        {bands.length > 0 ? <LegendItem color={theme.band} label="Out of stock" block /> : null}
      </View>

      <View style={styles.ranges}>
        {RANGES.map((key) => (
          <Chip key={key} label={key} selected={key === range} onPress={() => setRange(key)} accessibilityLabel={`Range ${key}`} />
        ))}
      </View>
    </View>
  );
}

function LegendItem({ color, label, dashed, block }: { color: string; label: string; dashed?: boolean; block?: boolean }) {
  return (
    <View style={styles.legendItem}>
      <View
        style={[
          block ? styles.legendBlock : styles.legendLine,
          block ? { backgroundColor: color } : { borderTopColor: color, borderStyle: dashed ? 'dashed' : 'solid' },
        ]}
      />
      <ThemedText style={styles.dateLabel} themeColor="textSecondary">{label}</ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: Spacing.two },
  readout: { minHeight: 44, justifyContent: 'flex-end' },
  readoutPrice: { fontSize: 20, lineHeight: 26, fontWeight: 700, fontVariant: ['tabular-nums'] },
  plot: { height: HEIGHT, flexDirection: 'row' },
  touch: { position: 'absolute', left: 0, top: 0, height: HEIGHT },
  axis: { width: AXIS, height: HEIGHT },
  tick: { position: 'absolute', right: 0, fontSize: 11, lineHeight: 16, fontVariant: ['tabular-nums'] },
  dates: { flexDirection: 'row', justifyContent: 'space-between', paddingRight: AXIS },
  dateLabel: { fontSize: 11, lineHeight: 16 },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.three },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: Spacing.one },
  legendLine: { width: 16, borderTopWidth: 2 },
  legendBlock: { width: 16, height: 10, borderRadius: 2 },
  ranges: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two, marginTop: Spacing.one },
  flat: {
    alignItems: 'center',
    gap: Spacing.one,
    padding: Spacing.four,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 10,
  },
  center: { textAlign: 'center' },
});
