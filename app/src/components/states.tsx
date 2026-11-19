import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { MinTouch, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { NotConfiguredError } from '@/lib/api';
import { AnonymousSignInDisabledError } from '@/lib/session';

export function Loading() {
  const theme = useTheme();
  return (
    <View style={styles.center} accessibilityLabel="Loading">
      <ActivityIndicator color={theme.textSecondary} />
    </View>
  );
}

export function Message({ title, detail, action, onAction }: {
  title: string;
  detail?: string;
  action?: string;
  onAction?: () => void;
}) {
  const theme = useTheme();
  return (
    <View style={styles.center}>
      <ThemedText type="smallBold" style={styles.text}>{title}</ThemedText>
      {detail ? <ThemedText type="small" themeColor="textSecondary" style={styles.text}>{detail}</ThemedText> : null}
      {action && onAction ? (
        <Pressable
          onPress={onAction}
          accessibilityRole="button"
          style={({ pressed }) => [styles.button, { borderColor: theme.border, opacity: pressed ? 0.6 : 1 }]}>
          <ThemedText type="smallBold">{action}</ThemedText>
        </Pressable>
      ) : null}
    </View>
  );
}

export function ErrorMessage({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (error instanceof NotConfiguredError) {
    return (
      <Message
        title="Not connected yet"
        detail="Add EXPO_PUBLIC_SUPABASE_URL and EXPO_PUBLIC_SUPABASE_ANON_KEY to app/.env, then restart the app."
      />
    );
  }
  if (error instanceof AnonymousSignInDisabledError) {
    return (
      <Message
        title="Watchlist is not switched on yet"
        detail="Turn on anonymous sign-ins in Supabase: Authentication → Sign In / Providers → Allow anonymous sign-ins."
      />
    );
  }
  const detail = error instanceof Error ? error.message : 'Something went wrong.';
  return <Message title="Could not load" detail={detail} action="Try again" onAction={onRetry} />;
}

const styles = StyleSheet.create({
  center: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.two,
    padding: Spacing.four,
    minHeight: 160,
  },
  text: { textAlign: 'center' },
  button: {
    minHeight: MinTouch,
    justifyContent: 'center',
    paddingHorizontal: Spacing.four,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: Radius.medium,
    marginTop: Spacing.two,
  },
});
