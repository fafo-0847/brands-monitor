import { StyleSheet, TextInput, View } from 'react-native';

import { Chip } from '@/components/chip';
import { PanelSection } from '@/components/side-panel';
import { ThemedText } from '@/components/themed-text';
import { MinTouch, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { priceBands, rupeesInput, type PriceStats } from '@/lib/filters';

type Props = {
  min: number | null | undefined;
  max: number | null | undefined;
  onChange: (min: number | null, max: number | null) => void;
  /** Spread of the current results; ranges are worked out from it. */
  stats: PriceStats | undefined;
};

const asText = (minor: number | null | undefined) => (minor === null || minor === undefined ? '' : String(Math.round(minor / 100)));

/** Price ranges that fit the current results, plus Min / Max boxes to type any range. */
export function PriceSection({ min, max, onChange, stats }: Props) {
  const theme = useTheme();
  const bands = priceBands(stats);
  // The boxes show the current values and apply as you type, so pressing Show never misses an entry.
  const minText = asText(min);
  const maxText = asText(max);
  const commit = (nextMin: string, nextMax: string) => onChange(rupeesInput(nextMin), rupeesInput(nextMax));

  const inputStyle = [styles.input, { backgroundColor: theme.backgroundElement, color: theme.text, borderColor: theme.border }];
  const hint = stats && stats.n > 0 && stats.min !== null && stats.max !== null
    ? `Current results: PKR ${asText(stats.min)} – ${asText(stats.max)}`
    : undefined;

  return (
    <PanelSection title="Price (PKR)" hint={hint}>
      {bands.map((band) => (
        <Chip
          key={band.label}
          label={band.label}
          selected={(min ?? null) === band.min && (max ?? null) === band.max}
          onPress={() => {
            const on = (min ?? null) === band.min && (max ?? null) === band.max;
            onChange(on ? null : band.min, on ? null : band.max);
          }}
          accessibilityLabel={`Price ${band.label} rupees`}
        />
      ))}
      <View style={styles.inputs}>
        <TextInput
          value={minText}
          onChangeText={(text) => commit(text, maxText)}
          placeholder="Min"
          placeholderTextColor={theme.textSecondary}
          keyboardType="number-pad"
          returnKeyType="done"
          accessibilityLabel="Minimum price in rupees"
          style={inputStyle}
        />
        <ThemedText themeColor="textSecondary">–</ThemedText>
        <TextInput
          value={maxText}
          onChangeText={(text) => commit(minText, text)}
          placeholder="Max"
          placeholderTextColor={theme.textSecondary}
          keyboardType="number-pad"
          returnKeyType="done"
          accessibilityLabel="Maximum price in rupees"
          style={inputStyle}
        />
      </View>
    </PanelSection>
  );
}

const styles = StyleSheet.create({
  inputs: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, width: '100%' },
  input: {
    flex: 1,
    minHeight: MinTouch,
    borderRadius: Radius.medium,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: Spacing.three,
    fontSize: 15,
  },
});
