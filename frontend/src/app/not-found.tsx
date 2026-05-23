import Link from 'next/link';

export default function NotFound() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg)',
        padding: 24,
      }}
    >
      <div style={{ textAlign: 'center', maxWidth: 400 }}>
        {/* Big number */}
        <div
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 96,
            fontWeight: 600,
            color: 'var(--border-md)',
            lineHeight: 1,
            letterSpacing: '-4px',
            userSelect: 'none',
          }}
        >
          404
        </div>

        {/* Icon row */}
        <div
          style={{
            margin: '24px auto 0',
            width: 48,
            height: 48,
            borderRadius: 12,
            background: 'var(--bg-card)',
            border: '1px solid var(--border-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {/* Open book SVG — no external dependency */}
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--fg4)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
          </svg>
        </div>

        <h1
          style={{
            fontFamily: 'var(--sans)',
            fontSize: 18,
            fontWeight: 600,
            color: 'var(--fg1)',
            margin: '20px 0 8px',
          }}
        >
          Page not found
        </h1>
        <p
          style={{
            fontFamily: 'var(--sans)',
            fontSize: 13,
            color: 'var(--fg3)',
            lineHeight: 1.6,
            margin: '0 0 28px',
          }}
        >
          That chapter doesn&apos;t exist in Docent. Maybe it was moved, or the link is wrong.
        </p>

        <Link
          href="/dashboard"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontFamily: 'var(--sans)',
            fontSize: 13,
            fontWeight: 600,
            color: '#fff',
            background: '#0fa76e',
            border: 'none',
            borderRadius: 9999,
            padding: '8px 20px',
            textDecoration: 'none',
            cursor: 'pointer',
          }}
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
