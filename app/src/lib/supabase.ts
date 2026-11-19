import 'expo-sqlite/localStorage/install';

import { createClient } from '@supabase/supabase-js';
import Constants from 'expo-constants';

// The project URL and anon key are public by design (row-level security protects the data). They
// live in app.json `extra.supabase` so every build and over-the-air update carries them; EAS Update
// does not read app/.env. EXPO_PUBLIC_* variables, when set, take precedence (e.g. a local database).
const fromConfig = (Constants.expoConfig?.extra?.supabase ?? {}) as { url?: string; anonKey?: string };
const url = process.env.EXPO_PUBLIC_SUPABASE_URL || fromConfig.url;
const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || fromConfig.anonKey;

/** False when app/.env is missing; screens show a setup message instead of failing requests. */
export const isConfigured = Boolean(url && anonKey);

export const supabase = createClient(url ?? 'http://localhost', anonKey ?? 'not-configured', {
  auth: {
    storage: localStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});
