'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import type { QueueEntry, Status } from '@/lib/types';

export interface EditFields {
  status?: Status;
  order?: number;
  deadline?: string;
  notes?: string;
  tags?: string[];
}

interface Props {
  entry: QueueEntry;
  onSave: (id: string, fields: EditFields) => void;
  onClose: () => void;
}

export default function EditModal({ entry, onSave, onClose }: Props) {
  const [status, setStatus]   = useState<Status>(entry.status);
  const [order, setOrder]     = useState(String(entry.order));
  const [deadline, setDeadline] = useState(entry.deadline ?? '');
  const [notes, setNotes]     = useState(entry.notes ?? '');
  const [tags, setTags]       = useState(entry.tags.join(', '));

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') onClose();
  }

  function handleSave() {
    const fields: EditFields = {};
    if (status !== entry.status) fields.status = status;
    const parsedOrder = parseInt(order, 10);
    if (!isNaN(parsedOrder) && parsedOrder !== entry.order) fields.order = parsedOrder;
    if (deadline !== (entry.deadline ?? '')) fields.deadline = deadline;
    if (notes !== (entry.notes ?? '')) fields.notes = notes;
    const newTags = tags.split(',').map(t => t.trim()).filter(Boolean);
    if (JSON.stringify(newTags) !== JSON.stringify(entry.tags)) fields.tags = newTags;
    onSave(entry.id, fields);
    onClose();
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Edit paper"
      onKeyDown={handleKeyDown}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-md)',
          borderRadius: 12,
          width: '100%', maxWidth: 480,
          boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
          padding: '16px 20px', borderBottom: '1px solid var(--border)',
        }}>
          <div style={{ minWidth: 0, paddingRight: 12 }}>
            <h2 style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)', margin: 0, lineHeight: 1.4 }}>
              {entry.title || entry.id}
            </h2>
            <p style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', margin: '3px 0 0', letterSpacing: '0.3px' }}>
              {entry.id}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--fg4)', display: 'flex', padding: 4, flexShrink: 0 }}
          >
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        {/* Form */}
        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Field label="Status">
              <select value={status} onChange={e => setStatus(e.target.value as Status)} style={inputStyle}>
                <option value="queued">Queued</option>
                <option value="reading">Reading</option>
                <option value="done">Done</option>
              </select>
            </Field>
            <Field label="Order">
              <input type="number" min={1} value={order} onChange={e => setOrder(e.target.value)} style={inputStyle} />
            </Field>
          </div>

          <Field label="Deadline">
            <input type="date" value={deadline} onChange={e => setDeadline(e.target.value)} style={inputStyle} />
          </Field>

          <Field label="Tags — comma-separated">
            <input
              type="text"
              value={tags}
              onChange={e => setTags(e.target.value)}
              placeholder="tag1, tag2, tag3"
              style={inputStyle}
            />
          </Field>

          <Field label="Notes">
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={3}
              style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.5 }}
            />
          </Field>
        </div>

        {/* Footer */}
        <div style={{
          display: 'flex', justifyContent: 'flex-end', gap: 8,
          padding: '12px 20px', borderTop: '1px solid var(--border)',
        }}>
          <button onClick={onClose} style={cancelBtnStyle}>Cancel</button>
          <button onClick={handleSave} style={saveBtnStyle}>Save changes</button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
        color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase',
      }}>
        {label}
      </span>
      {children}
    </label>
  );
}

const inputStyle: React.CSSProperties = {
  fontFamily: 'var(--sans)', fontSize: 13,
  color: 'var(--fg1)', background: 'var(--bg-subtle)',
  border: '1px solid var(--border-md)', borderRadius: 6,
  padding: '7px 10px', outline: 'none',
  width: '100%', boxSizing: 'border-box',
};

const cancelBtnStyle: React.CSSProperties = {
  fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
  color: 'var(--fg2)', background: 'transparent',
  border: '1px solid var(--border-md)', borderRadius: 9999,
  padding: '6px 14px', cursor: 'pointer',
};

const saveBtnStyle: React.CSSProperties = {
  fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
  color: '#fff', background: '#0fa76e',
  border: 'none', borderRadius: 9999,
  padding: '6px 16px', cursor: 'pointer',
};
