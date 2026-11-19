// Each phone gets its own anonymous Supabase account the first time it needs one (watchlist,
// alerts). It can later be linked to Google or email sign-in without losing anything.
import { isConfigured, supabase } from '@/lib/supabase';
import { NotConfiguredError } from '@/lib/api-errors';

export class AnonymousSignInDisabledError extends Error {
  constructor() {
    super('Anonymous sign-ins are switched off in Supabase (Authentication → Sign In / Providers).');
  }
}

let pending: Promise<string> | null = null;

/** The current user's id, signing in anonymously when there is no session yet. */
export function ensureSession(): Promise<string> {
  if (!isConfigured) return Promise.reject(new NotConfiguredError());
  pending ??= (async () => {
    const { data } = await supabase.auth.getSession();
    if (data.session) return data.session.user.id;
    const { data: created, error } = await supabase.auth.signInAnonymously();
    if (error) {
      if (/anonymous/i.test(error.message) && /disabled|not enabled/i.test(error.message)) {
        throw new AnonymousSignInDisabledError();
      }
      throw new Error(error.message);
    }
    if (!created.user) throw new Error('Sign-in returned no user');
    return created.user.id;
  })().finally(() => {
    pending = null;
  });
  return pending;
}

/** The current user's id, or null without creating an account. */
export async function currentUserId(): Promise<string | null> {
  if (!isConfigured) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.user.id ?? null;
}
