'use client';

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Sparkles, X } from 'lucide-react';

interface Release {
  version: string;
  date: string | null;
  highlights: string[];
}

interface WhatsNewPayload {
  version: string;
  release: Release | null;
  new: boolean;
}

/** Strip markdown bold, italic, and inline-code syntax for plain-text contexts. */
function stripMd(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1');
}

/** Truncate to maxLen characters, appending ellipsis if needed. */
function truncate(text: string, maxLen: number): string {
  return text.length > maxLen ? text.slice(0, maxLen).trimEnd() + '…' : text;
}

export default function WhatsNewToast() {
  const [release, setRelease] = useState<Release | null>(null);
  const [visible, setVisible] = useState(false);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/whatsnew')
      .then((r) => r.json())
      .then((data: WhatsNewPayload) => {
        if (cancelled) return;
        if (data.new && data.release && data.release.highlights.length > 0) {
          setRelease(data.release);
          setVisible(true);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  function dismiss() {
    setVisible(false);
    setShowModal(false);
    fetch('/api/whatsnew/seen', { method: 'POST' }).catch(() => {});
  }

  if (!visible || !release) return null;

  const previewItems = release.highlights.slice(0, 3);
  // Show "See more" if there are extra bullets OR if any visible bullet is truncated.
  const hasMore =
    release.highlights.length > 3 ||
    previewItems.some((h) => stripMd(h).length > 72);
  // Build a markdown bullet list for the modal.
  const fullMarkdown = release.highlights.map((h) => `- ${h}`).join('\n');

  return (
    <>
      {/* ── Toast ───────────────────────────────────────────────────────────── */}
      <div
        role="status"
        aria-live="polite"
        style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          zIndex: 100,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          padding: '14px 16px',
          borderRadius: 12,
          border: '1px solid rgba(24,226,153,0.25)',
          background: 'rgba(24,226,153,0.08)',
          backdropFilter: 'blur(8px)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.14)',
          maxWidth: 360,
          animation: 'fadeInUp 0.18s ease forwards',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: '#0fa76e', display: 'flex', flexShrink: 0 }}>
            <Sparkles size={15} strokeWidth={1.8} />
          </span>
          <span
            style={{
              fontFamily: 'var(--sans)',
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--fg1)',
              flex: 1,
            }}
          >
            What&apos;s New in v{release.version}
          </span>
          <button
            onClick={dismiss}
            aria-label="Dismiss"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--fg4)',
              display: 'flex',
              padding: 0,
              flexShrink: 0,
            }}
          >
            <X size={13} strokeWidth={2} />
          </button>
        </div>

        <ul
          style={{
            margin: 0,
            paddingLeft: 18,
            fontFamily: 'var(--sans)',
            fontSize: 12.5,
            fontWeight: 400,
            color: 'var(--fg2)',
            lineHeight: 1.55,
          }}
        >
          {previewItems.map((h, i) => (
            <li key={i}>{truncate(stripMd(h), 72)}</li>
          ))}
        </ul>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          {hasMore && (
            <button
              onClick={() => setShowModal(true)}
              style={{
                fontFamily: 'var(--sans)',
                fontSize: 12,
                fontWeight: 500,
                color: '#0fa76e',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '2px 4px',
              }}
            >
              See all →
            </button>
          )}
          <button
            onClick={dismiss}
            style={{
              fontFamily: 'var(--sans)',
              fontSize: 12,
              fontWeight: 500,
              color: 'var(--fg4)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '2px 4px',
            }}
          >
            Got it
          </button>
        </div>
      </div>

      {/* ── Full release-notes modal ─────────────────────────────────────────── */}
      {showModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`What's New in v${release.version}`}
          onClick={(e) => { if (e.target === e.currentTarget) dismiss(); }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 200,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(0,0,0,0.45)',
            backdropFilter: 'blur(4px)',
          }}
        >
          <div
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 14,
              padding: '28px 32px',
              maxWidth: 520,
              width: '90vw',
              maxHeight: '80vh',
              overflowY: 'auto',
              boxShadow: '0 8px 32px rgba(0,0,0,0.28)',
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
              <span style={{ color: '#0fa76e', marginRight: 10, display: 'flex' }}>
                <Sparkles size={17} strokeWidth={1.8} />
              </span>
              <span
                style={{
                  fontFamily: 'var(--sans)',
                  fontSize: 15,
                  fontWeight: 700,
                  color: 'var(--fg1)',
                  flex: 1,
                }}
              >
                What&apos;s New in v{release.version}
                {release.date && (
                  <span
                    style={{
                      fontWeight: 400,
                      fontSize: 12,
                      color: 'var(--fg4)',
                      marginLeft: 8,
                    }}
                  >
                    {release.date}
                  </span>
                )}
              </span>
              <button
                onClick={dismiss}
                aria-label="Close"
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--fg4)',
                  display: 'flex',
                  padding: 4,
                }}
              >
                <X size={15} strokeWidth={2} />
              </button>
            </div>

            {/* Content rendered as markdown */}
            <div
              style={{
                fontFamily: 'var(--sans)',
                fontSize: 13,
                color: 'var(--fg2)',
                lineHeight: 1.65,
              }}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  ul: ({ children }) => (
                    <ul style={{ margin: 0, paddingLeft: 20 }}>{children}</ul>
                  ),
                  li: ({ children }) => (
                    <li style={{ marginBottom: 8 }}>{children}</li>
                  ),
                  strong: ({ children }) => (
                    <strong style={{ color: 'var(--fg1)', fontWeight: 600 }}>{children}</strong>
                  ),
                  code: ({ children }) => (
                    <code
                      style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 12,
                        background: 'var(--gray100)',
                        color: 'var(--fg1)',
                        padding: '1px 5px',
                        borderRadius: 4,
                        border: '1px solid var(--border)',
                      }}
                    >
                      {children}
                    </code>
                  ),
                }}
              >
                {fullMarkdown}
              </ReactMarkdown>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}>
              <button
                onClick={dismiss}
                style={{
                  fontFamily: 'var(--sans)',
                  fontSize: 12.5,
                  fontWeight: 600,
                  color: '#0fa76e',
                  background: 'none',
                  border: '1px solid rgba(24,226,153,0.35)',
                  borderRadius: 6,
                  cursor: 'pointer',
                  padding: '6px 14px',
                }}
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
