import { useState } from 'react';
import { ScrollView, StyleSheet, TextInput, View } from 'react-native';

import { Chip } from '@/components/chip';
import { MinTouch, Radius, Spacing } from '@/constants/theme';
import { ThemedText } from '@/components/themed-text';
import { useTheme } from '@/hooks/use-theme';
import type { Brand, SearchParams, SortKey } from '@/lib/api';
import { cycle, stateOf } from '@/lib/tristate';

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'relevance', label: 'Best match' },
  { key: 'discount', label: 'Biggest discount' },
  { key: 'price_asc', label: 'Price: low to high' },
  { key: 'price_desc', label: 'Price: high to low' },
  { key: 'recent_price_change', label: 'Recent price change' },
  { key: 'newest', label: 'Newest' },
];

const GENDERS = [
  { key: 'women', label: 'Women' },
  { key: 'men', label: 'Men' },
  { key: 'kids', label: 'Kids' },
];

export const CATEGORIES = [
  { key: 'unstitched', label: 'Unstitched' },
  { key: 'eastern', label: 'Eastern' },
  { key: 'western', label: 'Western' },
  { key: 'formal', label: 'Formal' },
  { key: 'footwear', label: 'Footwear' },
  { key: 'bags-accessories', label: 'Bags & accessories' },
  { key: 'fragrance-beauty', label: 'Fragrance & beauty' },
  { key: 'home', label: 'Home' },
];

const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];

// Rupee bands picked from the spread of tracked prices (median about PKR 2,600, 90% under PKR 8,000).
const PRICE_BANDS: { label: string; min: number | null; max: number | null }[] = [
  { label: 'Under 2,000', min: null, max: 1_999 },
  { label: '2,000 – 5,000', min: 2_000, max: 5_000 },
  { label: '5,000 – 10,000', min: 5_000, max: 10_000 },
  { label: '10,000 – 20,000', min: 10_000, max: 20_000 },
  { label: 'Over 20,000', min: 20_000, max: null },
];

const toMinor = (rupees: number | null) => (rupees === null ? null : rupees * 100);
const toRupees = (minor: number | null | undefined) => (minor === null || minor === undefined ? null : Math.round(minor / 100));

type Props = {
  value: SearchParams;
  onChange: (next: SearchParams) => void;
  /** Size chips are hidden where the brand has no size-level data. */
  showSizes?: boolean;
  /** Brands to offer as a row of chips (Search). */
  brands?: Brand[];
};

function toggle(list: string[] | undefined, key: string): string[] {
  const current = list ?? [];
  return current.includes(key) ? current.filter((item) => item !== key) : [...current, key];
}

export function FilterBar({ value, onChange, showSizes = true, brands }: Props) {
  const sort = value.sort ?? 'relevance';
  const categoryLists = { include: value.categories ?? [], exclude: value.excludeCategories ?? [] };
  const brandLists = { include: value.brandIds ?? [], exclude: value.excludeBrandIds ?? [] };
  return (
    <View style={styles.wrap}>
      <Row label="Sort">
        {SORTS.map((item) => (
          <Chip key={item.key} label={item.label} selected={sort === item.key} onPress={() => onChange({ ...value, sort: item.key })} />
        ))}
      </Row>
      <Row label="Filters">
        <Chip
          label="In stock"
          selected={Boolean(value.inStock)}
          onPress={() => onChange({ ...value, inStock: !value.inStock, outOfStock: false })}
        />
        <Chip
          label="Out of stock"
          selected={Boolean(value.outOfStock)}
          onPress={() => onChange({ ...value, outOfStock: !value.outOfStock, inStock: false })}
        />
        <Chip label="On sale" selected={Boolean(value.onSale)} onPress={() => onChange({ ...value, onSale: !value.onSale })} />
        {GENDERS.map((item) => (
          <Chip
            key={item.key}
            label={item.label}
            selected={value.genders?.includes(item.key)}
            onPress={() => onChange({ ...value, genders: toggle(value.genders, item.key) })}
          />
        ))}
      </Row>
      <PriceRow value={value} onChange={onChange} />
      <Row label="Category">
        {CATEGORIES.map((item) => (
          <Chip
            key={item.key}
            label={item.label}
            selected={stateOf(categoryLists, item.key) === 'include'}
            excluded={stateOf(categoryLists, item.key) === 'exclude'}
            onPress={() => {
              const next = cycle(categoryLists, item.key);
              onChange({ ...value, categories: next.include, excludeCategories: next.exclude });
            }}
          />
        ))}
      </Row>
      {brands && brands.length > 1 ? (
        <Row label="Brand">
          {brands.map((brand) => (
            <Chip
              key={brand.id}
              label={brand.name}
              selected={stateOf(brandLists, brand.id) === 'include'}
              excluded={stateOf(brandLists, brand.id) === 'exclude'}
              onPress={() => {
                const next = cycle(brandLists, brand.id);
                onChange({ ...value, brandIds: next.include, excludeBrandIds: next.exclude });
              }}
            />
          ))}
        </Row>
      ) : null}
      <ThemedText style={styles.hint} themeColor="textSecondary">
        Tap a category{brands && brands.length > 1 ? ' or brand' : ''} once to show only it, twice to hide it.
      </ThemedText>
      {showSizes ? (
        <Row label="Size in stock">
          {SIZES.map((size) => (
            <Chip
              key={size}
              label={size}
              selected={value.sizes?.includes(size)}
              onPress={() => onChange({ ...value, sizes: toggle(value.sizes, size) })}
              accessibilityLabel={`Size ${size}`}
            />
          ))}
        </Row>
      ) : null}
    </View>
  );
}

/** Price bands plus a custom min/max. Reads and writes priceMin/priceMax (minor units) on `value`. */
export function PriceRow<T extends Pick<SearchParams, 'priceMin' | 'priceMax'>>({ value, onChange }: {
  value: T;
  onChange: (next: T) => void;
}) {
  const theme = useTheme();
  const min = toRupees(value.priceMin);
  const max = toRupees(value.priceMax);
  const band = PRICE_BANDS.find((item) => item.min === min && item.max === max);
  const active = min !== null || max !== null;
  const [custom, setCustom] = useState(active && !band);
  const [minText, setMinText] = useState(min !== null && !band ? String(min) : '');
  const [maxText, setMaxText] = useState(max !== null && !band ? String(max) : '');

  const setRange = (low: number | null, high: number | null) =>
    onChange({ ...value, priceMin: toMinor(low), priceMax: toMinor(high) });

  const applyCustom = () => {
    const parse = (text: string) => {
      const digits = text.replace(/[^0-9]/g, '');
      return digits ? Number(digits) : null;
    };
    let low = parse(minText);
    let high = parse(maxText);
    if (low !== null && high !== null && low > high) [low, high] = [high, low];
    setRange(low, high);
  };

  const inputStyle = [styles.input, { backgroundColor: theme.backgroundElement, color: theme.text, borderColor: theme.border }];

  return (
    <View style={styles.priceWrap}>
      <Row label="Price">
        <Chip
          label="Any price"
          selected={!active && !custom}
          onPress={() => {
            setCustom(false);
            setRange(null, null);
          }}
        />
        {PRICE_BANDS.map((item) => (
          <Chip
            key={item.label}
            label={item.label}
            selected={!custom && band === item}
            onPress={() => {
              setCustom(false);
              if (band === item) setRange(null, null);
              else setRange(item.min, item.max);
            }}
            accessibilityLabel={`Price ${item.label} rupees`}
          />
        ))}
        <Chip label="Custom" selected={custom} onPress={() => setCustom(!custom)} accessibilityLabel="Custom price range" />
      </Row>
      {custom ? (
        <View style={styles.customRow}>
          <TextInput
            value={minText}
            onChangeText={setMinText}
            onEndEditing={applyCustom}
            onSubmitEditing={applyCustom}
            placeholder="Min PKR"
            placeholderTextColor={theme.textSecondary}
            keyboardType="number-pad"
            returnKeyType="done"
            accessibilityLabel="Minimum price in rupees"
            style={inputStyle}
          />
          <TextInput
            value={maxText}
            onChangeText={setMaxText}
            onEndEditing={applyCustom}
            onSubmitEditing={applyCustom}
            placeholder="Max PKR"
            placeholderTextColor={theme.textSecondary}
            keyboardType="number-pad"
            returnKeyType="done"
            accessibilityLabel="Maximum price in rupees"
            style={inputStyle}
          />
          <Chip label="Apply" onPress={applyCustom} accessibilityLabel="Apply price range" />
        </View>
      ) : null}
    </View>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
      accessibilityLabel={label}
      keyboardShouldPersistTaps="handled">
      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: Spacing.two, marginHorizontal: -Spacing.three, paddingBottom: Spacing.three },
  row: { gap: Spacing.two, paddingHorizontal: Spacing.three },
  priceWrap: { gap: Spacing.two },
  hint: { fontSize: 12, lineHeight: 16, paddingHorizontal: Spacing.three },
  customRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, paddingHorizontal: Spacing.three },
  input: {
    flex: 1,
    minHeight: MinTouch,
    borderRadius: Radius.medium,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: Spacing.three,
    fontSize: 15,
  },
});
