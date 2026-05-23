export const TOUR_KEYS = ['dashboard', 'reading', 'studio', 'settings', 'docs', 'ecosystem'] as const;
export type TourKey = typeof TOUR_KEYS[number];

export const TOUR_LABELS: Record<TourKey, string> = {
  dashboard:  'Dashboard',
  reading:    'Reading queue',
  studio:     'Studio',
  settings:   'Settings',
  docs:       'Docs',
  ecosystem:  'Ecosystem',
};

const lsKey = (key: TourKey) => `docent:tour:${key}`;

export function tourHasSeen(key: TourKey): boolean {
  try { return localStorage.getItem(lsKey(key)) === 'seen'; } catch { return false; }
}

export function tourMarkSeen(key: TourKey): void {
  try { localStorage.setItem(lsKey(key), 'seen'); } catch { /* storage unavailable */ }
}

export function tourReset(key: TourKey): void {
  try { localStorage.removeItem(lsKey(key)); } catch { /* storage unavailable */ }
}

export function tourResetAll(): void {
  TOUR_KEYS.forEach(tourReset);
}
