// Three-state filter chips: tap once to show only this, again to hide it, again to clear.
// Pure: no React or React Native imports, so it runs under `node --test`.

export type TriState = 'off' | 'include' | 'exclude';

export type TriLists<T> = { include: T[]; exclude: T[] };

export function stateOf<T>(lists: TriLists<T>, key: T): TriState {
  if (lists.include.includes(key)) return 'include';
  if (lists.exclude.includes(key)) return 'exclude';
  return 'off';
}

/** off -> include -> exclude -> off. A key is never in both lists. */
export function cycle<T>(lists: TriLists<T>, key: T): TriLists<T> {
  const include = lists.include.filter((item) => item !== key);
  const exclude = lists.exclude.filter((item) => item !== key);
  const state = stateOf(lists, key);
  if (state === 'off') include.push(key);
  else if (state === 'include') exclude.push(key);
  return { include, exclude };
}

/** Whether an item passes the include and exclude lists (an empty include list allows everything). */
export function passes<T>(lists: TriLists<T>, key: T): boolean {
  return (lists.include.length === 0 || lists.include.includes(key)) && !lists.exclude.includes(key);
}
