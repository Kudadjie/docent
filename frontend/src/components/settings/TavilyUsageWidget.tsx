'use client';

import { useState, useEffect } from 'react';
import { RefreshCw } from 'lucide-react';

interface TavilyUsage {
  ok: boolean;
  plan?: string | null;
  plan_usage?: number | null;
  plan_limit?: number | null;
  key_search_usage?: number | null;
  pct_used?: number | null;
  message?: string;
}

export default function TavilyUsageWidget({ keyIsSet }: { keyIsSet: boolean }) {
  const [usage, setUsage] = useState<TavilyUsage | null>(null);
  const [fetchKey, setFetchKey] = useState(0);

  useEffect(() => {
    if (!keyIsSet) return;
    let cancelled = false;
    fetch('/api/studio/tavily-usage')
      .then(r => r.json() as Promise<TavilyUsage>)
      .then(d => { if (!cancelled) setUsage(d); })
      .catch(() => { if (!cancelled) setUsage({ ok: false, message: 'Could not reach server.' }); });
    return () => { cancelled = true; };
  }, [keyIsSet, fetchKey]);

  if (!keyIsSet) return null;

  const loading = usage === null;
  const pct = usage?.pct_used ?? null;
  const barColor = pct === null ? 'var(--fg4)' : pct >= 90 ? '#D45656' : pct >= 70 ? '#C97B00' : '#18E299';

  return (
    <div style={{ padding: '10px 0 4px', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg4)' }}>
          Monthly usage
        </span>
        <button
          onClick={() => { setUsage(null); setFetchKey(k => k + 1); }}
          disabled={loading}
          style={{ background: 'none', border: 'none', cursor: loading ? 'default' : 'pointer', padding: 0, display: 'flex', opacity: loading ? 0.5 : 1 }}
          title="Refresh Tavily usage"
        >
          <RefreshCw size={11} strokeWidth={1.5} color="var(--fg4)" style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
        </button>
      </div>
      {loading ? (
        <span style={{ fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg4)' }}>Loading…</span>
      ) : usage?.ok === false ? (
        <span style={{ fontFamily: 'var(--sans)', fontSize: 11.5, color: '#D45656' }}>{usage.message ?? 'Failed to load.'}</span>
      ) : usage ? (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <div style={{ flex: 1, height: 5, borderRadius: 9999, background: 'var(--gray100)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.min(pct ?? 0, 100)}%`, background: barColor, borderRadius: 9999, transition: 'width 0.4s' }} />
            </div>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg3)', flexShrink: 0 }}>
              {usage.plan_usage ?? '?'} / {usage.plan_limit ?? '?'}
            </span>
            {pct !== null && (
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: barColor, flexShrink: 0, fontWeight: 600 }}>
                {pct.toFixed(0)}%
              </span>
            )}
          </div>
          {usage.plan && (
            <span style={{ fontFamily: 'var(--sans)', fontSize: 10.5, color: 'var(--fg4)' }}>
              {usage.plan} plan · resets monthly
            </span>
          )}
        </div>
      ) : null}
    </div>
  );
}
