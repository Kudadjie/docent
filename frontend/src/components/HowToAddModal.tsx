'use client';

import { useRef, useEffect } from 'react';
import { X, FolderOpen, RefreshCw, BookOpen } from 'lucide-react';

interface Props {
  onClose: () => void;
  collectionName?: string;
  refManager?: string;
}

export default function HowToAddModal({ onClose, collectionName = 'Docent-Queue', refManager = 'Mendeley' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  const isZotero = refManager.toLowerCase() === 'zotero';

  const STEPS = isZotero ? [
    {
      icon: <BookOpen size={15} strokeWidth={1.5} />,
      label: 'Select the collection first',
      detail: `In the Zotero desktop app, click your "${collectionName}" collection (or a sub-collection) to make it active.`,
    },
    {
      icon: <FolderOpen size={15} strokeWidth={1.5} />,
      label: 'Save via the Zotero connector',
      detail: `Click the Zotero browser connector on the paper page. It saves directly into the active collection — no dragging needed.`,
    },
    {
      icon: <RefreshCw size={15} strokeWidth={1.5} />,
      label: 'Sync',
      detail: `Click "Sync" in the toolbar — Docent will pull the new entry into your queue.`,
    },
  ] : [
    {
      icon: <FolderOpen size={15} strokeWidth={1.5} />,
      label: 'Get the paper into Mendeley',
      detail: `Use the Mendeley Web Importer (browser extension) and save directly to "${collectionName}", or drop the PDF into your watch folder and drag it to the collection in Mendeley.`,
    },
    {
      icon: <BookOpen size={15} strokeWidth={1.5} />,
      label: 'Tip: target the collection',
      detail: `In the Web Importer popup, choose "${collectionName}" as the destination — skips the manual drag entirely.`,
    },
    {
      icon: <RefreshCw size={15} strokeWidth={1.5} />,
      label: 'Sync',
      detail: `Click "Sync" in the toolbar — Docent will pull the new entry into your queue.`,
    },
  ];

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const focusable = Array.from(container.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    ));
    focusable[0]?.focus();

    function trap(e: KeyboardEvent) {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key !== 'Tab' || focusable.length === 0) return;
      const first = focusable[0];
      const last  = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
      }
    }

    document.addEventListener('keydown', trap);
    return () => document.removeEventListener('keydown', trap);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="How to add documents"
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
        ref={containerRef}
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
              How to add documents
            </div>
            <div
              style={{
                fontFamily: 'var(--sans)',
                fontSize: 13,
                color: 'var(--fg3)',
                marginTop: 2,
              }}
            >
              Documents enter via {refManager} — not manually.
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
            {refManager} is the source of truth for metadata. Docent adds workflow on top.
          </p>
        </div>
      </div>
    </div>
  );
}
