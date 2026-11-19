// "New data is in" notifications. There are no accounts yet, so the phone registers its Expo push
// token anonymously (register_device). The pipeline sends one push after each ingest run.
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import { AndroidImportance } from 'expo-notifications';
import { Platform } from 'react-native';

import { ensureSession } from '@/lib/session';
import { isConfigured, supabase } from '@/lib/supabase';

/** Paths a notification may open; anything else is ignored. */
const ALLOWED_PATHS = new Set(['/changes', '/', '/watchlist']);

export function notificationPath(response: Notifications.NotificationResponse | null | undefined): string | null {
  const url = response?.notification.request.content.data?.url;
  if (typeof url !== 'string') return null;
  return ALLOWED_PATHS.has(url) || /^\/product\/\d{1,12}$/.test(url) ? url : null;
}

export type PushStatus = 'registered' | 'denied' | 'unavailable';

/**
 * Ask for permission and register this phone. Returns 'unavailable' on web, without the database
 * settings, or before the EAS project is linked (no projectId). Throws on Expo Go for Android,
 * which cannot receive remote pushes; callers ignore that.
 */
export async function registerForBroadcastPush(): Promise<PushStatus> {
  if (Platform.OS === 'web' || !isConfigured) return 'unavailable';
  const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
  if (!projectId) return 'unavailable';

  // On Android 13+ the channel must exist before asking, or the permission prompt never appears.
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'New data',
      description: 'A short summary after each price and stock check',
      importance: AndroidImportance.HIGH,
    });
  }
  let { status } = await Notifications.getPermissionsAsync();
  if (status !== 'granted') {
    ({ status } = await Notifications.requestPermissionsAsync());
  }
  if (status !== 'granted') return 'denied';

  const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
  const { error } = await supabase.rpc('register_device', {
    p_token: token,
    p_platform: Platform.OS,
    p_app_version: Constants.expoConfig?.version ?? null,
  });
  if (error) throw new Error(error.message);
  // The same token also receives this phone's watchlist alerts, under its anonymous account.
  await ensureSession();
  const linked = await supabase.rpc('register_my_device', {
    p_token: token,
    p_platform: Platform.OS,
    p_app_version: Constants.expoConfig?.version ?? null,
  });
  if (linked.error) throw new Error(linked.error.message);
  return 'registered';
}
