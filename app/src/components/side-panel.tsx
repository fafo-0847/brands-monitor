import type { ReactNode } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { MinTouch, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type Props = {
  visible: boolean;
  title: string;
  onClose: () => void;
  onClear: () => void;
  onApply: () => void;
  /** Text on the apply button, for example "Show 1,234 products". */
  applyLabel: string;
  children: ReactNode;
};

/** Filters and sort in a panel that slides over the screen from the right. */
export function SidePanel({ visible, title, onClose, onClear, onApply, applyLabel, children }: Props) {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const panelWidth = Math.min(400, Math.round(width * 0.9));

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      <View style={styles.backdrop}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Close filters" />
        <View style={[styles.panel, { width: panelWidth, backgroundColor: theme.background, borderLeftColor: theme.border }]}>
          <SafeAreaView style={styles.fill} edges={['top', 'bottom']}>
            <View style={[styles.header, { borderBottomColor: theme.border }]}>
              <ThemedText style={styles.title} accessibilityRole="header">{title}</ThemedText>
              <Pressable onPress={onClose} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close">
                <ThemedText style={styles.close} themeColor="textSecondary">✕</ThemedText>
              </Pressable>
            </View>
            <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
              {children}
            </ScrollView>
            <View style={[styles.footer, { borderTopColor: theme.border }]}>
              <Pressable
                onPress={onClear}
                accessibilityRole="button"
                style={({ pressed }) => [styles.clear, { borderColor: theme.border, opacity: pressed ? 0.6 : 1 }]}>
                <ThemedText type="smallBold">Clear all</ThemedText>
              </Pressable>
              <Pressable
                onPress={onApply}
                accessibilityRole="button"
                style={({ pressed }) => [styles.apply, { backgroundColor: theme.accent, opacity: pressed ? 0.8 : 1 }]}>
                <ThemedText style={[styles.applyText, { color: theme.onAccent }]} numberOfLines={1}>{applyLabel}</ThemedText>
              </Pressable>
            </View>
          </SafeAreaView>
        </View>
      </View>
    </Modal>
  );
}

/** A titled group of options inside the panel. */
export function PanelSection({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <View style={styles.section}>
      <ThemedText style={styles.sectionTitle} accessibilityRole="header">{title}</ThemedText>
      {hint ? <ThemedText style={styles.hint} themeColor="textSecondary">{hint}</ThemedText> : null}
      <View style={styles.wrap}>{children}</View>
    </View>
  );
}

/** The "⚙ Filters" button that opens the panel, with how many filters are on. */
export function FilterButton({ count, onPress }: { count: number; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={count > 0 ? `Filters and sort, ${count} on` : 'Filters and sort'}
      style={({ pressed }) => [
        styles.button,
        { borderColor: count > 0 ? theme.accent : theme.border, opacity: pressed ? 0.6 : 1 },
      ]}>
      <ThemedText type="smallBold" style={count > 0 ? { color: theme.accent } : undefined}>
        ⚙ Filters{count > 0 ? ` · ${count}` : ''}
      </ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', flexDirection: 'row', justifyContent: 'flex-end' },
  panel: { height: '100%', borderLeftWidth: StyleSheet.hairlineWidth },
  fill: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.three,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  title: { fontSize: 20, lineHeight: 26, fontWeight: 700 },
  close: { fontSize: 20, lineHeight: 26 },
  body: { padding: Spacing.three, gap: Spacing.four, paddingBottom: Spacing.five },
  section: { gap: Spacing.two },
  sectionTitle: { fontSize: 15, lineHeight: 20, fontWeight: 700 },
  hint: { fontSize: 12, lineHeight: 16 },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  footer: {
    flexDirection: 'row',
    gap: Spacing.two,
    padding: Spacing.three,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  clear: {
    minHeight: MinTouch,
    justifyContent: 'center',
    paddingHorizontal: Spacing.three,
    borderRadius: Radius.medium,
    borderWidth: StyleSheet.hairlineWidth,
  },
  apply: { flex: 1, minHeight: MinTouch, alignItems: 'center', justifyContent: 'center', borderRadius: Radius.medium },
  applyText: { fontSize: 15, lineHeight: 20, fontWeight: 700 },
  button: {
    minHeight: 36,
    justifyContent: 'center',
    paddingHorizontal: Spacing.three,
    borderRadius: 18,
    borderWidth: StyleSheet.hairlineWidth,
  },
});
