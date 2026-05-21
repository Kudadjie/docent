'use client';

import { useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Sparkles, Cpu, Upload } from 'lucide-react';
import { dashTokens, MONO, SANS } from './_tokens';
import { CardShell } from './_primitives';

const ACTIONS = [
  { id: 'queue',   label: 'Add to queue',     key: 'A', Icon: Plus     },
  { id: 'studio',  label: 'New studio run',   key: 'S', Icon: Sparkles },
  { id: 'feynman', label: 'Feynman research', key: 'F', Icon: Cpu      },
  { id: 'backup',  label: 'Backup now',       key: 'B', Icon: Upload   },
] as const;

type ActionId = typeof ACTIONS[number]['id'];

export default function QuickActions({ dark }: { dark: boolean }) {
  const D = dashTokens(dark);
  const router = useRouter();

  const handleAction = useCallback((id: ActionId) => {
    if (id === 'queue')   router.push('/reading');
    if (id === 'studio')  router.push('/studio');
    if (id === 'feynman') router.push('/studio');
    if (id === 'backup')  router.push('/settings');
  }, [router]);

  // Keyboard shortcuts — active only while this page is mounted
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;
      if (document.activeElement && document.activeElement !== document.body) return;
      const action = ACTIONS.find(a => a.key === e.key.toUpperCase());
      if (action) { e.preventDefault(); handleAction(action.id); }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [handleAction]);

  return (
    <CardShell dark={dark}>
      {/* Header */}
      <div style={{
        padding: '12px 18px',
        borderBottom: `1px solid ${D.divider}`,
      }}>
        <span style={{
          fontFamily: MONO, fontSize: 9, fontWeight: 500,
          color: D.sectionLabel, letterSpacing: '0.85px', textTransform: 'uppercase',
        }}>
          Quick Actions
        </span>
      </div>

      {/* Action rows */}
      <div style={{ padding: '6px 0' }}>
        {ACTIONS.map(({ id, label, key, Icon }) => (
          <button
            key={id}
            className="qa-row"
            onClick={() => handleAction(id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 12,
              width: '100%', padding: '11px 18px',
              background: 'transparent', border: 'none', cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            {/* Icon slot */}
            <span style={{ width: 22, display: 'flex', alignItems: 'center', color: D.sectionLabel }}>
              <Icon size={15} strokeWidth={1.5} />
            </span>

            {/* Label */}
            <span style={{ flex: 1, fontSize: 13, color: dark ? '#ededed' : '#0d0d0d' }}>
              {label}
            </span>

            {/* Key chip */}
            <span style={{
              fontFamily: MONO, fontSize: 10, fontWeight: 500,
              color: dark ? '#a0a0a0' : '#57606a',
              background: dark ? '#1e1e1e' : '#eaeef2',
              border: `1px solid ${dark ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.13)'}`,
              borderRadius: 4,
              minWidth: 22, height: 20,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              padding: '0 5px',
            }}>
              {key}
            </span>
          </button>
        ))}
      </div>
    </CardShell>
  );
}
