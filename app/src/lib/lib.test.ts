// Run with: npm test   (node's built-in test runner; TypeScript types are stripped by node)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { dayLabel, formatAgo, formatCount, formatPrice, formatPriceShort, isStale, percentChange } from './format.ts';
import { cycle, passes, stateOf } from './tristate.ts';
import { activeFilterCount, niceRupees, priceBands, rupeesInput } from './filters.ts';
import { clip, extremes, isFlat, outOfStockBands, pointAt, scale, stepPath, toPoints, type Point } from './series.ts';

const DAY = 86_400_000;
const T0 = Date.UTC(2026, 10, 1);
const point = (day: number, price: number, available = true, compareAt: number | null = null): Point => ({
  t: T0 + day * DAY,
  price,
  compareAt,
  available,
});

test('formatPrice', () => {
  assert.equal(formatPrice(199900), 'PKR 1,999');
  assert.equal(formatPrice(1499900), 'PKR 14,999');
  assert.equal(formatPrice(123456789), 'PKR 1,234,567.89');
  assert.equal(formatPrice(50), 'PKR 0.50');
  assert.equal(formatPrice(0), 'PKR 0');
  assert.equal(formatPrice(null), '—');
});

test('formatPriceShort', () => {
  assert.equal(formatPriceShort(1250000), '12.5k');
  assert.equal(formatPriceShort(99900), '999');
  assert.equal(formatPriceShort(25000000), '250k');
  assert.equal(formatPriceShort(150000000), '1.5M');
});

test('formatCount and dayLabel', () => {
  assert.equal(formatCount(0), '0');
  assert.equal(formatCount(1234567), '1,234,567');
  assert.equal(formatCount(10000, 10000), '10,000');
  assert.equal(formatCount(10001, 10000), '10,000+');
  const now = new Date(2026, 10, 17, 12);
  assert.equal(dayLabel('2026-11-17', now), 'Today');
  assert.equal(dayLabel('2026-11-16', now), 'Yesterday');
  assert.equal(dayLabel('2026-11-12', now), '12 Nov');
  assert.equal(dayLabel('2025-12-30', now), '30 Dec 2025');
});

test('three-state chips cycle off, include, exclude', () => {
  let lists = { include: [] as number[], exclude: [] as number[] };
  lists = cycle(lists, 1);
  assert.deepEqual(lists, { include: [1], exclude: [] });
  assert.equal(stateOf(lists, 1), 'include');
  lists = cycle(lists, 1);
  assert.deepEqual(lists, { include: [], exclude: [1] });
  assert.equal(passes(lists, 1), false);
  assert.equal(passes(lists, 2), true);
  lists = cycle(cycle(lists, 2), 1);
  assert.deepEqual(lists, { include: [2], exclude: [] });
  assert.equal(passes(lists, 3), false);
});

test('percentChange', () => {
  assert.equal(percentChange(300000, 150000), -50);
  assert.equal(percentChange(100000, 125000), 25);
  assert.equal(percentChange(null, 100), null);
  assert.equal(percentChange(0, 100), null);
});

test('formatAgo and isStale', () => {
  const now = new Date(T0 + 10 * DAY);
  assert.equal(formatAgo(new Date(T0 + 10 * DAY - 3_600_000).toISOString(), now), 'today');
  assert.equal(formatAgo(new Date(T0 + 9 * DAY - 1).toISOString(), now), 'yesterday');
  assert.equal(formatAgo(new Date(T0 + 5 * DAY).toISOString(), now), '5 days ago');
  assert.equal(formatAgo(null, now), 'never');
  assert.equal(isStale(new Date(T0 + 9 * DAY).toISOString(), now), false);
  assert.equal(isStale(new Date(T0 + 7 * DAY).toISOString(), now), true);
  assert.equal(isStale(null, now), true);
});

test('toPoints sorts by time', () => {
  const points = toPoints([
    { observed_at: '2026-11-03T00:00:00Z', price: 2, compare_at_price: null, available: true },
    { observed_at: '2026-11-01T00:00:00Z', price: 1, compare_at_price: 5, available: false },
  ]);
  assert.deepEqual(points.map((p) => p.price), [1, 2]);
  assert.equal(points[0].compareAt, 5);
});

test('clip carries the state at the range start into the window', () => {
  const points = [point(0, 500), point(20, 400), point(38, 300)];
  const now = T0 + 40 * DAY;
  const week = clip(points, '1W', now);
  assert.equal(week.start, now - 7 * DAY);
  assert.deepEqual(week.points.map((p) => [p.t, p.price]), [[now - 7 * DAY, 400], [T0 + 38 * DAY, 300]]);
  const all = clip(points, 'All', now);
  assert.equal(all.start, T0);
  assert.equal(all.points.length, 3);
  const year = clip(points, '1Y', now);
  assert.equal(year.start, T0, 'a range longer than the history starts at the first point');
  assert.deepEqual(clip([], '1M', now).points, []);
});

test('scale maps the window onto the drawing area with padding', () => {
  const points = [point(0, 100), point(5, 200)];
  const s = scale(points, T0, T0 + 10 * DAY, 300, 100);
  assert.equal(s.x(T0), 0);
  assert.equal(s.x(T0 + 10 * DAY), 300);
  assert.ok(s.y(200) > 0 && s.y(100) < 100, 'prices sit inside the padded area');
  assert.ok(s.y(200) < s.y(100), 'higher price is drawn higher');
  assert.equal(s.timeAt(150), T0 + 5 * DAY);
  assert.equal(s.timeAt(-50), T0);
  const flat = scale([point(0, 100)], T0, T0 + DAY, 300, 100);
  assert.equal(flat.y(100), 50, 'a flat series is centred');
});

test('stepPath draws horizontal then vertical segments and breaks on gaps', () => {
  const points = [point(0, 100), point(5, 200), point(8, 200, true, 300)];
  const s = scale(points, T0, T0 + 10 * DAY, 100, 100);
  const price = stepPath(points, T0 + 10 * DAY, s, (p) => p.price);
  assert.match(price, /^M0 [\d.]+H50V[\d.]+H80V[\d.]+H100$/);
  const compare = stepPath(points, T0 + 10 * DAY, s, (p) => p.compareAt);
  assert.match(compare, /^M80 [\d.]+H100$/);
  assert.equal(stepPath([], T0, s, (p) => p.price), '');
});

test('outOfStockBands merges neighbouring out-of-stock steps', () => {
  const points = [point(0, 1), point(2, 1, false), point(4, 2, false), point(6, 2), point(8, 2, false)];
  assert.deepEqual(outOfStockBands(points, T0 + 10 * DAY), [
    { from: T0 + 2 * DAY, to: T0 + 6 * DAY },
    { from: T0 + 8 * DAY, to: T0 + 10 * DAY },
  ]);
});

test('pointAt, extremes and isFlat', () => {
  const points = [point(0, 300), point(2, 100), point(4, 500), point(6, 100)];
  assert.equal(pointAt(points, T0 + 3 * DAY)?.price, 100);
  assert.equal(pointAt(points, T0 - DAY)?.price, 300);
  assert.equal(pointAt([], T0), null);
  const found = extremes(points);
  assert.equal(found?.low.t, T0 + 2 * DAY);
  assert.equal(found?.high.price, 500);
  assert.equal(isFlat(points), false);
  assert.equal(isFlat([point(0, 100), point(3, 100)]), true);
  assert.equal(isFlat([point(0, 100), point(3, 100, false)]), false);
});

test('niceRupees rounds to readable steps', () => {
  assert.equal(niceRupees(847), 800);
  assert.equal(niceRupees(1490), 1500);
  assert.equal(niceRupees(2625), 2500);
  assert.equal(niceRupees(4695), 4500);
  assert.equal(niceRupees(7875), 8000);
  assert.equal(niceRupees(23_400), 22_500);
  assert.equal(niceRupees(0), 0);
});

test('priceBands follow the spread of the results', () => {
  const bands = priceBands({ n: 500, min: 39900, max: 2_500_000, q: [149000, 262500, 469500, 787500] });
  assert.deepEqual(bands.map((band) => band.label),
    ['Under 1,500', '1,500 – 2,500', '2,500 – 4,500', '4,500 – 8,000', '8,000 and up']);
  assert.deepEqual([bands[0].min, bands[0].max], [null, 149999]);
  assert.deepEqual([bands[1].min, bands[1].max], [150000, 249999]);
  assert.deepEqual([bands[4].min, bands[4].max], [800000, null]);
  // Prices bunched together give fewer ranges; one price or none gives no ranges.
  assert.equal(priceBands({ n: 50, min: 300000, max: 320000, q: [310000, 310000, 310000, 310000] }).length, 2);
  assert.deepEqual(priceBands({ n: 1, min: 100, max: 100, q: [100, 100, 100, 100] }), []);
  assert.deepEqual(priceBands({ n: 0, min: null, max: null, q: null }), []);
  assert.deepEqual(priceBands(null), []);
});

test('rupeesInput and activeFilterCount', () => {
  assert.equal(rupeesInput(' 2,500 '), 250000);
  assert.equal(rupeesInput(''), null);
  assert.equal(rupeesInput('abc'), null);
  assert.equal(activeFilterCount({}), 0);
  assert.equal(activeFilterCount({ categories: [], priceMin: null, onSale: false }), 0);
  assert.equal(activeFilterCount({ excludeBrandIds: [3], priceMax: 500000, changeKinds: ['price_drop'], outOfStock: true }), 4);
  assert.equal(activeFilterCount({ brandIds: [1], excludeBrandIds: [2] }), 1);
});
