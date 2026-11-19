import '@/global.css';

import { Platform } from 'react-native';

// Dark is the reference design; light has the same roles. Green and red are never the only
// signal: every use is paired with an arrow or a label.
export const Colors = {
  light: {
    text: '#11181C',
    textSecondary: '#5F6770',
    background: '#FFFFFF',
    backgroundElement: '#F2F3F5',
    backgroundSelected: '#E2E4E9',
    border: '#DCDFE4',
    accent: '#2563EB',
    onAccent: '#FFFFFF',
    positive: '#0B7A43',
    negative: '#C0362C',
    band: 'rgba(192, 54, 44, 0.10)',
  },
  dark: {
    text: '#F2F3F5',
    textSecondary: '#A0A6AE',
    background: '#0B0D10',
    backgroundElement: '#16191E',
    backgroundSelected: '#252A31',
    border: '#2A2F37',
    accent: '#5B9BFF',
    onAccent: '#0B0D10',
    positive: '#3DD68C',
    negative: '#FF7A6E',
    band: 'rgba(255, 122, 110, 0.14)',
  },
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

export const Fonts = Platform.select({
  ios: { sans: 'system-ui', serif: 'ui-serif', rounded: 'ui-rounded', mono: 'ui-monospace' },
  default: { sans: 'normal', serif: 'serif', rounded: 'normal', mono: 'monospace' },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const Radius = { small: 6, medium: 10, large: 16 } as const;
export const MinTouch = 44;
export const MaxContentWidth = 960;
/** Space the native tab bar covers at the bottom of tab screens (web keeps its own padding). */
export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
