'use client';

import { useState, useEffect, useRef } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { BookOpen, FlaskConical, BookText, Settings, Globe2, GripVertical, Wrench, Blocks, ChevronsLeft, ChevronsRight } from 'lucide-react';
import WelcomeModal, { type UserProfile } from './WelcomeModal';
import { useAppRun } from '@/lib/app-run-context';

const NAV_ORDER_KEY    = 'docent:nav-order';
const USER_CACHE_KEY   = 'docent:user-profile';
const NAV_COLLAPSE_KEY = 'docent:nav-collapsed';
const W_EXPANDED = 220;
const W_COLLAPSED = 64;

interface NavItem {
  id: string;
  href: string;
  label: string;
  icon: React.ReactNode;
}

const PLUGIN_NAV: NavItem[] = [
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
  {
    id: 'tools',
    href: '/tools',
    label: 'Tools',
    icon: <Wrench size={16} strokeWidth={1.5} />,
  },
  {
    id: 'plugin-builder',
    href: '/plugin-builder',
    label: 'Plugin Builder',
    icon: <Blocks size={16} strokeWidth={1.5} />,
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
}

const REORDERABLE_IDS = PLUGIN_NAV.map(n => n.id);

function loadNavOrder(): string[] {
  try {
    const stored = JSON.parse(localStorage.getItem(NAV_ORDER_KEY) ?? 'null') as string[] | null;
    if (Array.isArray(stored)) {
      const valid = stored.filter(id => REORDERABLE_IDS.includes(id));
      const missing = REORDERABLE_IDS.filter(id => !valid.includes(id));
      // Exact match — use as stored.
      if (missing.length === 0 && valid.length === REORDERABLE_IDS.length) return valid;
      // Partial (e.g. old localStorage missing 'tools') — append new ids to end.
      if (valid.length > 0) return [...valid, ...missing];
    }
  } catch {}
  return REORDERABLE_IDS;
}

export default function Sidebar({ active, queueCount, dark: darkProp }: Props) {
  // Read generic app activity from AppRunContext — works for Studio and any
  // future background operation (Reading sync, Export, etc.).
  const { activities } = useAppRun();
  const studioActivity = activities['studio'];
  const currentRun = studioActivity?.status === 'running'
    ? { status: 'running' as const, currentPhase: (studioActivity.phase ?? 'run').slice(0, 7) }
    : null;
  const [user, setUser] = useState<UserProfile | null>(() => {
    try {
      const cached = localStorage.getItem(USER_CACHE_KEY);
      return cached ? (JSON.parse(cached) as UserProfile) : null;
    } catch { return null; }
  });
  const [showWelcome, setShowWelcome] = useState(false);
  const [localDark, setLocalDark] = useState(false);
  const [savedDatabaseDir, setSavedDatabaseDir] = useState<string>('');
  const [savedOutputDir, setSavedOutputDir] = useState<string>('');
  const [navOrder, setNavOrder] = useState<string[]>(REORDERABLE_IDS);
  // Read collapsed synchronously so a fresh Sidebar (mounted on every client-side
  // route change) starts at the correct width — no expand→collapse snap on tab change.
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem(NAV_COLLAPSE_KEY) === '1'; } catch { return false; }
  });
  // Gate the width transition until after first paint so the initial mount never animates.
  const [navMounted, setNavMounted] = useState(false);
  const dragId = useRef<string | null>(null);
  const dragOverId = useRef<string | null>(null);
  const [hoveredNavId, setHoveredNavId] = useState<string | null>(null);

  // One-time flag to enable the width transition only after first paint (avoids
  // animating the sidebar on mount / cross-page navigation).
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { setNavMounted(true); }, []);

  function toggleCollapsed() {
    setCollapsed(c => {
      const next = !c;
      try { localStorage.setItem(NAV_COLLAPSE_KEY, next ? '1' : '0'); } catch {}
      return next;
    });
  }

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
      .then((d: { reading: { database_dir: string | null; output_dir: string | null } }) => {
        setSavedDatabaseDir(d.reading?.database_dir ?? '');
        setSavedOutputDir(d.reading?.output_dir ?? '');
      })
      .catch(() => {});
  }, []);

  async function handleWelcomeComplete(profile: UserProfile, databaseDir?: string, outputDir?: string) {
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

    if (outputDir) {
      try {
        await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ section: 'reading', key: 'output_dir', value: outputDir }),
        });
        setSavedOutputDir(outputDir);
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
          initialOutputDir={savedOutputDir}
        />
      )}

      <nav
        aria-label="Main navigation"
        suppressHydrationWarning
        style={{
          width: collapsed ? W_COLLAPSED : W_EXPANDED,
          flexShrink: 0,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--bg-subtle)',
          borderRight: '1px solid var(--border)',
          transition: navMounted ? 'width 0.16s ease' : 'none',
          overflow: 'hidden',
        }}
      >
        {/* Logo — 48px to match StatusBanner height; borderBottom aligns as one top bar */}
        <div
          style={{
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? '0' : '0 18px',
            borderBottom: '1px solid var(--border)',
          }}
        >
          {collapsed ? (
            <Image src={dark ? '/favicon-dark.svg' : '/favicon.svg'} alt="docent" height={24} width={24} style={{ display: 'block' }} priority />
          ) : (
            <Image
              src={dark ? '/logo-dark.svg' : '/logo.svg'}
              alt="docent"
              height={28}
              width={112}
              style={{ display: 'block' }}
              priority
            />
          )}
        </div>

        {/* Plugin nav items */}
        <div
          style={{
            flex: 1,
            padding: collapsed ? '10px 8px' : '10px 8px',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          {navOrder
            .map(id => PLUGIN_NAV.find(n => n.id === id)!)
            .filter(Boolean)
            .map((item) => {
            const isActive = item.id === active;
            const isDraggable = !collapsed;
            const studioRunning = item.id === 'studio' && currentRun?.status === 'running';
            return (
              <Link
                key={item.id}
                href={item.href}
                aria-current={isActive ? 'page' : undefined}
                title={collapsed ? item.label : undefined}
                draggable={isDraggable}
                onDragStart={isDraggable ? () => onDragStart(item.id) : undefined}
                onDragOver={isDraggable ? (e) => onDragOver(e, item.id) : undefined}
                onDrop={isDraggable ? onDrop : undefined}
                onMouseEnter={() => setHoveredNavId(item.id)}
                onMouseLeave={() => setHoveredNavId(null)}
                style={{
                  position: 'relative',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  gap: collapsed ? 0 : 9,
                  width: '100%',
                  padding: collapsed ? '9px 0' : '7px 10px',
                  borderRadius: 8,
                  border: 'none',
                  textDecoration: 'none',
                  background: isActive ? 'var(--brand-light)' : 'transparent',
                  color: isActive ? 'var(--brand-deep)' : 'var(--fg3)',
                  fontFamily: 'var(--sans)',
                  fontSize: 13,
                  fontWeight: isActive ? 500 : 400,
                  transition: 'background 0.1s, color 0.1s',
                  boxShadow: isActive ? 'rgba(20,20,19,0.04) 0px 1px 3px' : 'none',
                  cursor: 'pointer',
                }}
              >
                <span style={{ display: 'flex', color: isActive ? 'var(--brand-deep)' : 'var(--fg4)' }}>
                  {item.icon}
                </span>
                {/* Collapsed: small dot marks a running Studio job */}
                {collapsed && studioRunning && (
                  <span style={{ position: 'absolute', top: 6, right: 10, width: 6, height: 6, borderRadius: '50%', background: '#F59E0B', animation: 'logo-dot-blink 0.9s step-end infinite' }} />
                )}
                {!collapsed && <span>{item.label}</span>}
                {!collapsed && (studioRunning ? (
                  <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--amber-text)', background: 'var(--amber-bg)', padding: '2px 7px', borderRadius: 9999, letterSpacing: '0.3px', textTransform: 'uppercase', fontWeight: 600 }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#F59E0B', animation: 'logo-dot-blink 0.9s step-end infinite' }} />
                    {currentRun!.currentPhase}
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
                      background: 'var(--brand-light)',
                      color: 'var(--brand-deep)',
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
                ) : null)}
              </Link>
            );
          })}
        </div>

        {/* Reorder hint — only when expanded */}
        {!collapsed && (
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
        )}

        {/* Utility nav (Ecosystem + Docs + Settings) — pinned above toggle/footer */}
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
                title={collapsed ? item.label : undefined}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  gap: collapsed ? 0 : 8,
                  width: '100%',
                  padding: collapsed ? '7px 0' : '5px 10px',
                  borderRadius: 6,
                  border: 'none',
                  textDecoration: 'none',
                  background: collapsed && isActive ? 'var(--brand-light)' : 'transparent',
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
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </div>

        {/* Collapse / expand toggle */}
        <button
          onClick={toggleCollapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand' : 'Collapse'}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: 8,
            width: '100%',
            padding: collapsed ? '8px 0' : '8px 18px',
            borderTop: '1px solid var(--border)',
            borderLeft: 'none', borderRight: 'none', borderBottom: 'none',
            background: 'transparent',
            color: 'var(--fg4)',
            fontFamily: 'var(--sans)',
            fontSize: 11,
            cursor: 'pointer',
          }}
        >
          <span style={{ display: 'flex' }}>
            {collapsed ? <ChevronsRight size={15} strokeWidth={1.5} /> : <ChevronsLeft size={15} strokeWidth={1.5} />}
          </span>
          {!collapsed && <span>Collapse</span>}
        </button>

        {/* User footer — suppressHydrationWarning because server renders null user
            (setup button) while client immediately has the localStorage-cached
            profile (profile button), causing a structural DOM mismatch. */}
        <div suppressHydrationWarning>
        {profileSet ? (
          <button
            onClick={() => setShowWelcome(true)}
            title={collapsed ? `${displayName} — edit profile` : 'Edit profile'}
            style={{
              width: '100%',
              padding: collapsed ? '12px 0' : '12px 18px',
              borderTop: '1px solid var(--border)',
              borderLeft: 'none', borderRight: 'none', borderBottom: 'none',
              background: 'transparent',
              display: 'flex', alignItems: 'center', justifyContent: collapsed ? 'center' : 'flex-start', gap: 8,
              cursor: 'pointer', textAlign: 'left',
            }}
          >
            <div suppressHydrationWarning style={{
              width: 28, height: 28, borderRadius: '50%',
              background: 'var(--brand-light)', color: 'var(--brand-deep)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--sans)', fontWeight: 600, fontSize: 12, flexShrink: 0,
            }}>
              {initial}
            </div>
            {!collapsed && (
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
            )}
          </button>
        ) : (
          <button
            onClick={() => setShowWelcome(true)}
            title={collapsed ? 'Set up your profile' : undefined}
            style={{
              width: '100%',
              padding: collapsed ? '12px 0' : '12px 18px',
              borderTop: '1px solid var(--border)',
              borderLeft: 'none', borderRight: 'none', borderBottom: 'none',
              background: 'transparent',
              display: 'flex', alignItems: 'center', justifyContent: collapsed ? 'center' : 'flex-start', gap: 8,
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
            {!collapsed && (
            <div style={{ minWidth: 0 }}>
              <div style={{
                fontFamily: 'var(--sans)', fontWeight: 500, fontSize: 12, color: 'var(--brand-deep)',
              }}>
                Set up your profile
              </div>
              <div style={{
                fontFamily: 'var(--sans)', fontWeight: 400, fontSize: 11, color: 'var(--fg4)',
              }}>
                Name, program, level
              </div>
            </div>
            )}
          </button>
        )}
        </div>
      </nav>
    </>
  );
}
