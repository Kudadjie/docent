'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw, Download, Printer, Search, Filter, HelpCircle, BookOpen, ArrowRight, BarChart2 } from 'lucide-react';

import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import PaperTable from '@/components/PaperTable';
import HowToAddModal from '@/components/HowToAddModal';
import EditModal, { type EditFields } from '@/components/EditModal';
import StatsModal from '@/components/StatsModal';
import DetailModal from '@/components/DetailModal';
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
  active,
}: {
  icon?: React.ReactNode;
  children: React.ReactNode;
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
  const [detailEntry, setDetailEntry] = useState<QueueEntry | null>(null);
  const [statsOpen, setStatsOpen] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [urlReady, setUrlReady] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const filterRef = useRef<HTMLDivElement>(null);
  const autoSyncedRef = useRef(false);

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

  // Read filter + search from URL on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const f = params.get('filter');
    if (f && ['all', 'reading', 'queued', 'done'].includes(f)) setFilter(f as FilterValue);
    const q = params.get('q');
    if (q) setSearch(q);
    setUrlReady(true);
  }, []);

  // Write filter + search to URL whenever they change (after initial read)
  useEffect(() => {
    if (!urlReady) return;
    const params = new URLSearchParams();
    if (filter !== 'all') params.set('filter', filter);
    if (search) params.set('q', search);
    const qs = params.toString();
    window.history.replaceState(null, '', qs ? `?${qs}` : window.location.pathname);
  }, [filter, search, urlReady]);

  // Close filter dropdown on outside click
  useEffect(() => {
    if (!filterOpen) return;
    function handle(e: MouseEvent) {
      if (filterRef.current && !filterRef.current.contains(e.target as Node)) {
        setFilterOpen(false);
      }
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [filterOpen]);

  // 30s polling — re-reads queue.json from disk, no CLI call
  useEffect(() => {
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [refresh]);

  // Auto-sync on load if queue is stale (> 30 min)
  useEffect(() => {
    if (!data || autoSyncedRef.current) return;
    autoSyncedRef.current = true;
    const age = data.last_updated
      ? Date.now() - new Date(data.last_updated).getTime()
      : Infinity;
    if (age < 30 * 60 * 1000) return;
    // Silent sync: show success toast, swallow errors
    fetch('/api/actions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'sync' }),
    })
      .then(r => r.json())
      .then((body: Record<string, string>) => {
        if (body.ok) {
          setToast({ type: 'success', message: toastSuccess('sync', body.stdout ?? '') });
          refresh();
        }
      })
      .catch(() => {});
  }, [data, refresh]);

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
      } else if (action === 'sync') {
        // Sync exits 0 even for handled failures (wrong collection, auth error).
        // Only show success if the count pattern is present in stdout.
        const stdout = body.stdout ?? '';
        if (/\d+ added.*?\d+ unchanged.*?\d+ removed/.test(stdout)) {
          setToast({ type: 'success', message: toastSuccess(action, stdout) });
        } else {
          const clean = stdout.replace(/\x1b\[[0-9;]*m/g, '').trim();
          setToast({ type: 'error', message: clean.slice(0, 200) || 'Sync returned no results — check your collection name in Settings.' });
        }
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
      // CLI exited 0 but printed a warning (wrong collection name, auth issue, etc.)
      const clean = stdout.replace(/\x1b\[[0-9;]*m/g, '').trim();
      if (clean) return clean.slice(0, 160);
      return 'Mendeley sync complete.';
    }
    if (action === 'scan')   return 'Folder scan complete.';
    if (action === 'done')   return 'Marked as done.';
    if (action === 'start')  return 'Marked as reading.';
    if (action === 'edit')      return 'Entry updated.';
    if (action === 'move-up')   return 'Moved up.';
    if (action === 'move-down') return 'Moved down.';
    return 'Done.';
  }

  function toastError(action: string, detail: string): string {
    const label: Record<string, string> = {
      sync:   'Mendeley sync failed',
      scan:   'Scan failed',
      done:   'Could not mark done',
      start:  'Could not start entry',
      edit:        'Could not update entry',
      'move-up':   'Could not move up',
      'move-down': 'Could not move down',
    };
    // Strip ANSI escape codes and Rich markup from CLI output
    const clean = detail.replace(/\x1b\[[0-9;]*m/g, '').trim();
    const first = clean.split('\n').find(l => l.trim()) ?? clean;
    return `${label[action] ?? 'Action failed'}: ${first.slice(0, 120)}`;
  }

  async function handleMarkDone(id: string) {
    await runAction('done', id);
  }

  async function handleStart(id: string) {
    await runAction('start', id);
  }

  async function handleMoveUp(id: string) {
    await runAction('move-up', id);
  }

  async function handleMoveDown(id: string) {
    await runAction('move-down', id);
  }

  function handleNext() {
    const queued = entries
      .filter(e => e.status === 'queued')
      .sort((a, b) => a.order - b.order);
    if (queued.length === 0) {
      setToast({ type: 'error', message: 'No queued papers.' });
      return;
    }
    const next = queued[0];
    setHighlightId(next.id);
    document.querySelector(`[data-entry-id="${next.id}"]`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => setHighlightId(null), 2500);
    setToast({ type: 'success', message: `Next: ${next.title || next.id}` });
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
      const exportDate = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

      const groups: { label: string; status: string; entries: QueueEntry[] }[] = [
        { label: 'Currently Reading', status: 'reading', entries: [] },
        { label: 'Queued', status: 'queued', entries: [] },
        { label: 'Done', status: 'done', entries: [] },
      ];
      for (const e of qdata.entries) {
        const g = groups.find(g => g.status === e.status);
        if (g) g.entries.push(e);
      }
      // Sort active groups by order; done by finished date
      groups[0].entries.sort((a, b) => a.order - b.order);
      groups[1].entries.sort((a, b) => a.order - b.order);

      function fmtDate(iso: string | null) {
        if (!iso) return '';
        try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
        catch { return iso; }
      }

      function entryHtml(e: QueueEntry, idx: number) {
        const typeTag = e.type === 'book' ? 'Book' : e.type === 'book_chapter' ? 'Chapter' : '';
        const meta = [e.authors, e.year, e.category].filter(Boolean).join('  ·  ');
        const deadline = e.deadline ? `Due ${fmtDate(e.deadline)}` : '';
        const started = e.started ? `Started ${fmtDate(e.started)}` : '';
        const finished = e.finished ? `Finished ${fmtDate(e.finished)}` : '';
        const dates = [started, finished, deadline].filter(Boolean).join('  ·  ');
        return `
          <div class="entry">
            <div class="entry-num">${idx + 1}</div>
            <div class="entry-body">
              <div class="entry-title">${e.title || e.id}${typeTag ? ` <span class="type-tag">${typeTag}</span>` : ''}</div>
              ${meta ? `<div class="entry-meta">${meta}</div>` : ''}
              ${dates ? `<div class="entry-dates">${dates}</div>` : ''}
              ${e.doi ? `<div class="entry-doi">DOI: ${e.doi}</div>` : ''}
              ${e.tags.length ? `<div class="entry-tags">${e.tags.map(t => `<span class="tag">${t}</span>`).join('')}</div>` : ''}
              ${e.notes ? `<div class="entry-notes">${e.notes}</div>` : ''}
            </div>
          </div>`;
      }

      const sectionsHtml = groups
        .filter(g => g.entries.length > 0)
        .map(g => `
          <section>
            <h2>${g.label} <span class="section-count">${g.entries.length}</span></h2>
            ${g.entries.map((e, i) => entryHtml(e, i)).join('')}
          </section>`)
        .join('');

      const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Reading Queue — ${exportDate}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 12pt; color: #1a1a1a; background: #fff; padding: 48px; max-width: 780px; margin: 0 auto; }
  header { border-bottom: 2px solid #18E299; padding-bottom: 16px; margin-bottom: 36px; }
  .logo { font-size: 22pt; font-weight: 700; letter-spacing: -0.5px; color: #0fa76e; }
  .header-sub { font-size: 10pt; color: #888; margin-top: 4px; }
  .summary { display: flex; gap: 24px; margin-bottom: 36px; }
  .summary-item { font-size: 10pt; color: #555; }
  .summary-item strong { color: #1a1a1a; font-size: 14pt; display: block; }
  section { margin-bottom: 36px; }
  h2 { font-size: 11pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; color: #555; border-bottom: 1px solid #eee; padding-bottom: 8px; margin-bottom: 16px; }
  .section-count { font-weight: 400; color: #aaa; }
  .entry { display: flex; gap: 14px; margin-bottom: 18px; padding-bottom: 18px; border-bottom: 1px solid #f0f0f0; }
  .entry:last-child { border-bottom: none; }
  .entry-num { font-size: 10pt; color: #ccc; font-weight: 600; min-width: 24px; padding-top: 2px; }
  .entry-title { font-size: 12pt; font-weight: 600; color: #1a1a1a; line-height: 1.4; }
  .type-tag { font-size: 8pt; font-weight: 500; text-transform: uppercase; letter-spacing: 0.4px; color: #888; background: #f2f2f2; padding: 1px 5px; border-radius: 3px; vertical-align: middle; margin-left: 6px; }
  .entry-meta { font-size: 10pt; color: #666; margin-top: 4px; }
  .entry-dates { font-size: 9pt; color: #999; margin-top: 3px; }
  .entry-doi { font-size: 9pt; color: #aaa; margin-top: 3px; font-family: monospace; }
  .entry-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
  .tag { font-size: 8pt; text-transform: uppercase; letter-spacing: 0.3px; color: #888; background: #f5f5f5; padding: 2px 7px; border-radius: 99px; }
  .entry-notes { font-size: 10pt; color: #555; margin-top: 6px; font-style: italic; line-height: 1.5; }
  @media print {
    body { padding: 0; }
    .entry { break-inside: avoid; }
    section { break-inside: avoid; }
  }
</style>
</head>
<body>
<header>
  <div class="logo">docent</div>
  <div class="header-sub">Reading Queue — exported ${exportDate}</div>
</header>
<div class="summary">
  <div class="summary-item"><strong>${groups[1].entries.length}</strong>Queued</div>
  <div class="summary-item"><strong>${groups[0].entries.length}</strong>Reading</div>
  <div class="summary-item"><strong>${groups[2].entries.length}</strong>Done</div>
  <div class="summary-item"><strong>${qdata.entries.length}</strong>Total</div>
</div>
${sectionsHtml}
</body>
</html>`;

      const w = window.open('', '_blank');
      if (!w) {
        setToast({ type: 'error', message: 'Pop-up blocked — allow pop-ups to export as PDF.' });
        return;
      }
      w.document.write(html);
      w.document.close();
      w.focus();
      setTimeout(() => w.print(), 300);
      setToast({ type: 'success', message: `Opened print dialog for ${qdata.entries.length} entries.` });
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
          dotState={busy === 'sync' || busy === 'refresh' ? 'working' : 'idle'}
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
                Local reading queue · {entries.length} {entries.length === 1 ? 'entry' : 'entries'}{' '}
              <span style={{ color: 'var(--fg4)' }}>·</span>{' '}
              <span title="Entries are added and removed by syncing with Mendeley. Docent does not edit your Mendeley library.">
                managed via Mendeley
              </span>
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
                onClick={async () => { setBusy('refresh'); await refresh(); setBusy(null); }}
              >
                {busy === 'refresh' ? 'Refreshing…' : 'Refresh'}
              </GhostBtn>
              <GhostBtn
                icon={<Download size={14} strokeWidth={1.5} />}
                onClick={handleSync}
              >
                {busy === 'sync' ? 'Syncing…' : 'Sync Mendeley'}
              </GhostBtn>
              <GhostBtn icon={<Printer size={14} strokeWidth={1.5} />} onClick={handleExport}>
                Export PDF
              </GhostBtn>
              <GhostBtn icon={<ArrowRight size={14} strokeWidth={1.5} />} onClick={handleNext}>
                Next
              </GhostBtn>
              <GhostBtn icon={<BarChart2 size={14} strokeWidth={1.5} />} onClick={() => setStatsOpen(true)}>
                Stats
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
                  placeholder="Search entries…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  aria-label="Search entries"
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
              {/* Filter dropdown */}
              <div ref={filterRef} style={{ position: 'relative' }}>
                <GhostBtn
                  icon={<Filter size={14} strokeWidth={1.5} />}
                  onClick={() => setFilterOpen(o => !o)}
                  active={filter !== 'all'}
                >
                  {filter === 'all' ? 'Filter' : FILTERS.find(f => f.value === filter)?.label ?? 'Filter'}
                </GhostBtn>
                {filterOpen && (
                  <div
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: 'calc(100% + 4px)',
                      zIndex: 20,
                      background: 'var(--bg)',
                      border: '1px solid var(--border-md)',
                      borderRadius: 8,
                      boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
                      minWidth: 120,
                      overflow: 'hidden',
                    }}
                  >
                    {FILTERS.map(({ value, label }) => (
                      <button
                        key={value}
                        onClick={() => { setFilter(value); setFilterOpen(false); }}
                        style={{
                          display: 'block',
                          width: '100%',
                          padding: '8px 14px',
                          textAlign: 'left',
                          border: 'none',
                          background: filter === value ? 'rgba(24,226,153,0.08)' : 'transparent',
                          color: filter === value ? '#0fa76e' : 'var(--fg2)',
                          fontFamily: 'var(--sans)',
                          fontSize: 13,
                          fontWeight: filter === value ? 500 : 400,
                          cursor: 'pointer',
                        }}
                      >
                        {label}
                        <span style={{ float: 'right', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)' }}>
                          {countByStatus(entries, value)}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
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
          highlightId={highlightId}
          activeFilter={filter}
          hasSearch={!!search.trim()}
          dark={dark}
          onMarkDone={handleMarkDone}
          onEdit={(entry) => setEditEntry(entry)}
          onStart={handleStart}
          onMoveUp={handleMoveUp}
          onMoveDown={handleMoveDown}
          onShowDetail={(entry) => setDetailEntry(entry)}
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

      {/* Detail modal */}
      {detailEntry && (
        <DetailModal
          entry={detailEntry}
          dark={dark}
          onClose={() => setDetailEntry(null)}
        />
      )}

      {/* Stats modal */}
      {statsOpen && (
        <StatsModal
          entries={entries}
          onClose={() => setStatsOpen(false)}
        />
      )}

      {/* Toast notifications */}
      {toast && <Toast toast={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
