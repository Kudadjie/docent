'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

const CHANNEL = 'docent-ui-session';

export default function TabGuard() {
  const [isDuplicate, setIsDuplicate] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return;

    const channel = new BroadcastChannel(CHANNEL);

    channel.onmessage = (e: MessageEvent<{ type: string }>) => {
      if (e.data?.type === 'tab-open') {
        // An existing tab replies to tell the newcomer it's already there
        channel.postMessage({ type: 'tab-exists' });
      }
      if (e.data?.type === 'tab-exists') {
        // We're the duplicate
        setIsDuplicate(true);
      }
    };

    // Announce ourselves — any existing tab will reply with 'tab-exists'
    channel.postMessage({ type: 'tab-open' });

    return () => channel.close();
  }, []);

  if (!isDuplicate || dismissed) return null;

  return (
    <div
      role="alert"
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999,
        background: '#B45309',
        padding: '9px 20px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}
    >
      <AlertTriangle size={14} strokeWidth={2} color="#fff" style={{ flexShrink: 0 }} />
      <span style={{
        flex: 1, fontFamily: 'var(--sans)', fontSize: 13,
        fontWeight: 500, color: '#fff', lineHeight: 1.4,
      }}>
        Another Docent tab is already open. Running multiple tabs simultaneously may cause unexpected behaviour.
      </span>
      <button
        onClick={() => window.close()}
        style={{
          fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
          color: '#fff', background: 'rgba(0,0,0,0.25)',
          border: '1px solid rgba(255,255,255,0.35)',
          borderRadius: 6, padding: '4px 12px', cursor: 'pointer', whiteSpace: 'nowrap',
        }}
      >
        Close this tab
      </button>
      <button
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.75)', display: 'flex', padding: 2 }}
      >
        <X size={14} strokeWidth={2} />
      </button>
    </div>
  );
}
