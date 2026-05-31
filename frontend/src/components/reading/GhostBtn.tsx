'use client';

import { useState } from 'react';
import type { ReactNode } from 'react';

export default function GhostBtn({
  icon,
  children,
  onClick,
  active,
}: {
  icon?: ReactNode;
  children: ReactNode;
  onClick?: () => void;
  active?: boolean;
}) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '5px 12px',
        borderRadius: 9999,
        border: active ? '1px solid #18E299' : '1px solid var(--border-md)',
        background: active ? 'rgba(24,226,153,0.1)' : hov ? 'var(--gray100)' : 'transparent',
        color: active ? '#0fa76e' : 'var(--fg2)',
        fontFamily: 'var(--sans)',
        fontSize: 13,
        fontWeight: 500,
        cursor: 'pointer',
        transition: 'background 0.12s',
        whiteSpace: 'nowrap',
      }}
    >
      {icon && (
        <span style={{ color: active ? '#0fa76e' : 'var(--fg4)', display: 'flex' }}>{icon}</span>
      )}
      {children}
    </button>
  );
}
