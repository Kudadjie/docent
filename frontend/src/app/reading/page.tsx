'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useDarkMode } from '@/hooks/useDarkMode';
import { RefreshCw, Download, Printer, Search, Filter, HelpCircle, BookOpen, ArrowRight, BarChart2, ArrowUpDown, AlertTriangle, Info, X, Trash2, BookmarkCheck } from 'lucide-react';

import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import PaperTable from '@/components/PaperTable';
import HowToAddModal from '@/components/HowToAddModal';
import EditModal, { type EditFields } from '@/components/EditModal';
import StatsModal from '@/components/StatsModal';
import DetailModal from '@/components/DetailModal';
import Toast, { type ToastData } from '@/components/Toast';
import type { QueueData, QueueEntry, FilterValue, BannerCounts } from '@/lib/types';
import { useTour } from '@/hooks/useTour';
import { extractMessage } from '@/lib/toast-utils';

// ── Hooks ─────────────────────────────────────────────────────────
function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState<T>(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

// ── Types ─────────────────────────────────────────────────────────
type SortBy = 'order' | 'date-newest' | 'date-oldest' | 'deadline' | 'status';
type QuickFilter = 'has-deadline' | 'past-due' | 'not-in-library';

// ── Helpers ──────────────────────────────────────────────────────
function applyFilter(entries: QueueEntry[], filter: FilterValue): QueueEntry[] {
  if (filter === 'all') return entries.filter(e => e.status !== 'removed');
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

function applyQuickFilter(entries: QueueEntry[], quick: Set<QuickFilter>): QueueEntry[] {
  if (quick.size === 0) return entries;
  return entries.filter(e => {
    if (quick.has('has-deadline') && !e.deadline) return false;
    if (quick.has('past-due') && (!e.deadline || new Date(e.deadline).getTime() >= Date.now())) return false;
    if (quick.has('not-in-library') && !e.not_in_mendeley && !e.manually_kept && !e.not_in_parent_collection) return false;
    return true;
  });
}

function applySort(entries: QueueEntry[], sortBy: SortBy): QueueEntry[] {
  switch (sortBy) {
    case 'order':
      return [
        ...entries.filter(e => e.status !== 'done' && e.status !== 'removed').sort((a, b) => a.order - b.order),
        ...entries.filter(e => e.status === 'done'),
        ...entries.filter(e => e.status === 'removed'),
      ];
    case 'date-newest':
      return [...entries].sort((a, b) => new Date(b.added).getTime() - new Date(a.added).getTime());
    case 'date-oldest':
      return [...entries].sort((a, b) => new Date(a.added).getTime() - new Date(b.added).getTime());
    case 'deadline':
      return [...entries].sort((a, b) => {
        if (!a.deadline && !b.deadline) return 0;
        if (!a.deadline) return 1;
        if (!b.deadline) return -1;
        return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
      });
    case 'status': {
      const order: Record<string, number> = { reading: 0, queued: 1, done: 2, removed: 3 };
      return [...entries].sort((a, b) => (order[a.status] ?? 4) - (order[b.status] ?? 4));
    }
    default:
      return entries;
  }
}

const STATUS_FILTERS: { value: FilterValue; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'reading', label: 'Reading' },
  { value: 'queued', label: 'Queued' },
  { value: 'done', label: 'Done' },
];

// Keep legacy alias
const FILTERS = STATUS_FILTERS;

function countByStatus(entries: QueueEntry[], status: FilterValue): number {
  if (status === 'all') return entries.filter(e => e.status !== 'removed').length;
  return entries.filter((e) => e.status === status).length;
}

const SORT_OPTIONS: { value: SortBy; label: string }[] = [
  { value: 'order', label: 'Reading order' },
  { value: 'date-newest', label: 'Newest added' },
  { value: 'date-oldest', label: 'Oldest added' },
  { value: 'deadline', label: 'Deadline (soonest)' },
  { value: 'status', label: 'Status' },
];

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
  const { dark, toggleDark } = useDarkMode();

  useTour('reading', [
    {
      element: 'table[aria-label="Reading queue"]',
      popover: {
        title: 'Your reading queue',
        description: 'Documents synced from your reference manager live here, ranked by reading priority. Each entry shows its status, deadline, and tags.',
      },
    },
    {
      element: 'div[role="tablist"][aria-label="Filter by status"]',
      popover: {
        title: 'Filter by status',
        description: 'Switch between Queued (to read), Reading (in progress), and Done. Use "All" to see your full history.',
      },
    },
    {
      element: 'input[aria-label="Search entries"]',
      popover: {
        title: 'Search your queue',
        description: 'Search across titles, authors, categories, and tags in real time. Combine with status filters to zero in on any document.',
      },
    },
    {
      element: '#docent-sync-btn',
      popover: {
        title: 'Sync your library',
        description: 'Pull new documents from your reference manager. Documents removed from your library are flagged — not deleted — so you decide what stays.',
      },
    },
  ]);
  const [data, setData] = useState<QueueData | null>(null);
  const [filter, setFilter] = useState<FilterValue>('all');
  const [search, setSearch] = useState('');
  const [newIds] = useState<Set<string>>(new Set());
  const [showInfo, setShowInfo] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastData | null>(null);
  const [editEntry, setEditEntry] = useState<QueueEntry | null>(null);
  const [detailEntry, setDetailEntry] = useState<QueueEntry | null>(null);
  const [statsOpen, setStatsOpen] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [urlReady, setUrlReady] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [sortOpen, setSortOpen] = useState(false);
  const [sortBy, setSortBy] = useState<SortBy>('order');
  const [quickFilters, setQuickFilters] = useState<Set<QuickFilter>>(new Set());
  const [serverError, setServerError] = useState(false);
  const [queueCollection, setQueueCollection] = useState<string>('Docent-Queue');
  const [refManagerName, setRefManagerName] = useState<string>('Mendeley');
  const [flaggedModal, setFlaggedModal] = useState(false);
  const [parentFlaggedModal, setParentFlaggedModal] = useState(false);
  const [dbModal, setDbModal] = useState(false);
  const [dbData, setDbData] = useState<{ database_dir: string | null; pdfs: string[]; last_checked: string } | null>(null);
  const [dbLoading, setDbLoading] = useState(false);
  const filterRef = useRef<HTMLDivElement>(null);
  const sortRef = useRef<HTMLDivElement>(null);
  const autoSyncedRef = useRef(false);

  // Fetch queue
  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/queue');
      if (res.ok) {
        setData(await res.json());
        setServerError(false);
      } else {
        setServerError(true);
      }
    } catch {
      setServerError(true);
    }
  }, []);

  // Parallel fetch on mount — queue + config in one round-trip window.
  useEffect(() => {
    Promise.all([
      fetch('/api/queue').then(r => r.json()).catch(() => null),
      fetch('/api/config').then(r => r.json()).catch(() => null),
    ]).then(([queueJson, configJson]) => {
      if (queueJson) {
        setData(queueJson as QueueData);
        setServerError(false);
      } else {
        setServerError(true);
      }
      if (configJson) {
        const d = configJson as { reading: { queue_collection?: string; reference_manager?: string } };
        if (d.reading?.queue_collection) setQueueCollection(d.reading.queue_collection);
        if (d.reading?.reference_manager) {
          const name = d.reading.reference_manager;
          setRefManagerName(name.charAt(0).toUpperCase() + name.slice(1));
        }
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Read filter + search from URL on mount; fall back to sessionStorage
  useEffect(() => {
    queueMicrotask(() => {
      const params = new URLSearchParams(window.location.search);
      const VALID_FILTERS = ['all', 'reading', 'queued', 'done', 'removed'];

      const urlFilter = params.get('filter');
      if (urlFilter && VALID_FILTERS.includes(urlFilter)) {
        setFilter(urlFilter as FilterValue);
      } else {
        try {
          const stored = sessionStorage.getItem('docent:reading:filter');
          if (stored && VALID_FILTERS.includes(stored)) setFilter(stored as FilterValue);
        } catch {}
      }

      const urlQ = params.get('q');
      if (urlQ) {
        setSearch(urlQ);
      } else {
        try {
          const stored = sessionStorage.getItem('docent:reading:search');
          if (stored) setSearch(stored);
        } catch {}
      }

      const urlSort = params.get('sort');
      if (urlSort && ['order', 'date-newest', 'date-oldest', 'deadline', 'status'].includes(urlSort)) {
        setSortBy(urlSort as SortBy);
      }

      setUrlReady(true);
    });
  }, []);

  // Write filter + search to URL and sessionStorage whenever they change
  useEffect(() => {
    if (!urlReady) return;
    const params = new URLSearchParams();
    if (filter !== 'all') params.set('filter', filter);
    if (search) params.set('q', search);
    if (sortBy !== 'order') params.set('sort', sortBy);
    const qs = params.toString();
    window.history.replaceState(null, '', qs ? `?${qs}` : window.location.pathname);
    try {
      sessionStorage.setItem('docent:reading:filter', filter);
      if (search) sessionStorage.setItem('docent:reading:search', search);
      else sessionStorage.removeItem('docent:reading:search');
    } catch {}
  }, [filter, search, sortBy, urlReady]);

  // Close filter/sort dropdowns on outside click
  useEffect(() => {
    if (!filterOpen && !sortOpen) return;
    function handle(e: MouseEvent) {
      if (filterRef.current && !filterRef.current.contains(e.target as Node)) setFilterOpen(false);
      if (sortRef.current && !sortRef.current.contains(e.target as Node)) setSortOpen(false);
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [filterOpen, sortOpen]);

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
          const clean = extractMessage((body.stdout ?? '').replace(/\x1b\[[0-9;]*m/g, '').trim());
          setToast({ type: 'success', message: clean.slice(0, 160) || `${refManagerName} sync complete.` });
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
        if (/\d+ added.*?\d+ unchanged/.test(stdout)) {
          setToast({ type: 'success', message: toastSuccess(action, stdout) });
        } else {
          const clean = extractMessage(stdout.replace(/\x1b\[[0-9;]*m/g, '').trim());
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
      // stdout: "X added, Y unchanged[, Z flagged (...)][, W cleared (...)], N failed."
      if (/\d+ added.*?\d+ unchanged/.test(stdout)) {
        const addedM = stdout.match(/(\d+) added/);
        const flaggedM = stdout.match(/(\d+) flagged/);
        const clearedM = stdout.match(/(\d+) cleared/);
        const parts: string[] = [];
        const added = addedM ? Number(addedM[1]) : 0;
        const flagged = flaggedM ? Number(flaggedM[1]) : 0;
        const cleared = clearedM ? Number(clearedM[1]) : 0;
        if (added > 0) parts.push(`${added} added`);
        if (flagged > 0) parts.push(`${flagged} flagged`);
        if (cleared > 0) parts.push(`${cleared} returned`);
        if (parts.length === 0) parts.push('Nothing changed');
        return `${refManagerName} sync — ${parts.join(', ')}.`;
      }
      // CLI exited 0 but printed a warning (wrong collection name, auth issue, etc.)
      const clean = extractMessage(stdout.replace(/\x1b\[[0-9;]*m/g, '').trim());
      if (clean) return clean.slice(0, 160);
      return `${refManagerName} sync complete.`;
    }
    if (action === 'scan')   return 'Folder scan complete.';
    if (action === 'done')   return 'Marked as done.';
    if (action === 'start')  return 'Marked as reading.';
    if (action === 'edit')      return 'Entry updated.';
    if (action === 'move-up')   return 'Moved up.';
    if (action === 'move-down') return 'Moved down.';
    if (action === 'remove') return 'Removed from queue.';
    if (action === 'clear-library-flag') return 'Kept in queue.';
    return 'Done.';
  }

  function toastError(action: string, detail: string): string {
    const label: Record<string, string> = {
      sync:   `${refManagerName} sync failed`,
      scan:   'Scan failed',
      done:   'Could not mark done',
      start:  'Could not start entry',
      edit:        'Could not update entry',
      'move-up':   'Could not move up',
      'move-down': 'Could not move down',
      'remove':    'Could not remove entry',
      'clear-library-flag': 'Could not clear flag',
    };
    // Strip ANSI codes, then extract human message (guards against raw JSON bodies)
    const clean = extractMessage(detail.replace(/\x1b\[[0-9;]*m/g, '').trim());
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

  async function handleReorder(id: string, newRank: number) {
    await runAction('edit', id, { order: newRank });
  }

  async function fetchDbData() {
    setDbLoading(true);
    try {
      const res = await fetch('/api/database');
      if (res.ok) setDbData(await res.json());
    } catch {}
    finally { setDbLoading(false); }
  }

  function handleOpenDatabase() {
    setDbModal(true);
    fetchDbData();
  }

  async function handleClearLibraryFlag(id: string) {
    await runAction('clear-library-flag', id);
  }

  async function handleRemoveEntry(id: string) {
    await runAction('remove', id);
  }

  function handleNext() {
    const queued = entries
      .filter(e => e.status === 'queued')
      .sort((a, b) => a.order - b.order);
    if (queued.length === 0) {
      setToast({ type: 'error', message: 'No queued entries.' });
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

      const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
      const blobUrl = URL.createObjectURL(blob);
      const w = window.open(blobUrl, '_blank');
      if (!w) {
        URL.revokeObjectURL(blobUrl);
        setToast({ type: 'error', message: 'Pop-up blocked — allow pop-ups to export as PDF.' });
        return;
      }
      // Revoke after the window has had time to load and print
      setTimeout(() => { w.focus(); w.print(); URL.revokeObjectURL(blobUrl); }, 500);
      setToast({ type: 'success', message: `Opened print dialog for ${qdata.entries.length} entries.` });
    } catch {
      setToast({ type: 'error', message: 'Export failed.' });
    }
  }

  const entries: QueueEntry[] = data?.entries ?? [];
  const banner: BannerCounts = data?.banner ?? { queued: 0, reading: 0, done: 0 };
  const flaggedEntries = entries.filter(e => e.not_in_mendeley && e.status !== 'removed');
  const parentFlaggedEntries = entries.filter(e => e.not_in_parent_collection && e.status !== 'removed');

  // Debounce search so filter runs at most every 150 ms while the user types.
  const debouncedSearch = useDebounce(search, 150);

  // Memoize the expensive filter+sort pipeline so it only reruns when inputs change.
  // eslint-disable-next-line react-hooks/preserve-manual-memoization
  const filtered = useMemo(() => applySort(
    applyQuickFilter(
      // eslint-disable-next-line react-hooks/preserve-manual-memoization
      applySearch(applyFilter([...entries], filter), debouncedSearch),
      quickFilters,
    ),
    sortBy,
  ), [entries, filter, debouncedSearch, quickFilters, sortBy]);

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
        {/* Server error notice */}
        {serverError && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              padding: '9px 20px',
              background: 'rgba(212,86,86,0.08)',
              borderBottom: '1px solid rgba(212,86,86,0.2)',
              flexShrink: 0,
            }}
          >
            <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: '#D45656' }}>
              Something doesn&apos;t seem right - the server may be unavailable.
            </span>
            <button
              onClick={() => { setServerError(false); refresh(); }}
              style={{
                fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
                color: '#D45656', background: 'transparent', border: '1px solid rgba(212,86,86,0.35)',
                borderRadius: 6, padding: '3px 10px', cursor: 'pointer', whiteSpace: 'nowrap',
              }}
            >
              Try refreshing
            </button>
          </div>
        )}

        {/* Status banner */}
        <StatusBanner
          dark={dark}
          onToggleDark={toggleDark}
          dotState={busy === 'sync' || busy === 'refresh' ? 'working' : 'idle'}
          banner={banner}
          lastUpdated={data?.last_updated ?? null}
          databaseCount={data?.database_count ?? null}
          onOpenDatabase={handleOpenDatabase}
        />

        {/* Not-in-library warning banner */}
        {flaggedEntries.length > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            gap: 12, padding: '8px 20px', flexShrink: 0,
            background: 'rgba(195,125,13,0.08)', borderBottom: '1px solid rgba(195,125,13,0.2)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <AlertTriangle size={13} strokeWidth={2} color="#C37D0D" />
              <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: '#C37D0D' }}>
                {flaggedEntries.length} {flaggedEntries.length === 1 ? 'entry is' : 'entries are'} no longer in your {refManagerName} collection.
              </span>
            </div>
            <button
              onClick={() => setFlaggedModal(true)}
              style={{
                fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
                color: '#C37D0D', background: 'transparent',
                border: '1px solid rgba(195,125,13,0.35)',
                borderRadius: 6, padding: '3px 10px', cursor: 'pointer', whiteSpace: 'nowrap',
              }}
            >
              Review
            </button>
          </div>
        )}

        {/* Sub-collection-only warning banner */}
        {parentFlaggedEntries.length > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            gap: 12, padding: '8px 20px', flexShrink: 0,
            background: 'rgba(59,130,246,0.06)', borderBottom: '1px solid rgba(59,130,246,0.15)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Info size={13} strokeWidth={2} color="#3B82F6" style={{ flexShrink: 0 }} />
              <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg1)' }}>
                <strong style={{ fontWeight: 500 }}>
                  {parentFlaggedEntries.length} {parentFlaggedEntries.length === 1 ? 'entry' : 'entries'}
                </strong>
                {' '}
                <span style={{ color: 'var(--fg3)' }}>
                  {parentFlaggedEntries.length === 1 ? 'is' : 'are'} in a sub-collection but no longer in the parent <strong style={{ fontWeight: 500, color: 'var(--fg2)' }}>{queueCollection}</strong> collection.
                </span>
              </span>
            </div>
            <button
              onClick={() => setParentFlaggedModal(true)}
              style={{
                fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
                color: 'var(--fg2)', background: 'transparent',
                border: '1px solid var(--border-md)',
                borderRadius: 6, padding: '3px 10px', cursor: 'pointer', whiteSpace: 'nowrap',
              }}
            >
              Review
            </button>
          </div>
        )}

        {/* Page header */}
        <div
          style={{
            position: 'relative',
            padding: '20px 24px 0',
            borderBottom: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
          <div aria-hidden className="hero-wash" />
          {/* Title row */}
          <div
            style={{
              position: 'relative',
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
              <span title={`Entries are added and removed by syncing with ${refManagerName}. Docent does not edit your library.`}>
                managed via {refManagerName}
              </span>
              </p>
            </div>

            {/* How to add button */}
            <button
              onClick={() => setShowInfo(true)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 14px', borderRadius: 9999, border: '1px solid #8B5CF6', background: '#8B5CF6', color: '#ffffff', fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, cursor: 'pointer', whiteSpace: 'nowrap' }}
            >
              <HelpCircle size={14} strokeWidth={1.5} />
              How to add?
            </button>
          </div>

          {/* Action bar */}
          <div
            style={{
              position: 'relative',
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
                onClick={async () => {
                  setBusy('refresh');
                  const [,] = await Promise.all([refresh(), new Promise(r => setTimeout(r, 1500))]);
                  setBusy(null);
                }}
              >
                {busy === 'refresh' ? 'Refreshing…' : 'Refresh'}
              </GhostBtn>
              <button
                id="docent-sync-btn"
                onClick={handleSync}
                disabled={busy === 'sync'}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '4px 14px', borderRadius: 9999, border: '1px solid #18E299', background: '#18E299', color: '#0a1f15', fontFamily: 'var(--sans)', cursor: busy === 'sync' ? 'wait' : 'pointer', whiteSpace: 'nowrap' }}
              >
                <RefreshCw
                  size={13}
                  strokeWidth={2}
                  style={{ animation: busy === 'sync' ? 'spin 0.75s linear infinite' : 'none', flexShrink: 0 }}
                />
                <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.2 }}>
                    {busy === 'sync' ? 'Syncing…' : 'Sync'}
                  </span>
                  {busy !== 'sync' && (
                    <span style={{ fontSize: 9, fontWeight: 400, opacity: 0.65, lineHeight: 1.2 }}>
                      from {refManagerName}
                    </span>
                  )}
                </span>
              </button>
              <GhostBtn icon={<Printer size={14} strokeWidth={1.5} />} onClick={handleExport}>
                Export Documents
              </GhostBtn>
              <GhostBtn icon={<ArrowRight size={14} strokeWidth={1.5} />} onClick={handleNext}>
                Next
              </GhostBtn>
              <GhostBtn icon={<BarChart2 size={14} strokeWidth={1.5} />} onClick={() => setStatsOpen(true)}>
                Stats
              </GhostBtn>
            </div>

            {/* Right: search + sort + filter */}
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
                    background: 'var(--bg-card)',
                    outline: 'none',
                  }}
                />
              </div>

              {/* Sort dropdown */}
              <div ref={sortRef} style={{ position: 'relative' }}>
                <GhostBtn
                  icon={<ArrowUpDown size={14} strokeWidth={1.5} />}
                  onClick={() => { setSortOpen(o => !o); setFilterOpen(false); }}
                  active={sortBy !== 'order'}
                >
                  {sortBy === 'order' ? 'Sort' : (SORT_OPTIONS.find(s => s.value === sortBy)?.label ?? 'Sort')}
                </GhostBtn>
                {sortOpen && (
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
                      minWidth: 170,
                      overflow: 'hidden',
                    }}
                  >
                    <div style={{ padding: '6px 14px 4px', fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--fg4)', letterSpacing: '0.6px', textTransform: 'uppercase' }}>Sort by</div>
                    {SORT_OPTIONS.map(({ value, label }) => (
                      <button
                        key={value}
                        onClick={() => { setSortBy(value); setSortOpen(false); }}
                        style={{
                          display: 'block', width: '100%', padding: '8px 14px',
                          textAlign: 'left', border: 'none',
                          background: sortBy === value ? 'rgba(24,226,153,0.08)' : 'transparent',
                          color: sortBy === value ? '#0fa76e' : 'var(--fg2)',
                          fontFamily: 'var(--sans)', fontSize: 13,
                          fontWeight: sortBy === value ? 500 : 400, cursor: 'pointer',
                        }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Filter dropdown */}
              <div ref={filterRef} style={{ position: 'relative' }}>
                <GhostBtn
                  icon={<Filter size={14} strokeWidth={1.5} />}
                  onClick={() => { setFilterOpen(o => !o); setSortOpen(false); }}
                  active={filter !== 'all' || quickFilters.size > 0}
                >
                  {filter === 'all' && quickFilters.size === 0
                    ? 'Filter'
                    : filter !== 'all'
                    ? FILTERS.find(f => f.value === filter)?.label ?? 'Filter'
                    : `Filter (${quickFilters.size})`}
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
                      minWidth: 160,
                      overflow: 'hidden',
                    }}
                  >
                    {/* Status filters */}
                    <div style={{ padding: '6px 14px 4px', fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--fg4)', letterSpacing: '0.6px', textTransform: 'uppercase' }}>Status</div>
                    {FILTERS.map(({ value, label }) => (
                      <button
                        key={value}
                        onClick={() => { setFilter(value); setFilterOpen(false); }}
                        style={{
                          display: 'block', width: '100%', padding: '7px 14px',
                          textAlign: 'left', border: 'none',
                          background: filter === value ? 'rgba(24,226,153,0.08)' : 'transparent',
                          color: filter === value ? '#0fa76e' : 'var(--fg2)',
                          fontFamily: 'var(--sans)', fontSize: 13,
                          fontWeight: filter === value ? 500 : 400, cursor: 'pointer',
                        }}
                      >
                        {label}
                        <span style={{ float: 'right', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)' }}>
                          {countByStatus(entries, value)}
                        </span>
                      </button>
                    ))}

                    {/* Quick filters */}
                    <div style={{ margin: '4px 14px', borderTop: '1px solid var(--border)' }} />
                    <div style={{ padding: '2px 14px 4px', fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--fg4)', letterSpacing: '0.6px', textTransform: 'uppercase' }}>Quick filters</div>
                    {([
                      { key: 'has-deadline' as QuickFilter, label: 'Has deadline' },
                      { key: 'past-due' as QuickFilter, label: 'Past due' },
                      { key: 'not-in-library' as QuickFilter, label: 'Not in library', count: flaggedEntries.length + parentFlaggedEntries.length },
                    ]).map(({ key, label, count }) => {
                      const active = quickFilters.has(key);
                      return (
                        <button
                          key={key}
                          onClick={() => {
                            setQuickFilters(prev => {
                              const next = new Set(prev);
                              if (next.has(key)) next.delete(key); else next.add(key);
                              return next;
                            });
                          }}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 8,
                            width: '100%', padding: '7px 14px',
                            textAlign: 'left', border: 'none',
                            background: active ? 'rgba(24,226,153,0.08)' : 'transparent',
                            color: active ? '#0fa76e' : 'var(--fg2)',
                            fontFamily: 'var(--sans)', fontSize: 13,
                            fontWeight: active ? 500 : 400, cursor: 'pointer',
                          }}
                        >
                          <span style={{
                            width: 14, height: 14, borderRadius: 3, flexShrink: 0,
                            border: `1.5px solid ${active ? '#18E299' : 'var(--border-md)'}`,
                            background: active ? '#18E299' : 'transparent',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                          }}>
                            {active && <span style={{ width: 6, height: 6, borderRadius: 1, background: '#0a1f15' }} />}
                          </span>
                          {label}
                          {count !== undefined && count > 0 && (
                            <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 10, color: '#C37D0D' }}>{count}</span>
                          )}
                        </button>
                      );
                    })}
                    {quickFilters.size > 0 && (
                      <button
                        onClick={() => { setQuickFilters(new Set()); setFilterOpen(false); }}
                        style={{
                          display: 'block', width: '100%', padding: '6px 14px 8px',
                          textAlign: 'left', border: 'none', background: 'transparent',
                          color: 'var(--fg4)', fontFamily: 'var(--sans)', fontSize: 11,
                          cursor: 'pointer',
                        }}
                      >
                        Clear quick filters
                      </button>
                    )}
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
                    background: isActive ? 'rgba(24,226,153,0.06)' : 'transparent',
                    borderRadius: '6px 6px 0 0',
                    fontFamily: 'var(--sans)',
                    fontSize: 13,
                    fontWeight: isActive ? 500 : 400,
                    color: isActive ? 'var(--fg1)' : 'var(--fg4)',
                    cursor: 'pointer',
                    transition: 'background 0.12s',
                  }}
                >
                  {label}
                  <span
                    style={{
                      fontFamily: 'var(--mono)',
                      fontSize: 10,
                      padding: '1px 6px',
                      borderRadius: 9999,
                      background: isActive ? '#18E2991c' : 'transparent',
                      color: isActive ? '#0fa76e' : 'var(--fg4)',
                      transition: 'all 0.12s',
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
        <div style={{ flex: 1, overflow: 'hidden', background: 'var(--bg-card)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
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
            onReorder={handleReorder}
          />
        </div>
      </main>

      {/* Info modal */}
      {showInfo && <HowToAddModal onClose={() => setShowInfo(false)} collectionName={queueCollection} />}

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

      {/* Database folder inspector modal */}
      {dbModal && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 50, background: 'var(--overlay)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}
          onClick={(e) => { if (e.target === e.currentTarget) setDbModal(false); }}
        >
          <div style={{ background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border-md)', boxShadow: '0 16px 48px rgba(0,0,0,0.3)', width: '100%', maxWidth: 560, maxHeight: '82vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

            {/* Header */}
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontFamily: 'var(--sans)', fontSize: 15, fontWeight: 600, color: 'var(--fg1)' }}>Watch folder</div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)', marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {dbData?.database_dir ?? 'Not configured'}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                <button
                  onClick={fetchDbData}
                  disabled={dbLoading}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 6, border: '1px solid var(--border-md)', background: 'transparent', color: 'var(--fg3)', fontFamily: 'var(--sans)', fontSize: 12, cursor: dbLoading ? 'wait' : 'pointer' }}
                >
                  <RefreshCw size={12} strokeWidth={1.5} style={dbLoading ? { animation: 'spin 0.75s linear infinite' } : {}} />
                  {dbLoading ? 'Scanning…' : 'Refresh'}
                </button>
                <button onClick={() => setDbModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--fg4)', display: 'flex' }}>
                  <X size={16} strokeWidth={1.5} />
                </button>
              </div>
            </div>

            {/* Info note */}
            <div style={{ padding: '10px 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-subtle)', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              <Info size={13} strokeWidth={1.5} color="var(--fg4)" style={{ flexShrink: 0, marginTop: 1 }} />
              <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.5 }}>
                PDFs dropped here are auto-imported by {refManagerName}. Docent counts files but cannot reliably match filenames to queue entries — check {refManagerName} to see which entries have PDFs attached.
              </span>
            </div>

            {/* Count pill */}
            <div style={{ padding: '10px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 700, color: 'var(--fg1)' }}>
                {dbData?.pdfs.length ?? '—'}
              </span>
              <span style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)' }}>PDF{(dbData?.pdfs.length ?? 0) !== 1 ? 's' : ''} in folder</span>
              {dbData?.last_checked && (
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', marginLeft: 'auto' }}>
                  checked {new Date(dbData.last_checked).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>

            {/* Filename list */}
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {dbLoading && !dbData && (
                <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--fg4)', fontFamily: 'var(--sans)', fontSize: 13 }}>Scanning folder…</div>
              )}
              {!dbData?.database_dir && !dbLoading && (
                <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--fg4)', fontFamily: 'var(--sans)', fontSize: 13 }}>
                  No watch folder configured — set one in Settings → Reading.
                </div>
              )}
              {dbData?.pdfs.length === 0 && dbData.database_dir && (
                <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--fg4)', fontFamily: 'var(--sans)', fontSize: 13 }}>
                  No PDFs found in this folder.
                </div>
              )}
              {(dbData?.pdfs ?? []).map((pdf, i) => (
                <div
                  key={pdf}
                  style={{
                    padding: '7px 20px',
                    borderBottom: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', gap: 10,
                    background: i % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.015)',
                  }}
                >
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', minWidth: 28, textAlign: 'right', flexShrink: 0 }}>{i + 1}</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{pdf}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Sub-collection-only review modal */}
      {parentFlaggedModal && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 50,
            background: 'var(--overlay)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 24,
          }}
          onClick={(e) => { if (e.target === e.currentTarget) setParentFlaggedModal(false); }}
        >
          <div style={{
            background: 'var(--bg-card)', borderRadius: 12,
            border: '1px solid var(--border-md)',
            boxShadow: '0 16px 48px rgba(0,0,0,0.3)',
            width: '100%', maxWidth: 600, maxHeight: '82vh',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            {/* Header */}
            <div style={{
              padding: '16px 20px', borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12,
            }}>
              <div>
                <div style={{ fontFamily: 'var(--sans)', fontSize: 15, fontWeight: 600, color: 'var(--fg1)' }}>
                  Sub-collection only
                </div>
                <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', marginTop: 2, lineHeight: 1.5 }}>
                  These entries are in a sub-collection but were removed from the parent <strong style={{ color: 'var(--fg2)' }}>{queueCollection}</strong> collection.
                  Docent still tracks them because it syncs all sub-collections. You have two options.
                </div>
              </div>
              <button onClick={() => setParentFlaggedModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--fg4)', display: 'flex', flexShrink: 0 }}>
                <X size={16} strokeWidth={1.5} />
              </button>
            </div>

            {/* Instructions */}
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-subtle)' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={{ padding: '12px 14px', borderRadius: 8, border: '1px solid rgba(99,102,241,0.2)', background: 'rgba(99,102,241,0.05)' }}>
                  <div style={{ fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 600, color: '#6366F1', marginBottom: 6 }}>
                    Option A — Add back to parent
                  </div>
                  <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.55 }}>
                    In Mendeley, drag the entry into the <strong style={{ color: 'var(--fg2)' }}>{queueCollection}</strong> collection directly (not just a sub-collection). Re-sync when done.
                  </div>
                </div>
                <div style={{ padding: '12px 14px', borderRadius: 8, border: '1px solid rgba(212,86,86,0.2)', background: 'rgba(212,86,86,0.04)' }}>
                  <div style={{ fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 600, color: '#D45656', marginBottom: 6 }}>
                    Option B — Remove entirely
                  </div>
                  <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.55 }}>
                    In Mendeley, right-click the entry and choose <em>Remove from collection</em> for each sub-collection it belongs to. Re-sync when done.
                  </div>
                </div>
              </div>
            </div>

            {/* Entry list */}
            <div style={{ overflowY: 'auto', flex: 1, padding: '8px 0' }}>
              {parentFlaggedEntries.map(entry => (
                <div
                  key={entry.id}
                  style={{
                    padding: '10px 20px', borderBottom: '1px solid var(--border)',
                  }}
                >
                  <div style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {entry.title || entry.id}
                  </div>
                  <div style={{ display: 'flex', gap: 10, marginTop: 3, flexWrap: 'wrap' }}>
                    {entry.authors && (
                      <span style={{ fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg4)' }}>{entry.authors}</span>
                    )}
                    {entry.category && (
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#6366F1', background: 'rgba(99,102,241,0.08)', padding: '1px 7px', borderRadius: 9999 }}>
                        {entry.category}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Footer */}
            <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setParentFlaggedModal(false)}
                style={{
                  fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                  color: 'var(--fg2)', background: 'var(--gray100)',
                  border: '1px solid var(--border-md)',
                  borderRadius: 8, padding: '6px 16px', cursor: 'pointer',
                }}
              >
                Close — I&apos;ll fix it in {refManagerName}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Not-in-library review modal */}
      {flaggedModal && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 50,
            background: 'var(--overlay)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 24,
          }}
          onClick={(e) => { if (e.target === e.currentTarget) setFlaggedModal(false); }}
        >
          <div style={{
            background: 'var(--bg-card)', borderRadius: 12,
            border: '1px solid var(--border-md)',
            boxShadow: '0 16px 48px rgba(0,0,0,0.3)',
            width: '100%', maxWidth: 560, maxHeight: '80vh',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            {/* Header */}
            <div style={{
              padding: '16px 20px', borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div>
                <div style={{ fontFamily: 'var(--sans)', fontSize: 15, fontWeight: 600, color: 'var(--fg1)' }}>
                  Not in library
                </div>
                <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', marginTop: 2 }}>
                  These entries are no longer in your {refManagerName} collection. Remove or keep them.
                </div>
              </div>
              <button onClick={() => setFlaggedModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--fg4)', display: 'flex' }}>
                <X size={16} strokeWidth={1.5} />
              </button>
            </div>

            {/* Entry list */}
            <div style={{ overflowY: 'auto', flex: 1, padding: '8px 0' }}>
              {flaggedEntries.length === 0 ? (
                <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--fg4)', fontFamily: 'var(--sans)', fontSize: 13 }}>
                  All clear — no flagged entries.
                </div>
              ) : (
                flaggedEntries.map(entry => (
                  <div
                    key={entry.id}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 12,
                      padding: '10px 20px', borderBottom: '1px solid var(--border)',
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {entry.title || entry.id}
                      </div>
                      {entry.authors && (
                        <div style={{ fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg4)', marginTop: 2 }}>
                          {entry.authors}
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                      <button
                        onClick={async () => {
                          await handleClearLibraryFlag(entry.id);
                          if (flaggedEntries.length <= 1) setFlaggedModal(false);
                        }}
                        title="Keep in queue"
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                          padding: '4px 10px', borderRadius: 6,
                          border: '1px solid var(--border-md)',
                          background: 'transparent', color: 'var(--fg2)',
                          fontFamily: 'var(--sans)', fontSize: 12, cursor: 'pointer',
                        }}
                      >
                        <BookmarkCheck size={12} strokeWidth={1.5} />
                        Keep
                      </button>
                      <button
                        onClick={async () => {
                          await handleRemoveEntry(entry.id);
                          if (flaggedEntries.length <= 1) setFlaggedModal(false);
                        }}
                        title="Remove from queue"
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                          padding: '4px 10px', borderRadius: 6,
                          border: '1px solid rgba(212,86,86,0.3)',
                          background: 'rgba(212,86,86,0.08)', color: '#D45656',
                          fontFamily: 'var(--sans)', fontSize: 12, cursor: 'pointer',
                        }}
                      >
                        <Trash2 size={12} strokeWidth={1.5} />
                        Remove
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
