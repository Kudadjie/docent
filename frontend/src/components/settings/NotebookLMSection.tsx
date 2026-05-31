'use client';

import { useState, useEffect } from 'react';
import { BookOpen, RefreshCw } from 'lucide-react';

interface NlmStatus {
  installed: boolean;
  playwright_ok: boolean;
  authenticated: boolean;
  fix?: string;
}

export default function NotebookLMSection() {
  const [nlmStatus, setNlmStatus] = useState<NlmStatus | null>(null);
  const [nlmChecking, setNlmChecking] = useState(false);

  async function checkNlmStatus() {
    setNlmChecking(true);
    try {
      const r = await fetch('/api/notebooklm/auth-status');
      const j = await r.json() as NlmStatus;
      setNlmStatus(j);
    } catch {
      setNlmStatus({ installed: false, playwright_ok: false, authenticated: false });
    } finally {
      setNlmChecking(false);
    }
  }

  useEffect(() => { checkNlmStatus(); }, []); // eslint-disable-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect

  const nlmDot = nlmStatus === null ? '#999'
    : !nlmStatus.installed ? '#C97B00'
    : !nlmStatus.playwright_ok ? '#C97B00'
    : nlmStatus.authenticated ? '#18E299' : '#D45656';

  const nlmLabel = nlmStatus === null ? 'Checking…'
    : !nlmStatus.installed ? 'Not installed'
    : !nlmStatus.playwright_ok ? 'Playwright browser missing'
    : nlmStatus.authenticated ? 'Authenticated' : 'Not authenticated';

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <BookOpen size={13} strokeWidth={1.5} color="#0ea5e9" />
        <h2 style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', margin: 0 }}>NotebookLM</h2>
      </div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: nlmDot, flexShrink: 0 }} />
            <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)' }}>
              {nlmLabel}
            </span>
          </div>
          <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.55 }}>
            {!nlmStatus?.installed ? (
              <>Not installed. Install with: <code style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)' }}>pip install notebooklm</code></>
            ) : !nlmStatus.playwright_ok ? (
              <>
                Playwright&apos;s Chromium browser is not downloaded — required for the login flow.
                Run:{' '}
                <code style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)' }}>
                  {nlmStatus.fix ?? 'playwright install chromium'}
                </code>
                {' '}then click <strong style={{ color: 'var(--fg2)', fontWeight: 500 }}>Refresh status</strong>.
                This may need repeating after <code style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>notebooklm</code> updates.
              </>
            ) : (
              <>
                Required for the <em>to-notebook</em> action. When your session expires, a browser
                window opens automatically during the run so you can re-authenticate without stopping
                anything.
              </>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end', flexShrink: 0 }}>
          <button
            onClick={checkNlmStatus}
            disabled={nlmChecking}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '5px 12px', borderRadius: 7,
              border: '1px solid var(--border-md)',
              background: 'transparent', color: 'var(--fg3)',
              fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
              cursor: nlmChecking ? 'default' : 'pointer',
              opacity: nlmChecking ? 0.6 : 1,
              whiteSpace: 'nowrap',
            }}
          >
            <RefreshCw size={12} strokeWidth={1.5} style={{ animation: nlmChecking ? 'spin 1s linear infinite' : 'none' }} />
            {nlmChecking ? 'Checking…' : 'Refresh status'}
          </button>
        </div>
      </div>
    </div>
  );
}
