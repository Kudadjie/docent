'use client';

import Image from 'next/image';
import Link from 'next/link';
import { LayoutDashboard, BookOpen } from 'lucide-react';

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
  dark?: boolean;
}

export default function Sidebar({ active, queueCount, dark = false }: Props) {
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
        <Image
          src={dark ? '/logo-dark.svg' : '/logo.svg'}
          alt="docent"
          height={24}
          width={96}
          style={{ display: 'block' }}
          priority
        />
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
