import { Pressable, StyleSheet } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type Props = {
  label: string;
  selected?: boolean;
  /** Shown crossed out: this item is hidden from the results. */
  excluded?: boolean;
  disabled?: boolean;
  onPress?: () => void;
  accessibilityLabel?: string;
};

export function Chip({ label, selected = false, excluded = false, disabled = false, onPress, accessibilityLabel }: Props) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      hitSlop={6}
      accessibilityRole="button"
      accessibilityState={{ selected, disabled }}
      accessibilityLabel={`${accessibilityLabel ?? label}${excluded ? ', hidden' : ''}`}
      style={({ pressed }) => [
        styles.chip,
        {
          backgroundColor: selected ? theme.text : theme.backgroundElement,
          borderColor: selected ? theme.text : excluded ? theme.negative : theme.border,
          opacity: disabled ? 0.45 : pressed ? 0.7 : 1,
        },
      ]}>
      <ThemedText
        style={[
          styles.label,
          { color: selected ? theme.background : excluded ? theme.negative : theme.text },
          excluded && styles.excluded,
        ]}>
        {excluded ? `✕ ${label}` : label}
      </ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    minHeight: 36,
    justifyContent: 'center',
    paddingHorizontal: Spacing.three,
    borderRadius: 18,
    borderWidth: StyleSheet.hairlineWidth,
  },
  label: { fontSize: 13, lineHeight: 18, fontWeight: 600 },
  excluded: { textDecorationLine: 'line-through' },
});
