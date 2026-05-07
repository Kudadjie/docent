'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { LayoutDashboard, BookOpen, BookText, Settings } from 'lucide-react';
import WelcomeModal, { type UserProfile } from './WelcomeModal';

interface NavItem {
  id: string;
  href: string;
  label: string;
  icon: React.ReactNode;
}

const PLUGIN_NAV: NavItem[] = [
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

const UTILITY_NAV: NavItem[] = [
  {
    id: 'docs',
    href: '/docs',
    label: 'Docs',
    icon: <BookText size={15} strokeWidth={1.5} />,
  },
  {
    id: 'settings',
    href: '/settings',
    label: 'Settings',
    icon: <Settings size={15} strokeWidth={1.5} />,
  },
];

interface Props {
  active: string;
  queueCount: number;
  dark?: boolean; // if passed, overrides localStorage; if omitted, Sidebar reads localStorage itself
}

export default function Sidebar({ active, queueCount, dark: darkProp }: Props) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [showWelcome, setShowWelcome] = useState(false);
  const [localDark, setLocalDark] = useState(false);

  useEffect(() => {
    if (darkProp === undefined) {
      setLocalDark(localStorage.getItem('docent:dark') === 'true');
    }
  }, [darkProp]);

  const dark = darkProp !== undefined ? darkProp : localDark;

  useEffect(() => {
    fetch('/api/user')
      .then(r => r.json())
      .then((data: UserProfile) => {
        setUser(data);
        if (!data.name) setShowWelcome(true);
      })
      .catch(() => {});
  }, []);

  async function handleWelcomeComplete(profile: UserProfile) {
    setShowWelcome(false);
    setUser(profile);
    try {
      await fetch('/api/user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
    } catch { /* ignore */ }
  }

  const profileSet = !!user?.name;
  const displayName = user?.name || 'You';
  const displayRole = user?.level && user?.program
    ? `${user.level} · ${user.program}`
    : user?.level || user?.program || 'Graduate student';
  const initial = displayName[0].toUpperCase();

  return (
    <>
      {showWelcome && <WelcomeModal onComplete={handleWelcomeComplete} />}

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

        {/* Plugin nav items */}
        <div
          style={{
            flex: 1,
            padding: '10px 8px',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          {PLUGIN_NAV.map((item) => {
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
                {item.id === 'reading' && isActive && (
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

        {/* Utility nav (Docs + Settings) — pinned above user footer */}
        <div
          style={{
            padding: '8px 8px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            gap: 1,
          }}
        >
          {UTILITY_NAV.map((item) => {
            const isActive = item.id === active;
            return (
              <Link
                key={item.id}
                href={item.href}
                aria-current={isActive ? 'page' : undefined}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: 'none',
                  textDecoration: 'none',
                  background: 'transparent',
                  color: isActive ? 'var(--fg1)' : 'var(--fg4)',
                  fontFamily: 'var(--sans)',
                  fontSize: 12,
                  fontWeight: isActive ? 500 : 400,
                  transition: 'color 0.1s',
                }}
              >
                <span style={{ display: 'flex', color: isActive ? 'var(--fg2)' : 'var(--fg4)' }}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>

        {/* User footer */}
        {profileSet ? (
          <button
            onClick={() => setShowWelcome(true)}
            title="Edit profile"
            style={{
              width: '100%',
              padding: '12px 18px',
              borderTop: '1px solid var(--border)',
              borderLeft: 'none', borderRight: 'none', borderBottom: 'none',
              background: 'transparent',
              display: 'flex', alignItems: 'center', gap: 8,
              cursor: 'pointer', textAlign: 'left',
            }}
          >
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: 'rgba(24,226,153,0.15)', color: '#0fa76e',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--sans)', fontWeight: 600, fontSize: 12, flexShrink: 0,
            }}>
              {initial}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{
                fontFamily: 'var(--sans)', fontWeight: 500, fontSize: 12,
                color: 'var(--fg1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {displayName}
              </div>
              <div style={{
                fontFamily: 'var(--sans)', fontWeight: 400, fontSize: 11,
                color: 'var(--fg4)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {displayRole}
              </div>
            </div>
          </button>
        ) : (
          <button
            onClick={() => setShowWelcome(true)}
            style={{
              width: '100%',
              padding: '12px 18px',
              borderTop: '1px solid var(--border)',
              borderLeft: 'none', borderRight: 'none', borderBottom: 'none',
              background: 'transparent',
              display: 'flex', alignItems: 'center', gap: 8,
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: 'var(--gray100)', color: 'var(--fg4)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--sans)', fontWeight: 600, fontSize: 14, flexShrink: 0,
            }}>
              ?
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{
                fontFamily: 'var(--sans)', fontWeight: 500, fontSize: 12, color: '#0fa76e',
              }}>
                Set up your profile
              </div>
              <div style={{
                fontFamily: 'var(--sans)', fontWeight: 400, fontSize: 11, color: 'var(--fg4)',
              }}>
                Name, program, level
              </div>
            </div>
          </button>
        )}
      </nav>
    </>
  );
}
