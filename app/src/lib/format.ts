// Pure helpers: no React or React Native imports, so they run under `node --test`.

/** 199900 -> "PKR 1,999". Paisa are shown only when they are not zero. */
export function formatPrice(minor: number | null | undefined): string {
  if (minor === null || minor === undefined) return '—';
  const rupees = Math.trunc(minor / 100);
  const paisa = Math.abs(minor % 100);
  const whole = String(Math.abs(rupees)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const sign = minor < 0 ? '-' : '';
  return `PKR ${sign}${whole}${paisa ? `.${String(paisa).padStart(2, '0')}` : ''}`;
}

/** Short axis label: 1,250,000 minor -> "12.5k". */
export function formatPriceShort(minor: number): string {
  const rupees = minor / 100;
  if (rupees >= 1_000_000) return `${trim(rupees / 1_000_000)}M`;
  if (rupees >= 1_000) return `${trim(rupees / 1_000)}k`;
  return String(Math.round(rupees));
}

function trim(value: number): string {
  return value >= 100 ? String(Math.round(value)) : String(Math.round(value * 10) / 10);
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "16 Nov 2026" in the device's time zone. */
export function formatDate(value: string | number | Date): string {
  const date = new Date(value);
  return `${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

/** "today", "yesterday", "5 days ago", then a date. */
export function formatAgo(value: string | null | undefined, now: Date = new Date()): string {
  if (!value) return 'never';
  const days = Math.floor((now.getTime() - new Date(value).getTime()) / 86_400_000);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days} days ago`;
  return formatDate(value);
}

/** 1234 -> "1,234"; above the cap -> "10,000+". */
export function formatCount(value: number, cap?: number): string {
  const shown = cap !== undefined && value > cap ? cap : value;
  return `${String(shown).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${cap !== undefined && value > cap ? '+' : ''}`;
}

/** "2026-11-16" -> "Today", "Yesterday" or "16 Nov", judged by the device's calendar. */
export function dayLabel(day: string, now: Date = new Date()): string {
  const [year, month, date] = day.split('-').map(Number);
  const target = Date.UTC(year, month - 1, date);
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const diff = Math.round((today - target) / 86_400_000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  return `${date} ${MONTHS[month - 1]}${year === now.getFullYear() ? '' : ` ${year}`}`;
}

/** "6:10 am" in the device's time zone. */
export function formatTime(value: string | number | Date): string {
  const date = new Date(value);
  const hours = date.getHours();
  return `${hours % 12 || 12}:${String(date.getMinutes()).padStart(2, '0')} ${hours < 12 ? 'am' : 'pm'}`;
}

/** A scrape round: "6:10 am – 8:52 am", with the day when it is not one of the shown days. */
export function roundLabel(startedAt: string, endedAt: string, shownDays: string[] = [], now: Date = new Date()): string {
  const start = new Date(startedAt);
  const day = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
  const prefix = shownDays.length === 1 && shownDays[0] === day ? '' : `${dayLabel(day, now)}, `;
  return `${prefix}${formatTime(startedAt)} – ${formatTime(endedAt)}`;
}

/** Percentage change from old to new, rounded; null when it cannot be computed. */
export function percentChange(oldPrice: number | null, newPrice: number | null): number | null {
  if (!oldPrice || newPrice === null || newPrice === undefined) return null;
  return Math.round(((newPrice - oldPrice) / oldPrice) * 100);
}

/** A brand's data is stale when its last good scan is more than 48 hours old. */
export function isStale(lastSuccessAt: string | null, now: Date = new Date()): boolean {
  if (!lastSuccessAt) return true;
  return now.getTime() - new Date(lastSuccessAt).getTime() > 48 * 3_600_000;
}
