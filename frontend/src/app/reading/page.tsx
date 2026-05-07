'use client';

import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Download, Upload, Search, Filter, HelpCircle, BookOpen } from 'lucide-react';

import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import PaperTable from '@/components/PaperTable';
import HowToAddModal from '@/components/HowToAddModal';
import EditModal, { type EditFields } from '@/components/EditModal';
import Toast, { type ToastData } from '@/components/Toast';
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
  const [toast, setToast] = useState<ToastData | null>(null);
  const [editEntry, setEditEntry] = useState<QueueEntry | null>(null);

  // Dark mode: persist to localStorage, apply data-theme attribute
  useEffect(() => {
    const saved = localStorage.getItem('docent:dark');
    if (saved === 'true') setDark(true);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : '');
    localStorage.setItem('docent:dark', dark ? 'true' : 'false');
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
  async function runAction(action: string, id?: string, extra?: Record<string, unknown>) {
    setBusy(action + (id ?? ''));
    try {
      let res: Response;
      try {
        res = await fetch('/api/actions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, id, ...extra }),
        });
      } catch {
        setToast({ type: 'error', message: 'Network error — is the server running?' });
        return;
      }

      const body = await res.json().catch(() => ({})) as Record<string, string>;

      if (!res.ok) {
        const detail = body.error ?? body.stderr ?? 'Unknown error';
        setToast({ type: 'error', message: toastError(action, detail) });
      } else {
        setToast({ type: 'success', message: toastSuccess(action, body.stdout ?? '') });
      }

      await refresh();
    } finally {
      setBusy(null);
    }
  }

  function toastSuccess(action: string, stdout: string): string {
    if (action === 'sync') {
      // stdout contains "X added, Y unchanged, Z removed, W failed."
      const m = stdout.match(/(\d+) added.*?(\d+) unchanged.*?(\d+) removed/);
      if (m) {
        const [, added, unchanged, removed] = m;
        const parts = [];
        if (Number(added) > 0)     parts.push(`${added} added`);
        if (Number(removed) > 0)   parts.push(`${removed} removed`);
        if (Number(unchanged) > 0) parts.push(`${unchanged} unchanged`);
        if (parts.length === 0)    parts.push('Nothing changed');
        return `Mendeley sync — ${parts.join(', ')}.`;
      }
      return 'Mendeley sync complete.';
    }
    if (action === 'scan')   return 'Folder scan complete.';
    if (action === 'done')   return 'Marked as done.';
    if (action === 'remove') return 'Entry removed from queue.';
    if (action === 'start')  return 'Marked as reading.';
    if (action === 'edit')   return 'Entry updated.';
    return 'Done.';
  }

  function toastError(action: string, detail: string): string {
    const label: Record<string, string> = {
      sync:   'Mendeley sync failed',
      scan:   'Scan failed',
      done:   'Could not mark done',
      remove: 'Could not remove entry',
      start:  'Could not start entry',
      edit:   'Could not update entry',
    };
    // Strip ANSI escape codes and Rich markup from CLI output
    const clean = detail.replace(/\x1b\[[0-9;]*m/g, '').trim();
    const first = clean.split('\n').find(l => l.trim()) ?? clean;
    return `${label[action] ?? 'Action failed'}: ${first.slice(0, 120)}`;
  }

  async function handleMarkDone(id: string) {
    await runAction('done', id);
  }

  async function handleDelete(id: string) {
    await runAction('remove', id);
  }

  async function handleStart(id: string) {
    await runAction('start', id);
  }

  async function handleSync() {
    await runAction('sync');
  }

  async function handleEditSave(id: string, fields: EditFields) {
    await runAction('edit', id, fields as Record<string, unknown>);
  }

  async function handleExport() {
    try {
      const res = await fetch('/api/queue');
      if (!res.ok) {
        setToast({ type: 'error', message: 'Export failed: could not fetch queue data.' });
        return;
      }
      const qdata: QueueData = await res.json();
      const json = JSON.stringify(qdata.entries, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `reading-queue-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setToast({ type: 'success', message: `Exported ${qdata.entries.length} entries.` });
    } catch {
      setToast({ type: 'error', message: 'Export failed.' });
    }
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
      <Sidebar active="reading" queueCount={entries.length} dark={dark} />

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
          dotState={busy === 'sync' ? 'working' : 'idle'}
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
                icon={<RefreshCw size={14} strokeWidth={1.5} />}
                onClick={refresh}
              >
                Refresh
              </GhostBtn>
              <GhostBtn
                icon={<Download size={14} strokeWidth={1.5} />}
                onClick={handleSync}
              >
                {busy === 'sync' ? 'Syncing…' : 'Sync Mendeley'}
              </GhostBtn>
              <GhostBtn icon={<Upload size={14} strokeWidth={1.5} />} onClick={handleExport}>
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
          onEdit={(entry) => setEditEntry(entry)}
          onStart={handleStart}
        />
      </main>

      {/* Info modal */}
      {showInfo && <HowToAddModal onClose={() => setShowInfo(false)} />}

      {/* Edit modal */}
      {editEntry && (
        <EditModal
          entry={editEntry}
          onSave={handleEditSave}
          onClose={() => setEditEntry(null)}
        />
      )}

      {/* Toast notifications */}
      {toast && <Toast toast={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
