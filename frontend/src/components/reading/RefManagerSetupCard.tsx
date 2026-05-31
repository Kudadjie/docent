'use client';

type Props = {
  onChoose: (rm: 'mendeley' | 'zotero') => void;
  busy: boolean;
};

const OPTIONS = [
  {
    key: 'mendeley' as const,
    label: 'Mendeley',
    detail: 'Connects via mendeley-mcp. Requires a Mendeley API client and one-time OAuth login.',
  },
  {
    key: 'zotero' as const,
    label: 'Zotero',
    detail: 'Connects via the Zotero Web API. Requires an API key — no browser login needed.',
  },
];

export default function RefManagerSetupCard({ onChoose, busy }: Props) {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 40,
      background: 'var(--bg-card)',
    }}>
      <div style={{
        maxWidth: 480,
        width: '100%',
        textAlign: 'center',
      }}>
        {/* Icon */}
        <div style={{
          width: 48,
          height: 48,
          borderRadius: 14,
          background: 'rgba(24,226,153,0.1)',
          border: '1px solid rgba(24,226,153,0.25)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 20px',
        }}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#18E299" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
        </div>

        {/* Heading */}
        <h2 style={{
          fontFamily: 'var(--sans)',
          fontSize: 16,
          fontWeight: 600,
          color: 'var(--fg1)',
          margin: '0 0 8px',
        }}>
          Choose your reference manager
        </h2>
        <p style={{
          fontFamily: 'var(--sans)',
          fontSize: 13,
          color: 'var(--fg3)',
          lineHeight: 1.6,
          margin: '0 0 28px',
        }}>
          Docent syncs your reading queue from a named collection in your reference manager.
          Pick one to get started — you can switch anytime in Settings.
        </p>

        {/* Choice buttons */}
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          {OPTIONS.map(({ key, label, detail }) => (
            <button
              key={key}
              disabled={busy}
              onClick={() => onChoose(key)}
              style={{
                flex: 1,
                maxWidth: 200,
                padding: '16px 14px',
                background: 'var(--bg)',
                border: '1.5px solid var(--border)',
                borderRadius: 10,
                cursor: busy ? 'not-allowed' : 'pointer',
                textAlign: 'left',
                transition: 'border-color 0.15s, background 0.15s',
                opacity: busy ? 0.6 : 1,
              }}
              onMouseEnter={e => {
                if (!busy) {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = '#18E299';
                  (e.currentTarget as HTMLButtonElement).style.background = 'rgba(24,226,153,0.04)';
                }
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border)';
                (e.currentTarget as HTMLButtonElement).style.background = 'var(--bg)';
              }}
            >
              <div style={{
                fontFamily: 'var(--sans)',
                fontSize: 14,
                fontWeight: 600,
                color: 'var(--fg1)',
                marginBottom: 6,
              }}>
                {label}
              </div>
              <div style={{
                fontFamily: 'var(--sans)',
                fontSize: 11,
                color: 'var(--fg4)',
                lineHeight: 1.5,
              }}>
                {detail}
              </div>
            </button>
          ))}
        </div>

        {/* Footer hint */}
        <p style={{
          fontFamily: 'var(--sans)',
          fontSize: 12,
          color: 'var(--fg4)',
          margin: '20px 0 0',
        }}>
          Need help? See the{' '}
          <a href="/docs" style={{ color: 'var(--accent, #18E299)', textDecoration: 'underline' }}>
            Reading Queue guide
          </a>
          {' '}for setup instructions.
        </p>
      </div>
    </div>
  );
}
