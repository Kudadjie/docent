'use client';

import { useState, useEffect } from 'react';
import { Zap } from 'lucide-react';

export default function OpenCodeSection() {
  const [running, setRunning] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/opencode/status')
      .then(r => r.json())
      .then((j: { running: boolean }) => setRunning(j.running))
      .catch(() => setRunning(false));
  }, []);

  async function toggle() {
    setBusy(true); setMsg(null);
    try {
      const url = running ? '/api/opencode/stop' : '/api/opencode/start';
      const r = await fetch(url, { method: 'POST' });
      const j = await r.json() as { ok?: boolean; status?: string; error?: string };
      if (!j.ok && j.error) { setMsg(j.error); return; }
      setRunning(j.status !== 'stopped');
      setMsg(j.status === 'already_running' ? 'Already running.' : j.status === 'started' ? 'Server started on :4096.' : 'Server stopped.');
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  const dotColor = running === true ? '#18E299' : running === false ? '#D45656' : '#999';

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Zap size={13} strokeWidth={1.5} color="#6366f1" />
        <h2 style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', margin: 0 }}>OpenCode server</h2>
      </div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: dotColor, flexShrink: 0, animation: running === true ? 'logo-dot-blink 2s step-end infinite' : 'none' }} />
            <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)' }}>
              {running === null ? 'Checking…' : running ? 'Running on :4096' : 'Stopped'}
            </span>
          </div>
          <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.55 }}>
            Required for the Docent research backend. Uses your configured LLM API key.
          </div>
          {msg && <div style={{ marginTop: 6, fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg4)' }}>{msg}</div>}
        </div>
        <button onClick={toggle} disabled={busy || running === null}
          style={{ padding: '7px 16px', borderRadius: 8, border: '1px solid var(--border-md)', background: running ? 'rgba(212,86,86,0.08)' : 'rgba(99,102,241,0.08)', color: running ? '#D45656' : '#6366f1', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600, cursor: busy ? 'wait' : 'pointer', opacity: (busy || running === null) ? 0.6 : 1 }}>
          {busy ? 'Working…' : running ? 'Stop server' : 'Start server'}
        </button>
      </div>
    </div>
  );
}
