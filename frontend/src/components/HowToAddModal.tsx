'use client';

import { X, FolderOpen, RefreshCw, BookOpen } from 'lucide-react';

interface Props {
  onClose: () => void;
}

const STEPS = [
  {
    icon: <FolderOpen size={15} strokeWidth={1.5} />,
    label: 'Drop the PDF',
    detail: 'Place the PDF into your database folder (your Mendeley auto-import folder).',
  },
  {
    icon: <BookOpen size={15} strokeWidth={1.5} />,
    label: 'Add to Mendeley',
    detail: 'In Mendeley Desktop, drag the document into your Docent-Queue collection.',
  },
  {
    icon: <RefreshCw size={15} strokeWidth={1.5} />,
    label: 'Sync',
    detail: 'Click "Sync Mendeley" in the toolbar — Docent will pull the new entry into your queue.',
  },
];

export default function HowToAddModal({ onClose }: Props) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="How to add papers"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.2)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-card)',
          borderRadius: 16,
          width: 440,
          border: '1px solid var(--border)',
          boxShadow: 'rgba(0,0,0,0.12) 0px 8px 32px',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px 16px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div
              style={{
                fontFamily: 'var(--sans)',
                fontSize: 15,
                fontWeight: 600,
                color: 'var(--fg1)',
              }}
            >
              How to add papers
            </div>
            <div
              style={{
                fontFamily: 'var(--sans)',
                fontSize: 13,
                color: 'var(--fg3)',
                marginTop: 2,
              }}
            >
              Papers enter via Mendeley — not manually.
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 28,
              height: 28,
              borderRadius: 6,
              border: 'none',
              background: 'transparent',
              color: 'var(--fg4)',
              cursor: 'pointer',
            }}
          >
            <X size={14} strokeWidth={1.5} />
          </button>
        </div>

        {/* Steps */}
        <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {STEPS.map((step, i) => (
            <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  background: 'var(--gray100)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  color: 'var(--brand-deep)',
                }}
              >
                {step.icon}
              </div>
              <div>
                <div
                  style={{
                    fontFamily: 'var(--sans)',
                    fontSize: 13,
                    fontWeight: 500,
                    color: 'var(--fg1)',
                    marginBottom: 2,
                  }}
                >
                  {step.label}
                </div>
                <div
                  style={{
                    fontFamily: 'var(--sans)',
                    fontSize: 12,
                    color: 'var(--fg3)',
                    lineHeight: 1.5,
                  }}
                >
                  {step.detail}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 24px 20px',
            borderTop: '1px solid var(--border)',
          }}
        >
          <p
            style={{
              fontFamily: 'var(--mono)',
              fontSize: 10,
              color: 'var(--fg4)',
              letterSpacing: '0.4px',
              textTransform: 'uppercase',
            }}
          >
            Mendeley is the source of truth for metadata. Docent adds workflow on top.
          </p>
        </div>
      </div>
    </div>
  );
}
