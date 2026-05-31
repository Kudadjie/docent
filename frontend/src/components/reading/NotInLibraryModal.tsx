import { X, BookmarkCheck, Trash2 } from 'lucide-react';
import type { QueueEntry } from '@/lib/types';

interface Props {
  open: boolean;
  entries: QueueEntry[];
  refManagerName: string;
  onClose: () => void;
  onKeep: (id: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
}

export default function NotInLibraryModal({ open, entries, refManagerName, onClose, onKeep, onRemove }: Props) {
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
        width: '100%', maxWidth: 560, maxHeight: '80vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
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
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--fg4)', display: 'flex' }}>
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        <div style={{ overflowY: 'auto', flex: 1, padding: '8px 0' }}>
          {entries.length === 0 ? (
            <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--fg4)', fontFamily: 'var(--sans)', fontSize: 13 }}>
              All clear — no flagged entries.
            </div>
          ) : (
            entries.map(entry => (
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
                      await onKeep(entry.id);
                      if (entries.length <= 1) onClose();
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
                      await onRemove(entry.id);
                      if (entries.length <= 1) onClose();
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
  );
}
