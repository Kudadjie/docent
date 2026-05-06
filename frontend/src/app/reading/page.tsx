'use client';

import { useState, useEffect, useCallback } from 'react';
import { FolderOpen, RefreshCw, Upload, Search, Filter, HelpCircle, BookOpen } from 'lucide-react';

import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import PaperTable from '@/components/PaperTable';
import HowToAddModal from '@/components/HowToAddModal';
import type { QueueData, QueueEntry, FilterValue, BannerCounts } from '@/lib/types';

// ── Helpers ──────────────────────────────────────────────────────
function applyFilter(entries: QueueEntry[], filter: FilterValue): QueueEntry[] {
  if (filter === 'all') return entries;
  return entries.filter((e) => e.status === filter);
}

function applySearch(entries: QueueEntry[], q: string): QueueEntry[] {
  if (!q.trim()) return entries;
  const lower = q.toLowerCase();
  return entries.filter((e) =>
    [e.title, e.authors, e.notes, e.category ?? '', e.id, ...e.tags]
      .join(' ')
      .toLowerCase()
      .includes(lower)
  );
}

const FILTERS: { value: FilterValue; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'reading', label: 'Reading' },
  { value: 'queued', label: 'Queued' },
  { value: 'done', label: 'Done' },
];

function countByStatus(entries: QueueEntry[], status: FilterValue): number {
  if (status === 'all') return entries.length;
  return entries.filter((e) => e.status === status).length;
}

// ── Ghost button ──────────────────────────────────────────────────
function GhostBtn({
  icon,
  children,
  onClick,
}: {
  icon?: React.ReactNode;
  children: React.ReactNode;
  onClick?: () => void;
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
        border: '1px solid var(--border-md)',
        background: hov ? 'var(--gray100)' : 'transparent',
        color: 'var(--fg2)',
        fontFamily: 'var(--sans)',
        fontSize: 13,
        fontWeight: 500,
        cursor: 'pointer',
        transition: 'background 0.12s',
        whiteSpace: 'nowrap',
      }}
    >
      {icon && (
        <span style={{ color: 'var(--fg4)', display: 'flex' }}>{icon}</span>
      )}
      {children}
    </button>
  );
}

// ── Page ──────────────────────────────────────────────────────────
export default function ReadingPage() {
  const [data, setData] = useState<QueueData | null>(null);
  const [filter, setFilter] = useState<FilterValue>('all');
  const [search, setSearch] = useState('');
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const [showInfo, setShowInfo] = useState(false);
  const [dark, setDark] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  // Dark mode: toggle data-theme attribute on root
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : '');
  }, [dark]);

  // Fetch queue
  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/queue');
      if (res.ok) setData(await res.json());
    } catch {
      /* silent — stale data stays visible */
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Actions
  async function runAction(action: string, id?: string) {
    setBusy(action + (id ?? ''));
    try {
      await fetch('/api/actions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, id }),
      });
      await refresh();
    } finally {
      setBusy(null);
    }
  }

  async function handleMarkDone(id: string) {
    await runAction('done', id);
  }

  async function handleDelete(id: string) {
    if (!confirm('Remove this entry from your queue?')) return;
    await runAction('remove', id);
  }

  async function handleScan() {
    await runAction('scan');
  }

  async function handleSync() {
    await runAction('sync');
  }

  const entries: QueueEntry[] = data?.entries ?? [];
  const banner: BannerCounts = data?.banner ?? { queued: 0, reading: 0, done: 0 };
  const filtered = applySearch(applyFilter(entries, filter), search);

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--bg)',
      }}
    >
      <Sidebar active="reading" queueCount={entries.length} />

      <main
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          overflow: 'hidden',
        }}
      >
        {/* Status banner */}
        <StatusBanner
          banner={banner}
          lastUpdated={data?.last_updated ?? null}
          databaseCount={data?.database_count ?? null}
          dark={dark}
          onToggleDark={() => setDark((d) => !d)}
        />

        {/* Page header */}
        <div
          style={{
            padding: '20px 24px 0',
            borderBottom: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
          {/* Title row */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              marginBottom: 16,
            }}
          >
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  marginBottom: 4,
                }}
              >
                <BookOpen size={16} strokeWidth={1.5} color="#0fa76e" />
                <h1
                  style={{
                    fontFamily: 'var(--sans)',
                    fontSize: 18,
                    fontWeight: 600,
                    letterSpacing: '-0.3px',
                    color: 'var(--fg1)',
                    margin: 0,
                  }}
                >
                  Reading
                </h1>
              </div>
              <p
                style={{
                  fontFamily: 'var(--sans)',
                  fontSize: 13,
                  color: 'var(--fg3)',
                  margin: 0,
                }}
              >
                Local reading queue · {entries.length} papers
              </p>
            </div>

            {/* How to add button */}
            <GhostBtn
              icon={<HelpCircle size={14} strokeWidth={1.5} />}
              onClick={() => setShowInfo(true)}
            >
              How to add?
            </GhostBtn>
          </div>

          {/* Action bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
            }}
          >
            {/* Left: action buttons */}
            <div style={{ display: 'flex', gap: 6 }}>
              <GhostBtn
                icon={<FolderOpen size={14} strokeWidth={1.5} />}
                onClick={handleScan}
              >
                {busy === 'scan' ? 'Scanning…' : 'Scan folder'}
              </GhostBtn>
              <GhostBtn
                icon={<RefreshCw size={14} strokeWidth={1.5} />}
                onClick={handleSync}
              >
                {busy === 'sync' ? 'Syncing…' : 'Sync Mendeley'}
              </GhostBtn>
              <GhostBtn icon={<Upload size={14} strokeWidth={1.5} />}>
                Export
              </GhostBtn>
            </div>

            {/* Right: search + filter */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <div style={{ position: 'relative' }}>
                <span
                  style={{
                    position: 'absolute',
                    left: 10,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--fg4)',
                    display: 'flex',
                    pointerEvents: 'none',
                  }}
                >
                  <Search size={14} strokeWidth={1.5} />
                </span>
                <input
                  type="search"
                  placeholder="Search papers…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  aria-label="Search papers"
                  style={{
                    width: 180,
                    padding: '5px 12px 5px 32px',
                    borderRadius: 9999,
                    border: '1px solid var(--border-md)',
                    fontFamily: 'var(--sans)',
                    fontSize: 12,
                    color: 'var(--fg1)',
                    background: 'var(--bg)',
                    outline: 'none',
                  }}
                />
              </div>
              <GhostBtn icon={<Filter size={14} strokeWidth={1.5} />}>
                Filter
              </GhostBtn>
            </div>
          </div>

          {/* Filter tabs */}
          <div
            role="tablist"
            aria-label="Filter by status"
            style={{ display: 'flex', marginTop: 12 }}
          >
            {FILTERS.map(({ value, label }) => {
              const isActive = filter === value;
              const count = countByStatus(entries, value);
              return (
                <button
                  key={value}
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setFilter(value)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '8px 14px',
                    border: 'none',
                    borderBottom: isActive ? '2px solid #18E299' : '2px solid transparent',
                    background: 'transparent',
                    fontFamily: 'var(--sans)',
                    fontSize: 13,
                    fontWeight: isActive ? 500 : 400,
                    color: isActive ? 'var(--fg1)' : 'var(--fg4)',
                    cursor: 'pointer',
                  }}
                >
                  {label}
                  <span
                    style={{
                      fontFamily: 'var(--mono)',
                      fontSize: 10,
                      padding: '1px 6px',
                      borderRadius: 9999,
                      background: isActive ? 'var(--gray100)' : 'transparent',
                      color: isActive ? 'var(--fg2)' : 'var(--fg4)',
                    }}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Table */}
        <PaperTable
          entries={filtered}
          newIds={newIds}
          dark={dark}
          onMarkDone={handleMarkDone}
          onDelete={handleDelete}
        />
      </main>

      {/* Info modal */}
      {showInfo && <HowToAddModal onClose={() => setShowInfo(false)} />}
    </div>
  );
}
