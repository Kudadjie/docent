'use client';

import { useEffect, useState } from 'react';
import { Sparkles, X } from 'lucide-react';

interface Release {
  version: string;
  date: string | null;
  highlights: string[];
}

interface WhatsNewPayload {
  version: string;
  release: Release | null;
  new: boolean;
}

/**
 * Dismissible "What's New" toast, shown once on first load after a version
 * change. Reads /api/whatsnew (server-side state, single source of truth =
 * CHANGELOG.md) and POSTs /api/whatsnew/seen on dismiss so it stays quiet until
 * the next update.
 */
export default function WhatsNewToast() {
  const [release, setRelease] = useState<Release | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/whatsnew')
      .then((r) => r.json())
      .then((data: WhatsNewPayload) => {
        if (cancelled) return;
        if (data.new && data.release && data.release.highlights.length > 0) {
          setRelease(data.release);
          setVisible(true);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  function dismiss() {
    setVisible(false);
    fetch('/api/whatsnew/seen', { method: 'POST' }).catch(() => {});
  }

  if (!visible || !release) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: '14px 16px',
        borderRadius: 12,
        border: '1px solid rgba(24,226,153,0.25)',
        background: 'rgba(24,226,153,0.08)',
        backdropFilter: 'blur(8px)',
        boxShadow: '0 4px 16px rgba(0,0,0,0.14)',
        maxWidth: 380,
        animation: 'fadeInUp 0.18s ease forwards',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: '#0fa76e', display: 'flex', flexShrink: 0 }}>
          <Sparkles size={15} strokeWidth={1.8} />
        </span>
        <span
          style={{
            fontFamily: 'var(--sans)',
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--fg1)',
            flex: 1,
          }}
        >
          What&apos;s New in v{release.version}
        </span>
        <button
          onClick={dismiss}
          aria-label="Dismiss"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--fg4)',
            display: 'flex',
            padding: 0,
            flexShrink: 0,
          }}
        >
          <X size={13} strokeWidth={2} />
        </button>
      </div>
      <ul
        style={{
          margin: 0,
          paddingLeft: 18,
          fontFamily: 'var(--sans)',
          fontSize: 12.5,
          fontWeight: 400,
          color: 'var(--fg2)',
          lineHeight: 1.55,
        }}
      >
        {release.highlights.slice(0, 4).map((h, i) => (
          <li key={i}>{h}</li>
        ))}
      </ul>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={dismiss}
          style={{
            fontFamily: 'var(--sans)',
            fontSize: 12,
            fontWeight: 500,
            color: '#0fa76e',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '2px 4px',
          }}
        >
          Got it
        </button>
      </div>
    </div>
  );
}
