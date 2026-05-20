'use client';

import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

const CHANNEL = 'docent-ui-session';
const HEARTBEAT_MS = 3_000;  // ping every 3 s
const EXPIRE_MS    = 9_000;  // gone if no ping for 9 s (3 missed beats)

export default function TabGuard() {
  const [isDuplicate, setIsDuplicate] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  // Stable ID for this tab instance across re-renders
  const myId   = useRef(Math.random().toString(36).slice(2));
  // otherId → last-seen timestamp
  const seenAt = useRef<Record<string, number>>({});

  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return;

    const id      = myId.current;
    const channel = new BroadcastChannel(CHANNEL);

    /** Remove stale entries and update duplicate state. */
    function reckon() {
      const now = Date.now();
      for (const [oid, t] of Object.entries(seenAt.current)) {
        if (now - t > EXPIRE_MS) delete seenAt.current[oid];
      }
      setIsDuplicate(Object.keys(seenAt.current).length > 0);
    }

    channel.onmessage = (e: MessageEvent<{ type: string; tabId: string }>) => {
      const { type, tabId: senderId } = e.data ?? {};
      if (!senderId || senderId === id) return;

      if (type === 'tab-open') {
        // A new tab announced itself — reply so it knows we exist
        channel.postMessage({ type: 'tab-exists', tabId: id });
        seenAt.current[senderId] = Date.now();
      } else if (type === 'tab-exists' || type === 'heartbeat') {
        seenAt.current[senderId] = Date.now();
      } else if (type === 'tab-close') {
        delete seenAt.current[senderId];
      }
      reckon();
    };

    // Announce arrival — existing tabs will reply with tab-exists
    channel.postMessage({ type: 'tab-open', tabId: id });

    // Keep broadcasting so other tabs know we're still here
    const heartbeatTimer = setInterval(() => {
      channel.postMessage({ type: 'heartbeat', tabId: id });
    }, HEARTBEAT_MS);

    // Periodically evict tabs that have gone silent
    const expiryTimer = setInterval(reckon, HEARTBEAT_MS);

    // Signal clean departure on page unload
    function onUnload() {
      channel.postMessage({ type: 'tab-close', tabId: id });
    }
    window.addEventListener('beforeunload', onUnload);

    return () => {
      onUnload();
      channel.close();
      clearInterval(heartbeatTimer);
      clearInterval(expiryTimer);
      window.removeEventListener('beforeunload', onUnload);
    };
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
