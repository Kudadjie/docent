import { useState, useEffect } from 'react';
import type { QueueEntry, FilterValue } from '@/lib/types';

export type SortBy = 'order' | 'date-newest' | 'date-oldest' | 'deadline' | 'status';
export type QuickFilter = 'has-deadline' | 'past-due' | 'not-in-library';

export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState<T>(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export function applyFilter(entries: QueueEntry[], filter: FilterValue): QueueEntry[] {
  if (filter === 'all') return entries.filter(e => e.status !== 'removed');
  return entries.filter((e) => e.status === filter);
}

export function applySearch(entries: QueueEntry[], q: string): QueueEntry[] {
  if (!q.trim()) return entries;
  const lower = q.toLowerCase();
  return entries.filter((e) =>
    [e.title, e.authors, e.notes, e.category ?? '', e.id, ...e.tags]
      .join(' ')
      .toLowerCase()
      .includes(lower)
  );
}

export function applyQuickFilter(entries: QueueEntry[], quick: Set<QuickFilter>): QueueEntry[] {
  if (quick.size === 0) return entries;
  return entries.filter(e => {
    if (quick.has('has-deadline') && !e.deadline) return false;
    if (quick.has('past-due') && (!e.deadline || new Date(e.deadline).getTime() >= Date.now())) return false;
    if (quick.has('not-in-library') && !e.not_in_library && !e.manually_kept && !e.not_in_parent_collection) return false;
    return true;
  });
}

export function applySort(entries: QueueEntry[], sortBy: SortBy): QueueEntry[] {
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

export function countByStatus(entries: QueueEntry[], status: FilterValue): number {
  if (status === 'all') return entries.filter(e => e.status !== 'removed').length;
  return entries.filter((e) => e.status === status).length;
}

export const STATUS_FILTERS: { value: FilterValue; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'reading', label: 'Reading' },
  { value: 'queued', label: 'Queued' },
  { value: 'done', label: 'Done' },
];

export const FILTERS = STATUS_FILTERS;

export const SORT_OPTIONS: { value: SortBy; label: string }[] = [
  { value: 'order', label: 'Reading order' },
  { value: 'date-newest', label: 'Newest added' },
  { value: 'date-oldest', label: 'Oldest added' },
  { value: 'deadline', label: 'Deadline (soonest)' },
  { value: 'status', label: 'Status' },
];
