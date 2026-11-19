import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as Notifications from 'expo-notifications';
import { DarkTheme, DefaultTheme, router, Stack, ThemeProvider } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { Platform, useColorScheme } from 'react-native';

import { Colors } from '@/constants/theme';
import { notificationPath, registerForBroadcastPush } from '@/lib/push';

if (Platform.OS !== 'web') {
  // Show the "new data" notification even when the app is open.
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: false,
      shouldSetBadge: false,
    }),
  });
}

/** Register for the "new data" push once, and open the screen a tapped notification points to. */
function usePushNotifications() {
  useEffect(() => {
    if (Platform.OS === 'web') return;
    registerForBroadcastPush().catch((error) => console.warn('Push registration skipped:', error?.message ?? error));

    const open = (response: Notifications.NotificationResponse | null) => {
      const path = notificationPath(response);
      if (!path) return;
      router.push(path as '/changes');
      Notifications.clearLastNotificationResponse();
    };
    open(Notifications.getLastNotificationResponse());
    const subscription = Notifications.addNotificationResponseReceivedListener(open);
    return () => subscription.remove();
  }, []);
}

export default function RootLayout() {
  usePushNotifications();
  const scheme = useColorScheme() === 'dark' ? 'dark' : 'light';
  const colors = Colors[scheme];
  const base = scheme === 'dark' ? DarkTheme : DefaultTheme;
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          // The catalog changes once a day, so cached screens stay useful for a long time.
          queries: { staleTime: 5 * 60_000, gcTime: 60 * 60_000, retry: 1 },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        value={{
          ...base,
          colors: {
            ...base.colors,
            background: colors.background,
            card: colors.background,
            text: colors.text,
            border: colors.border,
            primary: colors.accent,
          },
        }}>
        <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
        <Stack screenOptions={{ headerBackButtonDisplayMode: 'minimal', headerShadowVisible: false }}>
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="product/[id]" options={{ title: '' }} />
          <Stack.Screen name="brand/[slug]" options={{ title: '' }} />
        </Stack>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
