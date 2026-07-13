'use client';

// Live-run activity components (phase strip, source chips, log stream) —
// extracted from app/studio/_output.tsx in the v2.3 monolith split.

import { useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import {
  PHASE_LABELS, PHASE_TONE,
  type LogEntry, type Source,
} from '@/app/studio/_shared';
import { BRAND, BRAND_DEEP, AMBER_BORDER, PX_PER_PHASE } from '@/components/studio/palette';

export function PhaseStrip({ seenPhases, completedPhases, currentPhase, status }: {
  seenPhases: string[]; completedPhases: Set<string>; currentPhase: string | null; status: string;
}) {
  const phases = seenPhases;
  const containerRef = useRef<HTMLDivElement>(null);
  const [compact, setCompact] = useState(false);

  // Switch to compact (dots-only) mode whenever the available width is too
  // narrow to render full labels without cramping.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(entries => {
      const width = entries[0].contentRect.width;
      setCompact(width < phases.length * PX_PER_PHASE);
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, [phases.length]);

  if (phases.length <= 1) return null;

  // ── Compact mode: dots + short connectors + active-phase label only ──────────
  if (compact) {
    const allDone     = status === 'success';
    const activePhase = status === 'running' ? currentPhase
      : allDone ? phases[phases.length - 1] : null;
    const activeLabel = activePhase ? (PHASE_LABELS[activePhase] ?? activePhase) : null;

    return (
      <div ref={containerRef} style={{ padding: '10px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'nowrap', minWidth: 0 }}>
          {phases.map((p, i) => {
            const done    = completedPhases.has(p) || allDone;
            const current = p === currentPhase && status === 'running';
            const dotColor  = current ? AMBER_BORDER : done ? BRAND : 'var(--gray200)';
            const lineColor = done ? BRAND : 'var(--border)';
            return (
              <div key={p} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                <span
                  title={PHASE_LABELS[p] ?? p}
                  style={{
                    width: current ? 9 : 7, height: current ? 9 : 7,
                    borderRadius: '50%', background: dotColor,
                    flexShrink: 0, cursor: 'default',
                    animation: current ? 'logo-dot-blink 1.1s step-end infinite' : 'none',
                    transition: 'all 0.15s',
                  }}
                />
                {i < phases.length - 1 && (
                  <div style={{ width: 10, height: 1, background: lineColor, margin: '0 3px', transition: 'background 0.25s' }} />
                )}
              </div>
            );
          })}
          {activeLabel && (
            <span style={{
              marginLeft: 10, flexShrink: 0,
              fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600,
              color: allDone ? BRAND_DEEP : 'var(--amber-text)',
              letterSpacing: '0.5px', textTransform: 'uppercase', whiteSpace: 'nowrap',
            }}>
              {activeLabel}
            </span>
          )}
        </div>
      </div>
    );
  }

  // ── Full mode: dots + labels + connector lines in a single row ───────────────
  return (
    <div ref={containerRef} style={{ display: 'flex', alignItems: 'center', gap: 0, padding: '10px 0' }}>
      {phases.map((p, i) => {
        const done    = completedPhases.has(p);
        const current = p === currentPhase && status === 'running';
        const dotColor   = current ? AMBER_BORDER : done ? BRAND : 'var(--gray200)';
        const labelColor = current ? 'var(--amber-text)' : done ? BRAND_DEEP : 'var(--fg4)';
        const lineColor  = done ? BRAND : 'var(--border)';
        return (
          <div key={p} style={{ display: 'flex', alignItems: 'center', minWidth: 0, flex: i < phases.length - 1 ? '1 1 auto' : '0 0 auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
              <span style={{ width: current ? 9 : 7, height: current ? 9 : 7, borderRadius: '50%', background: dotColor, flexShrink: 0, animation: current ? 'logo-dot-blink 1.1s step-end infinite' : 'none', transition: 'all 0.15s' }} />
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: current ? 600 : 500, color: labelColor, letterSpacing: '0.5px', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
                {PHASE_LABELS[p] ?? p}
              </span>
            </div>
            {i < phases.length - 1 && (
              <div style={{ flex: 1, height: 1, background: lineColor, margin: '0 10px', transition: 'background 0.25s' }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Source chips ───────────────────────────────────────────────────────────────

export function SourceChips({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;
  return (
    <div style={{ padding: '10px 0 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500, color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase' }}>Sources collected</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, color: BRAND_DEEP, background: BRAND + '1f', padding: '1px 7px', borderRadius: 9999 }}>{sources.length}</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
        {sources.map((s, i) => (
          <div key={i} className="src-chip" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, maxWidth: 280, padding: '4px 10px', borderRadius: 9999, background: 'var(--gray100)', border: '1px solid var(--border)', fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg2)' }}>
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.title}>{s.title}</span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.3px', flexShrink: 0 }}>{s.src} {s.year}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Phase colour palette ───────────────────────────────────────────────────────
// Each phase group gets a distinct accent so the log is easy to scan at a glance.
const PHASE_PALETTE: Record<string, { color: string; bg: string }> = {
  // search phases → violet / purple
  web_search:    { color: '#a78bfa', bg: 'rgba(139,92,246,0.14)' },
  paper_search:  { color: '#a78bfa', bg: 'rgba(139,92,246,0.14)' },
  search:        { color: '#a78bfa', bg: 'rgba(139,92,246,0.14)' },
  scholar:       { color: '#a78bfa', bg: 'rgba(139,92,246,0.14)' },
  scholarly:     { color: '#a78bfa', bg: 'rgba(139,92,246,0.14)' },
  // planning / writing → blue
  search_plan:   { color: '#60a5fa', bg: 'rgba(59,130,246,0.14)' },
  plan:          { color: '#60a5fa', bg: 'rgba(59,130,246,0.14)' },
  fetch:         { color: '#60a5fa', bg: 'rgba(59,130,246,0.14)' },
  write:         { color: '#60a5fa', bg: 'rgba(59,130,246,0.14)' },
  draft:         { color: '#60a5fa', bg: 'rgba(59,130,246,0.14)' },
  research:      { color: '#60a5fa', bg: 'rgba(59,130,246,0.14)' },
  // compile / verify → brand green
  compile:       { color: BRAND_DEEP, bg: BRAND + '1c' },
  verify:        { color: BRAND_DEEP, bg: BRAND + '1c' },
  verify_citations: { color: BRAND_DEEP, bg: BRAND + '1c' },
  citations:     { color: BRAND_DEEP, bg: BRAND + '1c' },
  refine:        { color: BRAND_DEEP, bg: BRAND + '1c' },
  // review / done → teal-ish (same green family, slightly brighter)
  review:        { color: '#2dd4bf', bg: 'rgba(45,212,191,0.12)' },
  done:          { color: '#2dd4bf', bg: 'rgba(45,212,191,0.12)' },
  package:       { color: '#2dd4bf', bg: 'rgba(45,212,191,0.12)' },
  // warn / cost → amber  (overridden below for tone-based rows)
  warn:          { color: 'var(--amber-text)', bg: 'var(--amber-bg)' },
  cost:          { color: 'var(--amber-text)', bg: 'var(--amber-bg)' },
  // error → red
  error:         { color: 'var(--red-text)', bg: 'var(--red-bg)' },
  // start / info → neutral blue-grey
  start:         { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)' },
  info:          { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)' },
  // console → very dim (raw subprocess passthrough)
  console:       { color: '#64748b', bg: 'rgba(100,116,139,0.10)' },
};

export function phasePalette(phase: string, tone: string) {
  if (tone === 'warn') return { color: 'var(--amber-text)', bg: 'var(--amber-bg)', rowBg: 'var(--amber-bg)', border: AMBER_BORDER };
  if (tone === 'error') return { color: 'var(--red-text)', bg: 'var(--red-bg)', rowBg: 'var(--red-bg)', border: '#E53535' };
  const p = PHASE_PALETTE[phase] ?? { color: BRAND_DEEP, bg: BRAND + '1c' };
  return { ...p, rowBg: 'transparent', border: 'transparent' };
}

// ── Log line ───────────────────────────────────────────────────────────────────

export function LogLine({ phase, text, live }: { phase: string; text: string; live?: boolean }) {
  const tone = PHASE_TONE[phase] ?? 'info';
  const { color, bg, rowBg, border } = phasePalette(phase, tone);
  const isConsole = phase === 'console';
  return (
    <div className={'log-line' + (live ? ' live' : '')} style={{ display: 'flex', gap: 10, padding: isConsole ? '3px 12px 3px 10px' : '5px 12px 5px 10px', background: rowBg, borderLeft: `2px solid ${border}`, borderRadius: '2px 4px 4px 2px', alignItems: 'flex-start', opacity: isConsole ? 0.7 : 1 }}>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, fontWeight: 600, letterSpacing: '0.6px', textTransform: 'uppercase', color, background: bg, padding: '2px 6px', borderRadius: 4, flexShrink: 0, marginTop: 1, minWidth: 46, textAlign: 'center' }}>
        {PHASE_LABELS[phase] ?? phase}
      </span>
      <span style={{ fontFamily: 'var(--mono)', fontSize: isConsole ? 11 : 12.5, color: isConsole ? 'var(--fg4)' : 'var(--fg2)', lineHeight: 1.5, flex: 1, wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
        {text}
        {live && <span style={{ marginLeft: 4 }}><span className="thinking-dot" /><span className="thinking-dot" /><span className="thinking-dot" /></span>}
      </span>
    </div>
  );
}

// ── Log stream (collapsible) ───────────────────────────────────────────────────

export function LogStream({ logs, status }: { logs: LogEntry[]; status: string }) {
  const isRunning = status === 'running';
  const isResult  = status === 'success' || status === 'failure' || status === 'stopped';
  const [collapsed, setCollapsed] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  /* eslint-disable react-hooks/set-state-in-effect */
  // Intentional: auto-expand log when a run starts
  useEffect(() => {
    if (status === 'running') setCollapsed(false);
  }, [status]);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs.length]);

  if (!logs.length) return null;

  if (isResult && collapsed) {
    return (
      <button onClick={() => setCollapsed(false)} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '7px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-subtle)', color: 'var(--fg3)', fontFamily: 'var(--sans)', fontSize: 12, cursor: 'pointer', alignSelf: 'flex-start' }}>
        <ChevronRight size={14} strokeWidth={2} />
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.5px', textTransform: 'uppercase', color: 'var(--fg4)' }}>{logs.length} events</span>
        <span>Show activity log</span>
      </button>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500, color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase' }}>Activity log</div>
        {isResult && (
          <button onClick={() => setCollapsed(true)} style={{ marginLeft: 'auto', background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg4)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <ChevronDown size={14} strokeWidth={2} /> Collapse
          </button>
        )}
      </div>
      <div ref={logRef} style={{ display: 'flex', flexDirection: 'column', gap: 2, maxHeight: isResult ? 240 : undefined, overflowY: isResult ? 'auto' : 'visible' }}>
        {logs.map((l, i) => (
          <LogLine key={i} phase={l.phase} text={l.text} live={isRunning && i === logs.length - 1} />
        ))}
      </div>
    </div>
  );
}

// ── Empty state ────────────────────────────────────────────────────────────────
