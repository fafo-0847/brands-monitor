// Chart maths for the price history. Pure: no React or React Native imports.
// The series is a step function: each point holds from its time until the next point.

export type Point = { t: number; price: number; compareAt: number | null; available: boolean };

export type RangeKey = '1W' | '1M' | '3M' | '6M' | '1Y' | 'All';
export const RANGES: RangeKey[] = ['1W', '1M', '3M', '6M', '1Y', 'All'];

const DAY = 86_400_000;
const RANGE_DAYS: Record<Exclude<RangeKey, 'All'>, number> = { '1W': 7, '1M': 30, '3M': 91, '6M': 182, '1Y': 365 };

export function toPoints(
  rows: { observed_at: string; price: number; compare_at_price: number | null; available: boolean }[],
): Point[] {
  return rows
    .map((row) => ({
      t: new Date(row.observed_at).getTime(),
      price: row.price,
      compareAt: row.compare_at_price,
      available: row.available,
    }))
    .sort((a, b) => a.t - b.t);
}

/** Points clipped to the range. The state in force at the range start becomes the first point. */
export function clip(points: Point[], range: RangeKey, now: number): { points: Point[]; start: number; end: number } {
  if (points.length === 0) return { points: [], start: now, end: now };
  const first = points[0].t;
  const wanted = range === 'All' ? first : now - RANGE_DAYS[range] * DAY;
  const start = Math.max(wanted, first);
  const end = Math.max(now, points[points.length - 1].t);
  const clipped: Point[] = [];
  for (const point of points) {
    if (point.t <= start) clipped[0] = { ...point, t: start };
    else clipped.push(point);
  }
  return { points: clipped, start, end };
}

export type Scale = {
  x: (t: number) => number;
  y: (price: number) => number;
  timeAt: (x: number) => number;
  min: number;
  max: number;
};

export function scale(points: Point[], start: number, end: number, width: number, height: number): Scale {
  let min = Infinity;
  let max = -Infinity;
  for (const point of points) {
    min = Math.min(min, point.price);
    max = Math.max(max, point.price, point.compareAt ?? -Infinity);
  }
  if (!Number.isFinite(min)) {
    min = 0;
    max = 1;
  }
  const pad = max === min ? Math.max(max * 0.05, 1) : (max - min) * 0.12;
  const low = min - pad;
  const high = max + pad;
  const span = Math.max(end - start, 1);
  return {
    x: (t) => ((t - start) / span) * width,
    y: (price) => height - ((price - low) / (high - low)) * height,
    timeAt: (x) => start + (Math.min(Math.max(x, 0), width) / Math.max(width, 1)) * span,
    min,
    max,
  };
}

/** SVG path for a step line through the values picked by `pick`; gaps where it returns null. */
export function stepPath(points: Point[], end: number, s: Scale, pick: (p: Point) => number | null): string {
  let path = '';
  let drawing = false;
  points.forEach((point, index) => {
    const value = pick(point);
    const nextT = index + 1 < points.length ? points[index + 1].t : end;
    if (value === null) {
      drawing = false;
      return;
    }
    const x = round(s.x(point.t));
    const y = round(s.y(value));
    path += drawing ? `V${y}` : `M${x} ${y}`;
    path += `H${round(s.x(nextT))}`;
    drawing = true;
  });
  return path;
}

/** Time intervals during which the item was out of stock. */
export function outOfStockBands(points: Point[], end: number): { from: number; to: number }[] {
  const bands: { from: number; to: number }[] = [];
  points.forEach((point, index) => {
    if (point.available) return;
    const to = index + 1 < points.length ? points[index + 1].t : end;
    const last = bands[bands.length - 1];
    if (last && last.to === point.t) last.to = to;
    else bands.push({ from: point.t, to });
  });
  return bands;
}

/** The point in force at time t (the last one at or before t). */
export function pointAt(points: Point[], t: number): Point | null {
  let found: Point | null = null;
  for (const point of points) {
    if (point.t <= t) found = point;
    else break;
  }
  return found ?? points[0] ?? null;
}

/** Lowest and highest points of the visible series (first occurrence of each). */
export function extremes(points: Point[]): { low: Point; high: Point } | null {
  if (points.length === 0) return null;
  let low = points[0];
  let high = points[0];
  for (const point of points) {
    if (point.price < low.price) low = point;
    if (point.price > high.price) high = point;
  }
  return { low, high };
}

/** True when the visible series never changes price or stock: there is nothing to chart yet. */
export function isFlat(points: Point[]): boolean {
  return points.every((p) => p.price === points[0].price && p.available === points[0].available);
}

function round(value: number): number {
  return Math.round(value * 10) / 10;
}
