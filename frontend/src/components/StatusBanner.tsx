'use client';

import { Sun, Moon } from 'lucide-react';
import type { BannerCounts } from '@/lib/types';

interface Props {
  banner: BannerCounts;
  lastUpdated: string | null;
  databaseCount: number | null;
  dark: boolean;
  onToggleDark: () => void;
}

function formatAge(iso: string | null): string {
  if (!iso) return 'never';
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
      <span
        style={{
          fontFamily: 'var(--mono)',
          fontSize: 10,
          fontWeight: 500,
          color: 'var(--fg4)',
          letterSpacing: '0.7px',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: 'var(--mono)',
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--fg1)',
          letterSpacing: '0.4px',
        }}
      >
        {value}
      </span>
    </div>
  );
}

export default function StatusBanner({
  banner,
  lastUpdated,
  databaseCount,
  dark,
  onToggleDark,
}: Props) {
  const queueTotal = banner.queued + banner.reading;
  const age = formatAge(lastUpdated);

  return (
    <div
      style={{
        height: 40,
        background: 'var(--bg-subtle)',
        borderBottom: '1px solid var(--border)',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        gap: 24,
        flexShrink: 0,
      }}
    >
      <Stat label="Queue" value={queueTotal} />
      <Stat label="Database" value={databaseCount ?? '—'} />
      <Stat label="Done" value={banner.done} />

      <div style={{ flex: 1 }} />

      {/* Dark mode toggle */}
      <button
        onClick={onToggleDark}
        aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          padding: '3px 10px',
          border: '1px solid var(--border-md)',
          borderRadius: 9999,
          background: 'transparent',
          cursor: 'pointer',
          color: 'var(--fg4)',
        }}
      >
        {dark ? <Sun size={12} strokeWidth={2} /> : <Moon size={12} strokeWidth={2} />}
        <span
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 10,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            color: 'var(--fg4)',
          }}
        >
          {dark ? 'Light' : 'Dark'}
        </span>
      </button>

      {/* Synced indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: '#18E299',
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 10,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            color: 'var(--fg4)',
          }}
        >
          Synced {age}
        </span>
      </div>
    </div>
  );
}
