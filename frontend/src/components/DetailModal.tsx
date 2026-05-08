'use client';

import { X } from 'lucide-react';
import StatusBadge from './StatusBadge';
import type { QueueEntry } from '@/lib/types';

interface Props {
  entry: QueueEntry;
  dark: boolean;
  onClose: () => void;
}

function fmt(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return iso; }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
        color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase',
        display: 'block', marginBottom: 3,
      }}>
        {label}
      </span>
      <span style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg1)', lineHeight: 1.5 }}>
        {children}
      </span>
    </div>
  );
}

const TYPE_LABEL: Record<string, string> = { book: 'Book', book_chapter: 'Chapter', paper: 'Paper' };

export default function DetailModal({ entry, dark, onClose }: Props) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Entry details"
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
        width: '100%', maxWidth: 520,
        maxHeight: '80vh', overflowY: 'auto',
        boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
      }}>
        {/* Header */}
        <div style={{
          position: 'sticky', top: 0, zIndex: 1,
          background: 'var(--bg-card)',
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
          padding: '16px 20px', borderBottom: '1px solid var(--border)',
        }}>
          <div style={{ minWidth: 0, paddingRight: 12 }}>
            <h2 style={{
              fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600,
              color: 'var(--fg1)', margin: 0, lineHeight: 1.4,
            }}>
              {entry.title || entry.id}
            </h2>
            {entry.authors && (
              <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', margin: '3px 0 0' }}>
                {entry.authors}{entry.year ? ` · ${entry.year}` : ''}
              </p>
            )}
          </div>
          <button onClick={onClose} aria-label="Close"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--fg4)', display: 'flex', padding: 4, flexShrink: 0 }}>
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Status row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <StatusBadge status={entry.status} dark={dark} />
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)' }}>
              Order #{entry.order}
            </span>
            <span style={{
              fontFamily: 'var(--mono)', fontSize: 10, padding: '1px 6px',
              borderRadius: 4, background: 'var(--gray100)', color: 'var(--fg4)',
              textTransform: 'uppercase', letterSpacing: '0.4px',
            }}>
              {TYPE_LABEL[entry.type] ?? entry.type}
            </span>
            {entry.category && (
              <span style={{
                fontFamily: 'var(--mono)', fontSize: 10, padding: '1px 6px',
                borderRadius: 4, background: 'var(--gray100)', color: 'var(--fg4)',
                textTransform: 'uppercase', letterSpacing: '0.4px',
              }}>
                {entry.category}
              </span>
            )}
          </div>

          {/* Grid fields */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <Field label="Added">{fmt(entry.added)}</Field>
            <Field label="Deadline">{fmt(entry.deadline)}</Field>
            <Field label="Started">{fmt(entry.started)}</Field>
            <Field label="Finished">{fmt(entry.finished)}</Field>
          </div>

          <Field label="DOI">
            {entry.doi
              ? <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{entry.doi}</span>
              : '—'}
          </Field>

          <Field label="Entry ID">
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{entry.id}</span>
          </Field>

          {entry.mendeley_id && (
            <Field label="Mendeley ID">
              <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{entry.mendeley_id}</span>
            </Field>
          )}

          {/* Tags */}
          {entry.tags.length > 0 && (
            <div>
              <span style={{
                fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
                color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase',
                display: 'block', marginBottom: 6,
              }}>Tags</span>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {entry.tags.map(tag => (
                  <span key={tag} style={{
                    padding: '2px 8px', borderRadius: 9999,
                    background: 'var(--gray100)', color: 'var(--fg4)',
                    fontFamily: 'var(--mono)', fontSize: 10,
                    letterSpacing: '0.3px', textTransform: 'uppercase',
                  }}>{tag}</span>
                ))}
              </div>
            </div>
          )}

          {/* Notes */}
          <Field label="Notes">
            {entry.notes
              ? <span style={{ whiteSpace: 'pre-wrap' }}>{entry.notes}</span>
              : <span style={{ color: 'var(--fg4)' }}>—</span>}
          </Field>
        </div>
      </div>
    </div>
  );
}
