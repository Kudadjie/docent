'use client';

import { useState } from 'react';
import { CheckCircle, Pencil, Trash2, BookOpen, Play } from 'lucide-react';
import StatusBadge from './StatusBadge';
import OrderIndicator from './OrderIndicator';
import type { QueueEntry } from '@/lib/types';

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function isDeadlineUrgent(deadline: string | null): 'past' | 'soon' | null {
  if (!deadline) return null;
  const diff = new Date(deadline).getTime() - Date.now();
  if (diff < 0) return 'past';
  if (diff < 3 * 24 * 60 * 60 * 1000) return 'soon';
  return null;
}

const TYPE_LABEL: Record<string, string> = {
  book: 'BOOK',
  book_chapter: 'CHAPTER',
};

function PaperRow({
  entry,
  isNew,
  dark,
  onMarkDone,
  onDelete,
  onEdit,
  onStart,
}: {
  entry: QueueEntry;
  isNew: boolean;
  dark: boolean;
  onMarkDone: (id: string) => void;
  onDelete: (id: string) => void;
  onEdit: (entry: QueueEntry) => void;
  onStart: (id: string) => void;
}) {
  const [hov, setHov] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const deadlineUrgency = isDeadlineUrgent(entry.deadline);
  const typeTag = TYPE_LABEL[entry.type];

  return (
    <tr
      className={`paper-row${isNew ? ' row-fade' : ''}`}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        borderBottom: '1px solid var(--border)',
        background: hov ? 'var(--row-hover)' : 'transparent',
      }}
    >
      {/* Paper */}
      <td style={{ padding: '14px 20px', verticalAlign: 'top' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Title row */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              flexWrap: 'wrap',
              fontFamily: 'var(--sans)',
              fontSize: 14,
              fontWeight: 500,
              color: 'var(--fg1)',
              lineHeight: 1.4,
            }}
          >
            <span style={{ textWrap: 'pretty' } as React.CSSProperties}>{entry.title || entry.id}</span>
            {typeTag && (
              <span
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 9,
                  fontWeight: 500,
                  letterSpacing: '0.4px',
                  textTransform: 'uppercase',
                  padding: '1px 5px',
                  borderRadius: 4,
                  background: 'var(--gray100)',
                  color: 'var(--fg4)',
                  flexShrink: 0,
                }}
              >
                {typeTag}
              </span>
            )}
          </div>

          {/* Sub-line: authors · category+year */}
          <div
            style={{
              marginTop: 3,
              fontFamily: 'var(--sans)',
              fontSize: 12,
              color: 'var(--fg3)',
              lineHeight: 1.5,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              flexWrap: 'wrap',
            }}
          >
            {entry.authors && <span>{entry.authors}</span>}
            {(entry.authors && (entry.category || entry.year)) && (
              <span style={{ color: 'var(--gray200)' }}>·</span>
            )}
            {(entry.category || entry.year) && (
              <span
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 10,
                  color: 'var(--fg4)',
                  letterSpacing: '0.4px',
                  textTransform: 'uppercase',
                }}
              >
                {[entry.category, entry.year].filter(Boolean).join(' · ')}
              </span>
            )}
            {/* Deadline pill */}
            {entry.deadline && (
              <>
                <span style={{ color: 'var(--gray200)' }}>·</span>
                <span
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: '0.3px',
                    textTransform: 'uppercase',
                    padding: '1px 6px',
                    borderRadius: 9999,
                    background: deadlineUrgency === 'past'
                      ? 'rgba(212,86,86,0.12)'
                      : deadlineUrgency === 'soon'
                      ? 'rgba(195,125,13,0.12)'
                      : 'var(--gray100)',
                    color: deadlineUrgency === 'past'
                      ? '#D45656'
                      : deadlineUrgency === 'soon'
                      ? '#C37D0D'
                      : 'var(--fg4)',
                  }}
                >
                  Due {formatDate(entry.deadline)}
                </span>
              </>
            )}
          </div>

          {/* Tags */}
          {entry.tags.length > 0 && (
            <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {entry.tags.map((tag) => (
                <span
                  key={tag}
                  style={{
                    padding: '1px 8px',
                    borderRadius: 9999,
                    background: 'var(--gray100)',
                    color: 'var(--fg4)',
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    letterSpacing: '0.3px',
                    textTransform: 'uppercase',
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </td>

      {/* Status */}
      <td style={{ padding: '14px 16px', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
        <StatusBadge status={entry.status} dark={dark} />
      </td>

      {/* Order */}
      <td style={{ padding: '14px 16px', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
        <OrderIndicator order={entry.order} />
      </td>

      {/* Added */}
      <td style={{ padding: '14px 16px', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
        <span
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 11,
            color: 'var(--fg4)',
            letterSpacing: '0.3px',
          }}
        >
          {formatDate(entry.added)}
        </span>
      </td>

      {/* Actions */}
      <td style={{ padding: '14px 16px', verticalAlign: 'middle', textAlign: 'right' }}>
        <div className="row-actions" style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
          {entry.status === 'queued' && (
            <IconBtn
              icon={<Play size={14} strokeWidth={1.5} />}
              label="Start reading"
              color="#0fa76e"
              onClick={() => onStart(entry.id)}
            />
          )}
          {entry.status === 'reading' && (
            <IconBtn
              icon={<CheckCircle size={15} strokeWidth={1.5} />}
              label="Mark done"
              color="#0fa76e"
              onClick={() => onMarkDone(entry.id)}
            />
          )}
          <IconBtn
            icon={<Pencil size={15} strokeWidth={1.5} />}
            label="Edit"
            color="var(--fg4)"
            onClick={() => onEdit(entry)}
          />
          {confirmDelete ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginLeft: 2 }}>
              <button
                onClick={() => { onDelete(entry.id); setConfirmDelete(false); }}
                style={{
                  fontFamily: 'var(--sans)', fontSize: 11, fontWeight: 600,
                  color: '#D45656', background: 'rgba(212,86,86,0.1)',
                  border: '1px solid rgba(212,86,86,0.3)',
                  borderRadius: 6, padding: '2px 8px', cursor: 'pointer', whiteSpace: 'nowrap',
                }}
              >
                Delete?
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                aria-label="Cancel delete"
                style={{
                  fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
                  color: 'var(--fg4)', background: 'transparent',
                  border: 'none', cursor: 'pointer', padding: '2px 4px', lineHeight: 1,
                }}
              >
                ✕
              </button>
            </span>
          ) : (
            <IconBtn
              icon={<Trash2 size={15} strokeWidth={1.5} />}
              label="Delete"
              color="#D45656"
              onClick={() => setConfirmDelete(true)}
            />
          )}
        </div>
      </td>
    </tr>
  );
}

function IconBtn({
  icon,
  label,
  color,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  color: string;
  onClick: () => void;
}) {
  const [hov, setHov] = useState(false);
  return (
    <button
      aria-label={label}
      title={label}
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 28,
        height: 28,
        borderRadius: 6,
        border: 'none',
        background: hov ? 'var(--gray100)' : 'transparent',
        color,
        cursor: 'pointer',
        transition: 'background 0.1s',
      }}
    >
      {icon}
    </button>
  );
}

interface Props {
  entries: QueueEntry[];
  newIds: Set<string>;
  dark: boolean;
  onMarkDone: (id: string) => void;
  onDelete: (id: string) => void;
  onEdit: (entry: QueueEntry) => void;
  onStart: (id: string) => void;
}

export default function PaperTable({ entries, newIds, dark, onMarkDone, onDelete, onEdit, onStart }: Props) {
  if (entries.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: 200,
          gap: 10,
          color: 'var(--fg4)',
        }}
      >
        <BookOpen size={32} strokeWidth={1} style={{ opacity: 0.4 }} />
        <span style={{ fontFamily: 'var(--sans)', fontSize: 13 }}>No papers found</span>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto' }}>
      <table
        style={{ width: '100%', borderCollapse: 'collapse' }}
        aria-label="Reading queue"
      >
        <thead>
          <tr
            style={{
              position: 'sticky',
              top: 0,
              zIndex: 1,
              background: 'var(--bg)',
            }}
          >
            {['Paper', 'Status', 'Order', 'Added', ''].map((col, i) => (
              <th
                key={i}
                scope="col"
                style={{
                  padding: i === 0 ? '9px 16px 9px 20px' : '9px 16px',
                  textAlign: i === 4 ? 'right' : 'left',
                  fontFamily: 'var(--mono)',
                  fontSize: 10,
                  fontWeight: 500,
                  color: 'var(--fg4)',
                  letterSpacing: '0.6px',
                  textTransform: 'uppercase',
                  borderBottom: '1px solid var(--border)',
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <PaperRow
              key={entry.id}
              entry={entry}
              isNew={newIds.has(entry.id)}
              dark={dark}
              onMarkDone={onMarkDone}
              onDelete={onDelete}
              onEdit={onEdit}
              onStart={onStart}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
