'use client';

import { Sun, Moon } from 'lucide-react';
import type { BannerCounts } from '@/lib/types';

export type DotState = 'idle' | 'working' | 'error' | 'done';

const DOT_COLOR: Record<DotState, string> = {
  idle:    '#18E299',
  working: '#F5A623',
  error:   '#E53535',
  done:    '#18E299',
};

const DOT_ANIM: Record<DotState, string> = {
  idle:    'none',
  working: 'logo-dot-blink 1s step-end infinite',
  error:   'logo-dot-blink 0.7s step-end infinite',
  done:    'logo-dot-done 0.5s ease-in-out 3',
};

interface Props {
  dark: boolean;
  onToggleDark: () => void;
  dotState?: DotState;
  // Reading-page extras — all optional; omit on non-reading pages
  banner?: BannerCounts;
  lastUpdated?: string | null;
  databaseCount?: number | null;
}

function formatAge(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch {
    return '—';
  }
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
        color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase',
      }}>
        {label}
      </span>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
        color: 'var(--fg1)', letterSpacing: '0.4px',
      }}>
        {value}
      </span>
    </div>
  );
}

export default function StatusBanner({
  dark,
  onToggleDark,
  dotState = 'idle',
  banner,
  lastUpdated,
  databaseCount,
}: Props) {
  const showStats = !!banner;
  const queueTotal = banner ? banner.queued + banner.reading : 0;

  // Activity label — reading page shows sync age when idle; everywhere shows Working/Error when busy
  let activityLabel = '';
  if (dotState === 'working') activityLabel = 'Working…';
  else if (dotState === 'error') activityLabel = 'Error';
  else if (dotState === 'done' && !lastUpdated) activityLabel = 'Saved';
  else if (lastUpdated) activityLabel = `Synced ${formatAge(lastUpdated)}`;

  return (
    <div style={{
      height: 48,
      background: 'var(--bg-subtle)',
      borderBottom: '1px solid var(--border)',
      padding: '0 24px',
      display: 'flex',
      alignItems: 'center',
      gap: 24,
      flexShrink: 0,
    }}>
      {/* Reading-page stats */}
      {showStats && (
        <>
          <Stat label="Queue" value={queueTotal} />
          <Stat label="Database" value={databaseCount ?? '—'} />
          <Stat label="Done" value={banner!.done} />
        </>
      )}

      <div style={{ flex: 1 }} />

      {/* Dark mode toggle */}
      <button
        onClick={onToggleDark}
        aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          padding: '3px 10px', border: '1px solid var(--border-md)',
          borderRadius: 9999, background: 'transparent',
          cursor: 'pointer', color: 'var(--fg4)',
        }}
      >
        {dark ? <Sun size={12} strokeWidth={2} /> : <Moon size={12} strokeWidth={2} />}
        <span style={{
          fontFamily: 'var(--mono)', fontSize: 10,
          textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--fg4)',
        }}>
          {dark ? 'Light' : 'Dark'}
        </span>
      </button>

      {/* Activity label + status pill */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {activityLabel && (
          <span style={{
            fontFamily: 'var(--mono)', fontSize: 10,
            textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--fg4)',
          }}>
            {activityLabel}
          </span>
        )}
        <div style={{
          height: 24, display: 'inline-flex', alignItems: 'center',
          padding: '0 9px', gap: 6, borderRadius: 9999,
          border: '1.5px solid var(--logo-border)', flexShrink: 0,
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: DOT_COLOR[dotState], flexShrink: 0,
            animation: DOT_ANIM[dotState],
          }} />
          <span style={{
            fontFamily: 'var(--sans)', fontSize: 11.5, fontWeight: 600,
            color: 'var(--fg1)', letterSpacing: '-0.2px', lineHeight: 1,
          }}>
            docent
          </span>
        </div>
      </div>
    </div>
  );
}
