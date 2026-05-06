'use client';

import Link from 'next/link';
import { LayoutDashboard, BookOpen } from 'lucide-react';

type DotState = 'idle' | 'working' | 'error' | 'done';

const DOT_COLOR: Record<DotState, string> = {
  idle:    '#18E299',
  working: '#F5A623',
  error:   '#E53535',
  done:    '#18E299',
};

const DOT_ANIM: Record<DotState, string> = {
  idle:    'none',
  working: 'logo-dot-blink 1s step-end infinite',
  error:   'logo-dot-blink 0.7s step-end infinite',
  done:    'logo-dot-done 0.5s ease-in-out 3',
};

interface NavItem {
  id: string;
  href: string;
  label: string;
  icon: React.ReactNode;
}

const NAV: NavItem[] = [
  {
    id: 'dashboard',
    href: '/dashboard',
    label: 'Dashboard',
    icon: <LayoutDashboard size={16} strokeWidth={1.5} />,
  },
  {
    id: 'reading',
    href: '/reading',
    label: 'Reading',
    icon: <BookOpen size={16} strokeWidth={1.5} />,
  },
];

interface Props {
  active: string;
  queueCount: number;
  dotState?: DotState;
}

export default function Sidebar({ active, queueCount, dotState = 'idle' }: Props) {
  return (
    <nav
      aria-label="Main navigation"
      style={{
        width: 220,
        flexShrink: 0,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg)',
        borderRight: '1px solid var(--border)',
      }}
    >
      {/* Logo */}
      <div
        style={{
          height: 56,
          display: 'flex',
          alignItems: 'center',
          padding: '0 18px',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div
          style={{
            height: 28,
            display: 'inline-flex',
            alignItems: 'center',
            padding: '0 11px',
            gap: 7,
            borderRadius: 9999,
            border: '1.5px solid var(--logo-border)',
            background: 'var(--bg)',
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: DOT_COLOR[dotState],
              flexShrink: 0,
              animation: DOT_ANIM[dotState],
            }}
          />
          <span
            style={{
              fontFamily: 'var(--sans)',
              fontSize: 13.5,
              fontWeight: 600,
              color: 'var(--fg1)',
              letterSpacing: '-0.2px',
              lineHeight: 1,
            }}
          >
            docent
          </span>
        </div>
      </div>

      {/* Nav items */}
      <div
        style={{
          flex: 1,
          padding: '10px 8px',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        {NAV.map((item) => {
          const isActive = item.id === active;
          return (
            <Link
              key={item.id}
              href={item.href}
              aria-current={isActive ? 'page' : undefined}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 9,
                width: '100%',
                padding: '7px 10px',
                borderRadius: 8,
                border: 'none',
                textDecoration: 'none',
                background: isActive ? 'rgba(24,226,153,0.13)' : 'transparent',
                color: isActive ? '#0fa76e' : 'var(--fg3)',
                fontFamily: 'var(--sans)',
                fontSize: 13,
                fontWeight: isActive ? 500 : 400,
                transition: 'background 0.1s, color 0.1s',
                boxShadow: isActive ? 'rgba(0,0,0,0.04) 0px 1px 3px' : 'none',
              }}
            >
              <span style={{ display: 'flex', color: isActive ? '#0fa76e' : 'var(--fg4)' }}>
                {item.icon}
              </span>
              <span>{item.label}</span>
              {isActive && (
                <span
                  style={{
                    marginLeft: 'auto',
                    fontFamily: 'var(--mono)',
                    fontSize: 9,
                    fontWeight: 500,
                    padding: '1px 6px',
                    borderRadius: 9999,
                    background: 'rgba(24,226,153,0.2)',
                    color: '#0fa76e',
                    textTransform: 'uppercase',
                    letterSpacing: '0.3px',
                  }}
                >
                  {queueCount}
                </span>
              )}
            </Link>
          );
        })}
      </div>

      {/* User footer */}
      <div
        style={{
          padding: '12px 18px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: 'rgba(24,226,153,0.15)',
            color: '#0fa76e',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: 'var(--sans)',
            fontWeight: 600,
            fontSize: 12,
            flexShrink: 0,
          }}
        >
          J
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontFamily: 'var(--sans)',
              fontWeight: 500,
              fontSize: 12,
              color: 'var(--fg1)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            John
          </div>
          <div
            style={{
              fontFamily: 'var(--sans)',
              fontWeight: 400,
              fontSize: 11,
              color: 'var(--fg4)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            Graduate student
          </div>
        </div>
      </div>
    </nav>
  );
}
