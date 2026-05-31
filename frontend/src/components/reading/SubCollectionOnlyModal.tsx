import { X } from 'lucide-react';
import type { QueueEntry } from '@/lib/types';

interface Props {
  open: boolean;
  entries: QueueEntry[];
  queueCollection: string;
  refManagerName: string;
  onClose: () => void;
}

export default function SubCollectionOnlyModal({ open, entries, queueCollection, refManagerName, onClose }: Props) {
  if (!open) return null;
  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        background: 'var(--overlay)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: 'var(--bg-card)', borderRadius: 12,
        border: '1px solid var(--border-md)',
        boxShadow: '0 16px 48px rgba(0,0,0,0.3)',
        width: '100%', maxWidth: 600, maxHeight: '82vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
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
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--fg4)', display: 'flex', flexShrink: 0 }}>
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-subtle)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div style={{ padding: '12px 14px', borderRadius: 8, border: '1px solid rgba(99,102,241,0.2)', background: 'rgba(99,102,241,0.05)' }}>
              <div style={{ fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 600, color: '#6366F1', marginBottom: 6 }}>
                Option A — Add back to parent
              </div>
              <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.55 }}>
                In {refManagerName}, drag the entry into the <strong style={{ color: 'var(--fg2)' }}>{queueCollection}</strong> collection directly (not just a sub-collection). Re-sync when done.
              </div>
            </div>
            <div style={{ padding: '12px 14px', borderRadius: 8, border: '1px solid rgba(212,86,86,0.2)', background: 'rgba(212,86,86,0.04)' }}>
              <div style={{ fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 600, color: '#D45656', marginBottom: 6 }}>
                Option B — Remove entirely
              </div>
              <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.55 }}>
                In {refManagerName}, right-click the entry and choose <em>Remove from collection</em> for each sub-collection it belongs to. Re-sync when done.
              </div>
            </div>
          </div>
        </div>

        <div style={{ overflowY: 'auto', flex: 1, padding: '8px 0' }}>
          {entries.map(entry => (
            <div
              key={entry.id}
              style={{ padding: '10px 20px', borderBottom: '1px solid var(--border)' }}
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

        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
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
  );
}
