'use client';

/**
 * AppRunProvider — generic layout-level context for cross-page background
 * activity indicators (Sidebar pill, StatusBanner dot).
 *
 * Any feature that runs something in the background (Studio, Reading sync,
 * future Export page, …) calls `setActivity(id, info)` to register itself.
 * Passing null clears the entry. The global status indicators read from this
 * context — they have no knowledge of per-feature internals.
 *
 * Usage from a feature provider:
 *
 *   const { setActivity } = useAppRun();
 *   useEffect(() => {
 *     setActivity('studio', { label: 'Studio', phase: currentPhase, status: 'running' });
 *     return () => setActivity('studio', null);
 *   }, [status, currentPhase]);
 *
 * Usage from a status indicator:
 *
 *   const { activities } = useAppRun();
 *   const anyRunning = Object.values(activities).some(a => a?.status === 'running');
 */

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react';

// ── Activity record ────────────────────────────────────────────────────────────

export interface AppActivity {
  /** Human-readable name shown in status indicators, e.g. "Studio" or "Reading sync". */
  label: string;
  /**
   * Optional sub-phase label shown in the Sidebar pill, e.g. "synth".
   * The Sidebar truncates this to 7 chars so keep it short.
   */
  phase?: string;
  status: 'running' | 'success' | 'failure' | 'stopped';
}

// ── Context value ─────────────────────────────────────────────────────────────

export interface AppRunContextValue {
  /**
   * All registered activities, keyed by stable feature ID (e.g. 'studio', 'reading-sync').
   * A null value means the feature finished and explicitly cleared its slot.
   * An absent key means the feature never ran this session.
   */
  activities: Record<string, AppActivity | null>;

  /**
   * Register or update an activity.
   * - Pass an AppActivity to create/update.
   * - Pass null to clear (hides the indicator).
   */
  setActivity: (id: string, info: AppActivity | null) => void;
}

// ── Context + hook ────────────────────────────────────────────────────────────

const AppRunContext = createContext<AppRunContextValue | null>(null);

export function useAppRun(): AppRunContextValue {
  const ctx = useContext(AppRunContext);
  if (!ctx) throw new Error('useAppRun must be called inside <AppRunProvider>');
  return ctx;
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function AppRunProvider({ children }: { children: ReactNode }) {
  const [activities, setActivities] = useState<Record<string, AppActivity | null>>({});

  const setActivity = useCallback((id: string, info: AppActivity | null) => {
    setActivities(prev => ({ ...prev, [id]: info }));
  }, []);

  return (
    <AppRunContext.Provider value={{ activities, setActivity }}>
      {children}
    </AppRunContext.Provider>
  );
}
