import type { ComponentType } from 'react';

export interface DashboardStat {
  label: string;
  value: number | string;
  color?: string;   // hex; omit for primary fg
  dim?: boolean;    // muted/grey treatment
}

export interface DashboardPlugin {
  id: string;
  Card: ComponentType<{ dark: boolean; onStats: (stats: DashboardStat[]) => void }>;
}

// Import lazily to avoid circular deps — the page imports from here,
// the cards import from lib. Keep this file dep-free of React components.
// Re-export only after all cards are defined; the page does the real import.
