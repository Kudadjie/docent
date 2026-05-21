'use client';

import { useState, useEffect, useRef } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { LayoutDashboard, BookOpen, FlaskConical, BookText, Settings, Globe2, GripVertical } from 'lucide-react';
import WelcomeModal, { type UserProfile } from './WelcomeModal';

const NAV_ORDER_KEY  = 'docent:nav-order';
const USER_CACHE_KEY = 'docent:user-profile';

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
  {
    id: 'studio',
    href: '/studio',
    label: 'Studio',
    icon: <FlaskConical size={16} strokeWidth={1.5} />,
  },
];

const UTILITY_NAV: NavItem[] = [
  {
    id: 'ecosystem',
    href: '/ecosystem',
    label: 'Ecosystem',
    icon: <Globe2 size={15} strokeWidth={1.5} />,
  },
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
  dark?: boolean;
  currentRun?: { status: 'running'; currentPhase: string } | null;
}

const REORDERABLE_IDS = PLUGIN_NAV.filter(n => n.id !== 'dashboard').map(n => n.id);

function loadNavOrder(): string[] {
  try {
    const stored = JSON.parse(localStorage.getItem(NAV_ORDER_KEY) ?? 'null') as string[] | null;
    if (Array.isArray(stored) && stored.every(id => REORDERABLE_IDS.includes(id))) return stored;
  } catch {}
  return REORDERABLE_IDS;
}

export default function Sidebar({ active, queueCount, dark: darkProp, currentRun }: Props) {
  const [user, setUser] = useState<UserProfile | null>(() => {
    try {
      const cached = localStorage.getItem(USER_CACHE_KEY);
      return cached ? (JSON.parse(cached) as UserProfile) : null;
    } catch { return null; }
  });
  const [showWelcome, setShowWelcome] = useState(false);
  const [localDark, setLocalDark] = useState(false);
  const [savedDatabaseDir, setSavedDatabaseDir] = useState<string>('');
  const [navOrder, setNavOrder] = useState<string[]>(REORDERABLE_IDS);
  const dragId = useRef<string | null>(null);
  const dragOverId = useRef<string | null>(null);
  const [hoveredNavId, setHoveredNavId] = useState<string | null>(null);

  useEffect(() => {
    if (darkProp === undefined) {
      queueMicrotask(() => {
        setLocalDark(localStorage.getItem('docent:dark') === 'true');
      });
    }
  }, [darkProp]);

  useEffect(() => {
    queueMicrotask(() => setNavOrder(loadNavOrder()));
  }, []);

  function onDragStart(id: string) { dragId.current = id; }
  function onDragOver(e: React.DragEvent, id: string) {
    e.preventDefault();
    dragOverId.current = id;
  }
  function onDrop() {
    const from = dragId.current;
    const to = dragOverId.current;
    if (!from || !to || from === to) return;
    setNavOrder(prev => {
      const next = [...prev];
      const fi = next.indexOf(from);
      const ti = next.indexOf(to);
      if (fi < 0 || ti < 0) return prev;
      next.splice(fi, 1);
      next.splice(ti, 0, from);
      try { localStorage.setItem(NAV_ORDER_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
    dragId.current = null;
    dragOverId.current = null;
  }

  const dark = darkProp !== undefined ? darkProp : localDark;

  useEffect(() => {
    fetch('/api/user')
      .then(r => r.json())
      .then((data: UserProfile) => {
        setUser(data);
        try { localStorage.setItem(USER_CACHE_KEY, JSON.stringify(data)); } catch {}
        if (!data.name) setShowWelcome(true);
      })
      .catch(() => {});

    fetch('/api/config')
      .then(r => r.json())
      .then((d: { reading: { database_dir: string | null } }) => {
        setSavedDatabaseDir(d.reading?.database_dir ?? '');
      })
      .catch(() => {});
  }, []);

  async function handleWelcomeComplete(profile: UserProfile, databaseDir?: string) {
    setShowWelcome(false);
    setUser(profile);
    try { localStorage.setItem(USER_CACHE_KEY, JSON.stringify(profile)); } catch {}
    try {
      await fetch('/api/user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
    } catch { /* ignore */ }

    if (databaseDir) {
      try {
        await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ section: 'reading', key: 'database_dir', value: databaseDir }),
        });
        setSavedDatabaseDir(databaseDir);
      } catch { /* ignore */ }
    }
  }

  const profileSet = !!user?.name;
  const displayName = user?.name || 'You';
  const displayRole = user?.level && user?.program
    ? `${user.level} · ${user.program}`
    : user?.level || user?.program || 'Graduate student';
  const initial = displayName[0].toUpperCase();

  return (
    <>
      {showWelcome && (
        <WelcomeModal
          onComplete={handleWelcomeComplete}
          onCancel={profileSet ? () => setShowWelcome(false) : undefined}
          initialProfile={profileSet ? user ?? undefined : undefined}
          initialDatabaseDir={savedDatabaseDir}
        />
      )}

      <nav
        aria-label="Main navigation"
        style={{
          width: 220,
          flexShrink: 0,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--bg-subtle)',
          borderRight: '1px solid var(--border)',
        }}
      >
        {/* Logo — 48px to match StatusBanner height; borderBottom aligns as one top bar */}
        <div
          style={{
            height: 48,
            display: 'flex',
            alignItems: 'center',
            padding: '0 18px',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <Image
            src={dark ? '/logo-dark.svg' : '/logo.svg'}
            alt="docent"
            height={28}
            width={112}
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
          {[
            PLUGIN_NAV.find(n => n.id === 'dashboard')!,
            ...navOrder.map(id => PLUGIN_NAV.find(n => n.id === id)!).filter(Boolean),
          ].map((item) => {
            const isActive = item.id === active;
            const isDraggable = item.id !== 'dashboard';
            return (
              <Link
                key={item.id}
                href={item.href}
                aria-current={isActive ? 'page' : undefined}
                draggable={isDraggable}
                onDragStart={isDraggable ? () => onDragStart(item.id) : undefined}
                onDragOver={isDraggable ? (e) => onDragOver(e, item.id) : undefined}
                onDrop={isDraggable ? onDrop : undefined}
                onMouseEnter={() => setHoveredNavId(item.id)}
                onMouseLeave={() => setHoveredNavId(null)}
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
                  cursor: 'pointer',
                }}
              >
                <span style={{ display: 'flex', color: isActive ? '#0fa76e' : 'var(--fg4)' }}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
                {item.id === 'studio' && currentRun?.status === 'running' ? (
                  <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--amber-text)', background: 'var(--amber-bg)', padding: '2px 7px', borderRadius: 9999, letterSpacing: '0.3px', textTransform: 'uppercase', fontWeight: 600 }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#F59E0B', animation: 'logo-dot-blink 0.9s step-end infinite' }} />
                    {currentRun.currentPhase}
                  </span>
                ) : item.id === 'reading' && isActive ? (
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
                ) : isDraggable && hoveredNavId === item.id ? (
                  <span style={{ marginLeft: 'auto', color: 'var(--fg4)', display: 'flex', opacity: 0.5 }}>
                    <GripVertical size={12} strokeWidth={1.5} />
                  </span>
                ) : null}
              </Link>
            );
          })}
        </div>

        {/* Utility nav (Docs + Settings) — pinned above user footer */}
        <div
          style={{
            padding: '4px 18px 8px',
            fontFamily: 'var(--mono)',
            fontSize: 9,
            color: 'var(--fg4)',
            letterSpacing: '0.5px',
            textTransform: 'uppercase',
            opacity: 0.7,
          }}
        >
          Drag tabs to reorder
        </div>
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
            <div suppressHydrationWarning style={{
              width: 28, height: 28, borderRadius: '50%',
              background: 'rgba(24,226,153,0.15)', color: '#0fa76e',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--sans)', fontWeight: 600, fontSize: 12, flexShrink: 0,
            }}>
              {initial}
            </div>
            <div style={{ minWidth: 0 }}>
              <div suppressHydrationWarning style={{
                fontFamily: 'var(--sans)', fontWeight: 500, fontSize: 12,
                color: 'var(--fg1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {displayName}
              </div>
              <div suppressHydrationWarning style={{
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
