import { ScrollView, StyleSheet, View } from 'react-native';

import { Chip } from '@/components/chip';
import { Spacing } from '@/constants/theme';
import type { SearchParams, SortKey } from '@/lib/api';

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

const CATEGORIES = [
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

type Props = {
  value: SearchParams;
  onChange: (next: SearchParams) => void;
  /** Size chips are hidden where the brand has no size-level data. */
  showSizes?: boolean;
};

function toggle(list: string[] | undefined, key: string): string[] {
  const current = list ?? [];
  return current.includes(key) ? current.filter((item) => item !== key) : [...current, key];
}

export function FilterBar({ value, onChange, showSizes = true }: Props) {
  const sort = value.sort ?? 'relevance';
  return (
    <View style={styles.wrap}>
      <Row label="Sort">
        {SORTS.map((item) => (
          <Chip key={item.key} label={item.label} selected={sort === item.key} onPress={() => onChange({ ...value, sort: item.key })} />
        ))}
      </Row>
      <Row label="Filters">
        <Chip label="In stock" selected={Boolean(value.inStock)} onPress={() => onChange({ ...value, inStock: !value.inStock })} />
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
      <Row label="Category">
        {CATEGORIES.map((item) => (
          <Chip
            key={item.key}
            label={item.label}
            selected={value.categories?.includes(item.key)}
            onPress={() => onChange({ ...value, categories: toggle(value.categories, item.key) })}
          />
        ))}
      </Row>
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
});
