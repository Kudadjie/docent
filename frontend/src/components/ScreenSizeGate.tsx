'use client';

import { useState, useEffect } from 'react';
import { Monitor } from 'lucide-react';

type ScreenClass = 'optimal' | 'tablet' | 'mobile';

function classifyScreen(w: number): ScreenClass {
  if (w < 768) return 'mobile';
  if (w < 1100) return 'tablet';
  return 'optimal';
}

export default function ScreenSizeGate() {
  const [cls, setCls] = useState<ScreenClass>('optimal');
  const [dismissed, setDismissed] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const update = () => setCls(classifyScreen(window.innerWidth));
    queueMicrotask(() => {
      setMounted(true);
      update();
    });
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  if (!mounted || cls === 'optimal') return null;

  // Mobile — full blocking overlay
  if (cls === 'mobile') {
    return (
      <div style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'var(--bg)',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        padding: 32, textAlign: 'center',
      }}>
        <Monitor size={40} strokeWidth={1} color="#0fa76e" style={{ marginBottom: 20 }} />
        <h2 style={{
          fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 600,
          color: 'var(--fg1)', margin: '0 0 10px', letterSpacing: '-0.3px',
        }}>
          Docent is designed for laptop & desktop
        </h2>
        <p style={{
          fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)',
          maxWidth: 320, lineHeight: 1.6, margin: 0,
        }}>
          Please open Docent on a laptop or desktop computer for the best experience.
        </p>
      </div>
    );
  }

  // Tablet — dismissible banner
  if (dismissed) return null;
  return (
    <div style={{
      position: 'fixed', bottom: 16, right: 16, zIndex: 9000,
      background: 'var(--bg-card)',
      border: '1px solid var(--border-md)',
      borderRadius: 10,
      boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
      padding: '12px 16px',
      maxWidth: 320,
      display: 'flex', alignItems: 'flex-start', gap: 10,
    }}>
      <Monitor size={16} strokeWidth={1.5} color="#C97B00" style={{ flexShrink: 0, marginTop: 1 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500, color: 'var(--fg1)', marginBottom: 2 }}>
          Small screen detected
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg3)', lineHeight: 1.5 }}>
          Docent is optimised for laptop and desktop screens. Some elements may not display correctly here.
        </div>
      </div>
      <button
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        style={{
          background: 'transparent', border: 'none',
          cursor: 'pointer', color: 'var(--fg4)',
          fontFamily: 'var(--sans)', fontSize: 18,
          lineHeight: 1, padding: '0 2px', flexShrink: 0,
        }}
      >
        ×
      </button>
    </div>
  );
}
