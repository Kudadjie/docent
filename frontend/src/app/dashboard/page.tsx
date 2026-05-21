'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';
import { useTour } from '@/hooks/useTour';
import { dashTokens, BRAND, VIOLET, MONO } from './_tokens';
import { CardShell } from './_primitives';
import ReadingCard from './_reading';
import StudioCard from './_studio';
import ActivityHeatmap from './_activity';
import QuickActions from './_quickactions';
import type { DashboardPlugin, DashboardStat } from './_registry';

// ─── Plugin registry ──────────────────────────────────────────────────────────
// Adding a new tool to Docent = one entry here.
// Each Card receives `dark` and `onStats` — call onStats once with your stat
// contributions so they appear in the global stat row automatically.
const PLUGIN_CARDS: DashboardPlugin[] = [
  { id: 'reading', Card: ReadingCard  },
  { id: 'studio',  Card: StudioCard  },
  // Future plugins registered here — no layout code to touch.
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

function formatDatetime(): string {
  const d = new Date();
  const wd  = ['SUN','MON','TUE','WED','THU','FRI','SAT'][d.getDay()];
  const day = String(d.getDate()).padStart(2, '0');
  const mo  = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'][d.getMonth()];
  const yr  = d.getFullYear();
  const h12 = ((d.getHours() + 11) % 12) + 1;
  const mn  = String(d.getMinutes()).padStart(2, '0');
  const ap  = d.getHours() >= 12 ? 'PM' : 'AM';
  return `${wd} ${day} ${mo} ${yr} · ${h12}:${mn} ${ap}`;
}

// ─── Global stat row ──────────────────────────────────────────────────────────
function StatCell({ stat, dark, showDivider }: { stat: DashboardStat; dark: boolean; showDivider: boolean }) {
  const D = dashTokens(dark);
  return (
    <>
      <div style={{ flex: 1, padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
        <div style={{
          fontFamily: MONO, fontSize: 28, fontWeight: 600, lineHeight: 1,
          letterSpacing: '-0.5px',
          color: stat.dim ? D.dataMuted : (stat.color ?? D.dataBright),
        }}>
          {stat.value}
        </div>
        <div style={{
          fontFamily: MONO, fontSize: 10, fontWeight: 500,
          color: D.sectionLabel, letterSpacing: '1px', textTransform: 'uppercase',
        }}>
          {stat.label}
        </div>
      </div>
      {showDivider && <div style={{ width: 1, background: D.divider, flexShrink: 0 }} />}
    </>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
interface UserProfile { name: string; program: string; level: string }

export default function DashboardPage() {
  const { dark, toggleDark } = useDarkMode();
  const D = dashTokens(dark);

  useTour('dashboard', [
    {
      popover: {
        title: 'Welcome to Docent',
        description: "Docent is your grad school AI — a single place to manage your reading, run research, and stay on top of your academic work. Let's take a quick look around.",
      },
    },
    {
      element: 'nav[aria-label="Main navigation"]',
      popover: {
        title: 'Navigate Docent',
        description: 'Reading manages your paper queue and syncs with Mendeley. Studio runs AI-powered research sessions. Ecosystem and Docs cover your tools and guides.',
      },
    },
    {
      element: '[data-tour="stat-row"]',
      popover: {
        title: 'At a glance',
        description: 'Your key numbers live here — papers queued, in progress, done, and research outputs. Each plugin you add to Docent contributes its own stat automatically.',
      },
    },
    {
      element: '[data-tour="card-grid"]',
      popover: {
        title: 'Tool cards',
        description: 'Each card is a live window into a Docent tool. As more tools are added, new cards appear here automatically.',
      },
    },
  ]);

  // Collect stats from all plugin cards
  const [statMap, setStatMap] = useState<Record<string, DashboardStat[]>>({});
  const handleStats = useCallback((id: string, stats: DashboardStat[]) => {
    setStatMap(prev => ({ ...prev, [id]: stats }));
  }, []);

  // Flatten stats in plugin order (preserves consistent left→right column order)
  const allStats = PLUGIN_CARDS.flatMap(p => statMap[p.id] ?? []);

  // User profile for greeting — seed from localStorage cache, then refresh from API
  const [user, setUser] = useState<UserProfile | null>(() => {
    try {
      const cached = localStorage.getItem('docent:user-profile');
      return cached ? (JSON.parse(cached) as UserProfile) : null;
    } catch { return null; }
  });
  useEffect(() => {
    fetch('/api/user').then(r => r.json()).then(setUser).catch(() => {});
  }, []);

  // Activity heatmap needs Studio output mtimes
  const [outputMtimes, setOutputMtimes] = useState<number[]>([]);
  useEffect(() => {
    fetch('/api/studio/outputs')
      .then(r => r.json())
      .then((d: { files: Array<{ mtime: number }> }) => {
        setOutputMtimes((d.files ?? []).map(f => f.mtime));
      })
      .catch(() => {});
  }, []);

  // Clock tick for live datetime display
  const [datetime, setDatetime] = useState(formatDatetime());
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    tickRef.current = setInterval(() => setDatetime(formatDatetime()), 60000);
    return () => { if (tickRef.current) clearInterval(tickRef.current); };
  }, []);

  const displayName    = user?.name || null;
  const displayProgram = [user?.level, user?.program].filter(Boolean).join(' · ');

  const queueCount = (statMap['reading']?.find(s => s.label === 'Queued')?.value as number) ?? 0;

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="dashboard" queueCount={queueCount} dark={dark} />

      <main
        className="dash-main-bg"
        style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}
      >
        <StatusBanner dark={dark} onToggleDark={toggleDark} />

        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', background: 'transparent' }}>

          {/* Greeting strip */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 24px',
            borderBottom: `1px solid ${D.divider}`,
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
              <span suppressHydrationWarning style={{
                fontSize: 16, fontWeight: 600,
                color: 'var(--fg1)', letterSpacing: '-0.2px',
              }}>
                {displayName ? `${greeting()}, ${displayName}` : 'Welcome to Docent'}
              </span>
              {displayProgram && (
                <>
                  <span style={{ color: D.sectionLabel, fontSize: 14, lineHeight: 1 }}>·</span>
                  <span suppressHydrationWarning style={{ fontSize: 14, color: 'var(--fg3)' }}>
                    {displayProgram}
                  </span>
                </>
              )}
            </div>
            <span suppressHydrationWarning style={{
              fontFamily: MONO, fontSize: 11, color: D.dataMuted,
              letterSpacing: '0.5px', whiteSpace: 'nowrap',
            }}>
              {datetime}
            </span>
          </div>

          {/* Main content */}
          <div style={{
            flex: 1,
            padding: '18px 24px 28px',
            display: 'flex', flexDirection: 'column', gap: 16,
          }}>

            {/* Global stat row */}
            {allStats.length > 0 && (
              <CardShell dark={dark} style={{ flexDirection: 'row' }} data-tour="stat-row">
                {allStats.map((stat, i) => (
                  <StatCell
                    key={`${stat.label}-${i}`}
                    stat={stat}
                    dark={dark}
                    showDivider={i < allStats.length - 1}
                  />
                ))}
              </CardShell>
            )}

            {/* Plugin card grid */}
            <div
              data-tour="card-grid"
              style={{
                display: 'grid',
                // 2-column grid; odd final card spans full width
                gridTemplateColumns: PLUGIN_CARDS.length === 1 ? '1fr' : 'repeat(2, 1fr)',
                gap: 16,
              }}
            >
              {PLUGIN_CARDS.map((plugin, i) => {
                const isOddLast = PLUGIN_CARDS.length % 2 !== 0 && i === PLUGIN_CARDS.length - 1;
                return (
                  <div key={plugin.id} style={{
                    minWidth: 0,
                    overflow: 'hidden',
                    ...(isOddLast ? { gridColumn: '1 / -1' } : {}),
                  }}>
                    <plugin.Card
                      dark={dark}
                      onStats={(stats) => handleStats(plugin.id, stats)}
                    />
                  </div>
                );
              })}
            </div>

            {/* Bottom row: Activity heatmap + Quick Actions */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
              <div style={{ minWidth: 0 }}><ActivityHeatmap dark={dark} mtimes={outputMtimes} /></div>
              <div style={{ minWidth: 0 }}><QuickActions dark={dark} /></div>
            </div>

            {/* Footer breadcrumb */}
            <div style={{
              display: 'flex', justifyContent: 'space-between', paddingTop: 4,
              fontFamily: MONO, fontSize: 9, color: D.sectionLabel,
              textTransform: 'uppercase', letterSpacing: '0.85px',
            }}>
              <span>
                Docent · Dashboard{displayProgram ? ` · ${displayProgram}` : ''}
              </span>
              <span>{dark ? 'Dark' : 'Light'}</span>
            </div>

          </div>
        </div>
      </main>
    </div>
  );
}
