'use client';

import { X } from 'lucide-react';
import type { QueueEntry } from '@/lib/types';

interface Props {
  entries: QueueEntry[];
  onClose: () => void;
}

function isOverdue(deadline: string | null) {
  if (!deadline) return false;
  return new Date(deadline).getTime() < Date.now();
}

function isDueSoon(deadline: string | null) {
  if (!deadline) return false;
  const diff = new Date(deadline).getTime() - Date.now();
  return diff >= 0 && diff < 3 * 24 * 60 * 60 * 1000;
}

function Row({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0' }}>
      <span style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg2)' }}>{label}</span>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 600,
        color: color ?? 'var(--fg1)', letterSpacing: '0.3px',
      }}>{value}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p style={{
        fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
        color: 'var(--fg4)', letterSpacing: '0.6px', textTransform: 'uppercase',
        margin: '0 0 6px',
      }}>{title}</p>
      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 4 }}>
        {children}
      </div>
    </div>
  );
}

const TYPE_LABEL: Record<string, string> = {
  paper: 'Papers',
  book: 'Books',
  book_chapter: 'Chapters',
};

export default function StatsModal({ entries, onClose }: Props) {
  const queued  = entries.filter(e => e.status === 'queued').length;
  const reading = entries.filter(e => e.status === 'reading').length;
  const done    = entries.filter(e => e.status === 'done').length;

  const byType = Object.entries(
    entries.reduce<Record<string, number>>((acc, e) => {
      acc[e.type] = (acc[e.type] ?? 0) + 1;
      return acc;
    }, {})
  ).sort((a, b) => b[1] - a[1]);

  const byCategory = Object.entries(
    entries.reduce<Record<string, number>>((acc, e) => {
      const cat = e.category ?? 'Uncategorised';
      acc[cat] = (acc[cat] ?? 0) + 1;
      return acc;
    }, {})
  ).sort((a, b) => b[1] - a[1]);

  const overdue  = entries.filter(e => isOverdue(e.deadline)).length;
  const dueSoon  = entries.filter(e => isDueSoon(e.deadline)).length;
  const withDeadline = entries.filter(e => e.deadline).length;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Queue statistics"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
    >
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-md)',
        borderRadius: 12,
        width: '100%', maxWidth: 380,
        boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', borderBottom: '1px solid var(--border)',
        }}>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)', margin: 0 }}>
            Queue stats
          </h2>
          <button onClick={onClose} aria-label="Close"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--fg4)', display: 'flex', padding: 4 }}>
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Status */}
          <Section title="By status">
            <Row label="Reading" value={reading} color="#0fa76e" />
            <Row label="Queued"  value={queued} />
            <Row label="Done"    value={done}   color="var(--fg4)" />
            <Row label="Total"   value={entries.length} />
          </Section>

          {/* Type */}
          <Section title="By type">
            {byType.map(([type, count]) => (
              <Row key={type} label={TYPE_LABEL[type] ?? type} value={count} />
            ))}
          </Section>

          {/* Category */}
          {byCategory.length > 0 && (
            <Section title="By category">
              {byCategory.map(([cat, count]) => (
                <Row key={cat} label={cat} value={count} />
              ))}
            </Section>
          )}

          {/* Deadlines */}
          <Section title="Deadlines">
            {overdue > 0  && <Row label="Overdue"        value={overdue}  color="#D45656" />}
            {dueSoon > 0  && <Row label="Due within 3 days" value={dueSoon} color="#C37D0D" />}
            <Row label="With deadline" value={withDeadline} />
          </Section>
        </div>
      </div>
    </div>
  );
}
