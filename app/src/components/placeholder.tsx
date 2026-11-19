import { StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, Spacing } from '@/constants/theme';

/** A tab whose feature is not built yet: says so plainly instead of showing an empty screen. */
export function Placeholder({ title, detail }: { title: string; detail: string }) {
  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView style={styles.screen} edges={['top']}>
        <ThemedText style={styles.heading} accessibilityRole="header">{title}</ThemedText>
        <View style={styles.center}>
          <ThemedText type="smallBold">Not available yet</ThemedText>
          <ThemedText type="small" themeColor="textSecondary" style={styles.detail}>{detail}</ThemedText>
        </View>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  heading: { fontSize: 26, lineHeight: 32, fontWeight: 700, padding: Spacing.three },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.two,
    padding: Spacing.five,
    paddingBottom: BottomTabInset + Spacing.five,
  },
  detail: { textAlign: 'center', maxWidth: 360 },
});
