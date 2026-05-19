'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  CheckCircle, XCircle, AlertTriangle, ExternalLink, ChevronDown, ChevronRight, Plus, X, History, Trash,
} from 'lucide-react';
import {
  PHASE_LABELS, PHASE_TONE, findAction,
  type ActionId, type ActionMeta, type FormState, type LogEntry, type Source, type RunRecord,
} from './_shared';
import { GhostBtn, PrimaryBtn, CodeBlock, Chip, FieldLabel, Kbd } from './_form';

const BRAND      = '#18E299';
const BRAND_DEEP = '#0fa76e';
const AMBER_BORDER = '#F59E0B';
const AMBER      = '#C37D0D';
const BLUE       = '#3772cf';

// ── Phase strip ────────────────────────────────────────────────────────────────

function PhaseStrip({ seenPhases, completedPhases, currentPhase, status }: {
  seenPhases: string[]; completedPhases: Set<string>; currentPhase: string | null; status: string;
}) {
  const phases = seenPhases;
  if (phases.length <= 1) return null;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, padding: '10px 0' }}>
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

function SourceChips({ sources }: { sources: Source[] }) {
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
};

function phasePalette(phase: string, tone: string) {
  if (tone === 'warn') return { color: 'var(--amber-text)', bg: 'var(--amber-bg)', rowBg: 'var(--amber-bg)', border: AMBER_BORDER };
  if (tone === 'error') return { color: 'var(--red-text)', bg: 'var(--red-bg)', rowBg: 'var(--red-bg)', border: '#E53535' };
  const p = PHASE_PALETTE[phase] ?? { color: BRAND_DEEP, bg: BRAND + '1c' };
  return { ...p, rowBg: 'transparent', border: 'transparent' };
}

// ── Log line ───────────────────────────────────────────────────────────────────

function LogLine({ phase, text, live }: { phase: string; text: string; live?: boolean }) {
  const tone = PHASE_TONE[phase] ?? 'info';
  const { color, bg, rowBg, border } = phasePalette(phase, tone);
  return (
    <div className={'log-line' + (live ? ' live' : '')} style={{ display: 'flex', gap: 10, padding: '5px 12px 5px 10px', background: rowBg, borderLeft: `2px solid ${border}`, borderRadius: '2px 4px 4px 2px', alignItems: 'flex-start' }}>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, fontWeight: 600, letterSpacing: '0.6px', textTransform: 'uppercase', color, background: bg, padding: '2px 6px', borderRadius: 4, flexShrink: 0, marginTop: 1, minWidth: 46, textAlign: 'center' }}>
        {phase}
      </span>
      <span style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.5, flex: 1, wordBreak: 'break-word' }}>
        {text}
        {live && <span style={{ marginLeft: 4 }}><span className="thinking-dot" /><span className="thinking-dot" /><span className="thinking-dot" /></span>}
      </span>
    </div>
  );
}

// ── Log stream (collapsible) ───────────────────────────────────────────────────

function LogStream({ logs, status }: { logs: LogEntry[]; status: string }) {
  const isRunning = status === 'running';
  const isResult  = status === 'success' || status === 'failure' || status === 'stopped';
  const [collapsed, setCollapsed] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (status === 'running') setCollapsed(false);
  }, [status]);

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

function OutputEmpty() {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '48px 32px',
      backgroundImage: 'radial-gradient(circle, var(--gray200) 1px, transparent 1px)',
      backgroundSize: '24px 24px',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, maxWidth: 380, textAlign: 'center' }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '4px 12px', borderRadius: 9999,
          background: BRAND + '1c', border: `1px solid ${BRAND + '44'}`,
          fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600,
          color: BRAND_DEEP, letterSpacing: '1.5px', textTransform: 'uppercase',
        }}>
          <span style={{ width: 5, height: 5, borderRadius: '50%', background: BRAND, display: 'inline-block' }} />
          Ready
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 24, fontWeight: 700, color: 'var(--fg1)', letterSpacing: '-0.5px', lineHeight: 1.2 }}>
          Run a studio action
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)', lineHeight: 1.75, maxWidth: 320 }}>
          Select an action on the left, fill in the form, then run — or press <Kbd>Ctrl</Kbd><Kbd>K</Kbd> to quick-jump.
        </div>
      </div>
    </div>
  );
}

// ── Result variants ────────────────────────────────────────────────────────────

function DocPreview({ path }: { path: string }) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    if (content !== null) { setOpen(o => !o); return; }
    setOpen(true);
    setLoading(true);
    try {
      const r = await fetch('/api/fs/read?path=' + encodeURIComponent(path));
      const j = await r.json() as { content?: string; error?: string };
      if (j.error) setErr(j.error);
      else setContent(j.content ?? '');
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <button onClick={load} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: 'transparent', border: 'none', cursor: 'pointer', padding: '3px 0', fontFamily: 'var(--sans)', fontSize: 12, color: BRAND_DEEP, fontWeight: 500 }}>
        <ChevronDown size={13} strokeWidth={2} style={{ transform: open ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.12s' }} />
        {open ? 'Hide preview' : 'Preview document'}
      </button>
      {open && (
        <div style={{ marginTop: 8, border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', maxHeight: 400 }}>
          {loading && <div style={{ padding: '16px', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)' }}>Loading…</div>}
          {err && <div style={{ padding: '12px', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--red-text)' }}>{err}</div>}
          {content !== null && !loading && (
            <div style={{ padding: '14px 16px', background: 'var(--bg-subtle)', overflowY: 'auto', maxHeight: 400 }}
              className="md-preview">
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ResultResearchSuccess({ topic, action, dest, doneData, onSaveAsPreset, onPipeToNotebook }: {
  topic: string; action: ActionMeta; dest: string;
  doneData?: Record<string, unknown> | null;
  onSaveAsPreset: () => void; onPipeToNotebook: () => void;
}) {
  const outputFile = (doneData?.output_file as string | null | undefined) ?? null;
  const notebookId = (doneData?.notebook_id as string | null | undefined) ?? null;
  const message    = (doneData?.message as string | undefined) ?? '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
          <span style={{ color: BRAND_DEEP, display: 'flex' }}><CheckCircle size={16} strokeWidth={1.5} /></span>
          <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Done</span>
        </span>
        {message && <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.5px' }}>{message}</span>}
        <div style={{ marginLeft: 'auto' }}>
          <GhostBtn size="sm" onClick={onSaveAsPreset}>Save as preset</GhostBtn>
        </div>
      </div>

      {outputFile ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <FieldLabel>Output file</FieldLabel>
          <CodeBlock>{outputFile}</CodeBlock>
          <DocPreview path={outputFile} />
        </div>
      ) : (
        <div>
          <FieldLabel>Output file</FieldLabel>
          <CodeBlock>{'~/docent/research/' + action.id + '_' + (topic || 'output').slice(0, 24).replace(/\s+/g, '-') + '.md'}</CodeBlock>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {notebookId ? (
          <a href={'https://notebooklm.google.com/notebook/' + notebookId} target="_blank" rel="noreferrer"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--sans)', fontSize: 12, color: BRAND_DEEP, textDecoration: 'none', padding: '4px 10px', borderRadius: 9999, background: BRAND + '18', border: '1px solid ' + BRAND + '44' }}>
            <ExternalLink size={12} strokeWidth={1.5} /> Open in NotebookLM
          </a>
        ) : dest === 'Local' && (
          <button onClick={onPipeToNotebook} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)', padding: '4px 10px', borderRadius: 9999, background: 'transparent', border: '1px solid var(--border-md)', cursor: 'pointer' }}>
            <ExternalLink size={12} strokeWidth={1.5} /> Send to NotebookLM
          </button>
        )}
        {outputFile && (
          <button onClick={() => fetch('/api/fs/open?path=' + encodeURIComponent(outputFile))}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)', padding: '4px 10px', borderRadius: 9999, background: 'transparent', border: '1px solid var(--border-md)', cursor: 'pointer' }}>
            <ExternalLink size={12} strokeWidth={1.5} /> Open output folder
          </button>
        )}
      </div>

    </div>
  );
}

function ResultStopped() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: AMBER_BORDER, display: 'flex' }}><AlertTriangle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Run stopped</span>
      </div>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.55 }}>
        The run was cancelled before it finished. The activity log above shows progress up to the stop point.
      </div>
    </div>
  );
}

function ResultFailure() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: 'var(--red-text)', display: 'flex' }}><XCircle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Run failed</span>
      </div>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.55 }}>
        Anthropic backend returned <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5 }}>401 unauthorized</span>. The API key is missing or invalid.
      </div>
      <div>
        <FieldLabel>Fix</FieldLabel>
        <CodeBlock>{'docent config set anthropic_api_key sk-ant-...'}</CodeBlock>
      </div>
    </div>
  );
}

function ResultSearch({ query }: { query: string }) {
  const rows = [
    { title: 'Storm surge attribution under non-stationary sea level rise', year: 2024, authors: 'Lin, N. · Emanuel, K.', source: 'arXiv' },
    { title: 'Bayesian inundation forecasting on US Atlantic coast',         year: 2023, authors: 'Park, J. · Walsh, K. · Vitart, F.', source: 'JGR' },
    { title: 'Compound flooding from tropical cyclones: a review',          year: 2022, authors: 'Wahl, T. · Jain, S. · Bender, J.', source: 'Nat. Geo.' },
    { title: 'High-resolution coupled modeling of coastal flood risk',      year: 2024, authors: 'Marsooli, R. · Lin, N.', source: 'PNAS' },
    { title: 'Tide-surge-wave interaction in shallow estuaries',            year: 2021, authors: 'Vatvani, D. · Zijlema, M.', source: 'Ocean Eng.' },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>
        {rows.length} results · query <span style={{ fontFamily: 'var(--mono)', color: 'var(--fg2)' }}>&ldquo;{query || 'storm surge inundation'}&rdquo;</span>
      </div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border)' }}>
              {['Title', 'Year', 'Authors', 'Source', ''].map((c, i) => (
                <th key={i} style={{ padding: '8px 12px', textAlign: i === 4 ? 'right' : 'left', fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500, color: 'var(--fg4)', letterSpacing: '0.6px', textTransform: 'uppercase' }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} style={{ borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg1)', lineHeight: 1.4 }}>
                  <a href="#" style={{ color: 'var(--fg1)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                    {r.title}<span style={{ color: 'var(--fg4)', opacity: 0.5, display: 'flex' }}><ExternalLink size={12} strokeWidth={1.5} /></span>
                  </a>
                </td>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg3)', whiteSpace: 'nowrap' }}>{r.year}</td>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', whiteSpace: 'nowrap' }}>{r.authors}</td>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.4px', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{r.source}</td>
                <td style={{ padding: '8px 12px', textAlign: 'right' }}><GhostBtn size="sm">Look up</GhostBtn></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ResultGetPaper() {
  const [more, setMore] = useState(false);
  const [added, setAdded] = useState(false);
  const abstract = `We present a high-resolution coupled ocean-atmosphere model for storm surge attribution on the US Atlantic coast. The framework combines tropical cyclone synthetic tracks with a barotropic surge solver and applies Bayesian downscaling to convert ensemble forecasts into actionable inundation depth probabilities. Validation against historical events including Sandy (2012), Florence (2018), and Ian (2022) shows skill improvements of 12–18% over the prior generation of operational systems.`;
  const overview = `This paper extends Lin & Emanuel (2019) by adding non-stationary sea level rise priors to the Bayesian framework. The key novelty is the joint treatment of tide–surge–wave coupling in shallow estuaries — historically a major source of bias in operational forecasts. The authors release open-source code (GPL-3) and the trained surrogate model. Section 4.2 on hindcast skill is the most actionable for downstream users. The discussion acknowledges that intensity scaling under warmer climates remains uncertain and recommends future work coupling with a CMIP6 ensemble.`;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 16, fontWeight: 600, color: 'var(--fg1)', lineHeight: 1.35, marginBottom: 6 }}>
          High-resolution coupled modeling of coastal flood risk under non-stationary sea level rise
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)' }}>
          <span>Marsooli, R. · Lin, N. · Emanuel, K.</span>
          <span style={{ color: 'var(--gray200)' }}>·</span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.4px', textTransform: 'uppercase' }}>PNAS 2024</span>
          <span style={{ color: 'var(--gray200)' }}>·</span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)' }}>arXiv:2401.12345</span>
        </div>
      </div>
      <div>
        <FieldLabel>Abstract</FieldLabel>
        <div style={{ maxHeight: 140, overflowY: 'auto', background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg2)', lineHeight: 1.55 }}>{abstract}</div>
      </div>
      <div>
        <FieldLabel>AI overview</FieldLabel>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg2)', lineHeight: 1.6 }}>
          {more ? overview : overview.slice(0, 600) + '…'}
          <button onClick={() => setMore(m => !m)} style={{ marginLeft: 6, background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500, color: BRAND_DEEP, padding: 0 }}>
            {more ? 'Show less' : 'Show more'}
          </button>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button onClick={() => setAdded(true)} disabled={added} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 9999, background: added ? BRAND + '33' : BRAND, color: '#0d0d0d', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600, border: 'none', cursor: added ? 'default' : 'pointer' }}>
          {added ? <CheckCircle size={12} strokeWidth={1.5} /> : <Plus size={14} strokeWidth={2} />}
          {added ? 'Added to Reading' : 'Add to Reading'}
        </button>
        <a href="#" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 9999, background: 'transparent', color: 'var(--fg2)', border: '1px solid var(--border-md)', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 500, textDecoration: 'none' }}>
          <ExternalLink size={12} strokeWidth={1.5} /> Open on arXiv
        </a>
      </div>
    </div>
  );
}

function PerspectiveSection({ title, color, body }: { title: string; color: string; body: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
      <button onClick={() => setOpen(o => !o)} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', textAlign: 'left' }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
        {title}
        <span style={{ marginLeft: 'auto', color: 'var(--fg4)', display: 'flex' }}>
          {open ? <ChevronDown size={14} strokeWidth={2} /> : <ChevronRight size={14} strokeWidth={2} />}
        </span>
      </button>
      {open && (
        <div style={{ padding: '0 14px 12px', fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.6, borderTop: '1px solid var(--border)' }}>
          <div style={{ paddingTop: 10 }}>{body}</div>
        </div>
      )}
    </div>
  );
}

function ResultNotebook() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: BRAND_DEEP, display: 'flex' }}><CheckCircle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Notebook updated</span>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Chip color={BRAND_DEEP}>18 sources added</Chip>
        <Chip color={AMBER}>2 failed</Chip>
        <Chip color={BLUE}>5 from NLM web</Chip>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 9999, background: BRAND + '22', color: BRAND_DEEP, fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
          <CheckCircle size={11} strokeWidth={1.5} /> Quality gate · clean
        </span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)' }}>0 contradictions · 1 gap noted</span>
      </div>
      <div>
        <FieldLabel>Perspectives</FieldLabel>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <PerspectiveSection title="Practitioner" color={BLUE} body="Section 4.2 hindcast skill is directly usable; you can replace the prior Lin & Emanuel (2019) module with this one and expect 12–18% improvement. Note that the surrogate model is GPU-only above 4km resolution." />
          <PerspectiveSection title="Skeptic" color={AMBER} body="The validation set leans on three named storms. Generalization to compound events (rain + surge) is unclear and the paper does not run a leave-one-out cross-check across decades." />
          <PerspectiveSection title="Beginner" color={BRAND_DEEP} body="Read Section 1 and the figures in Section 5 first. Skip the Bayesian downscaling derivation (Sections 3.2–3.4) unless you specifically need the math — the headline result holds without it." />
        </div>
      </div>
      <div style={{ background: 'var(--amber-bg)', borderLeft: '3px solid var(--amber-border)', borderRadius: '4px 8px 8px 4px', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, color: 'var(--amber-text)', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600 }}>
          <AlertTriangle size={14} strokeWidth={2} /> Save this notebook ID
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--amber-text)', lineHeight: 1.5 }}>A new notebook was created. Run this once to make it the default:</div>
        <CodeBlock>{'docent config set notebook_id nb_4f2c'}</CodeBlock>
      </div>
    </div>
  );
}

function ResultConfigShow() {
  const rows = [
    ['default_backend',     'anthropic'],
    ['notebook_id',         'nb_4f2c'],
    ['vault_path',          '~/docent/vault'],
    ['anthropic_api_key',   'sk-a...xZ9q'],
    ['openai_api_key',      'sk-p...4Aj1'],
    ['groq_api_key',        '(not set)'],
    ['gemini_api_key',      '(not set)'],
    ['tavily_api_key',      'tvly...kQ2m'],
    ['mendeley_token',      'eyJh...A8wL'],
    ['max_research_minutes','30'],
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>Configuration ({rows.length} keys)</div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
        {rows.map(([k, v], i) => {
          const unset = v === '(not set)';
          return (
            <div key={k} style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 0.4fr) 1fr', gap: 14, padding: '9px 14px', borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none', background: i % 2 === 0 ? 'transparent' : 'var(--bg-subtle)', alignItems: 'center' }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)', letterSpacing: '0.3px' }}>{k}</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: unset ? 'var(--fg4)' : 'var(--fg1)', fontStyle: unset ? 'italic' : 'normal' }}>{v}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ResultConfigSet({ cfgKey }: { cfgKey: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: BRAND_DEEP, display: 'flex' }}><CheckCircle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Key saved</span>
      </div>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.6 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--fg1)' }}>{cfgKey || 'anthropic_api_key'}</span>{' was written to:'}
      </div>
      <CodeBlock>{'~/.docent/config.toml'}</CodeBlock>
    </div>
  );
}

function ResultCompare({ a, b }: { a: string; b: string }) {
  const aOnly  = ['Uses Bayesian downscaling with priors trained on 1979–2020 reanalysis', 'Validation against Sandy, Florence, Ian (3 storms)', 'Open-source GPL-3 release of surrogate model'];
  const shared = ['Tropical cyclone synthetic tracks coupled with barotropic surge solver', 'Reports 12–18% skill improvement over operational baselines', 'Identifies tide-surge-wave coupling as primary bias source'];
  const bOnly  = ['Ensemble of 10k members vs. 1k in A', 'No code release; results table only', 'Includes inland riverine flooding component'];
  const contradictions = [{ label: 'Surrogate model resolution', a: 'A: GPU-only above 4km; CPU fallback degrades quality', b: 'B: claims CPU-only inference is "fully equivalent" at any resolution' }];

  function Col({ label, items, color }: { label: string; items: string[]; color: string }) {
    return (
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, color, letterSpacing: '0.6px', textTransform: 'uppercase' }}>
          <span style={{ width: 5, height: 5, borderRadius: '50%', background: color }} />{label}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {items.map((it, i) => (
            <div key={i} style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--bg-subtle)', border: '1px solid var(--border)', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)', lineHeight: 1.5 }}>{it}</div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: BRAND_DEEP, display: 'flex' }}><CheckCircle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Comparison complete</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>· {shared.length + aOnly.length + bOnly.length} findings</span>
      </div>
      <div style={{ display: 'flex', gap: 12 }}>
        {[{ label: 'Paper A', id: a || '2401.12345', color: BLUE }, { label: 'Paper B', id: b || '2310.06825', color: BRAND_DEEP }].map(p => (
          <div key={p.label} style={{ flex: 1, padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-subtle)' }}>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: p.color, letterSpacing: '0.7px', textTransform: 'uppercase', marginBottom: 4 }}>{p.label}</div>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 500, color: 'var(--fg1)', lineHeight: 1.4 }}>{p.id}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, alignItems: 'flex-start' }}>
        <Col label="Only in A" items={aOnly}  color={BLUE} />
        <Col label="Shared"    items={shared} color={BRAND_DEEP} />
        <Col label="Only in B" items={bOnly}  color={BRAND_DEEP} />
      </div>
      {contradictions.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, color: 'var(--amber-text)', letterSpacing: '0.6px', textTransform: 'uppercase' }}>
            <AlertTriangle size={14} strokeWidth={2} /> Contradictions
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {contradictions.map((c, i) => (
              <div key={i} style={{ background: 'var(--amber-bg)', borderLeft: '3px solid var(--amber-border)', borderRadius: '4px 8px 8px 4px', padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600, color: 'var(--amber-text)' }}>{c.label}</div>
                <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)', lineHeight: 1.55 }}>{c.a}</div>
                <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)', lineHeight: 1.55 }}>{c.b}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      <div>
        <FieldLabel>Output file</FieldLabel>
        <CodeBlock>{'~/docent/runs/2026-05-18_compare_' + (a || '2401').replace(/\./g, '-') + '-vs-' + (b || '2310').replace(/\./g, '-') + '/comparison.md'}</CodeBlock>
      </div>
    </div>
  );
}

// ── Output panel ───────────────────────────────────────────────────────────────

const PHASE_SKIP = new Set(['error', 'warn', 'cost']);

export function OutputPanel({ action, state, status, logs, sources, currentPhase, doneData, onReset, onSaveAsPreset, onPipeToNotebook }: {
  action: ActionMeta; state: FormState; status: string;
  logs: LogEntry[]; sources: Source[]; currentPhase: string | null;
  doneData?: Record<string, unknown> | null;
  onReset: () => void; onSaveAsPreset: () => void; onPipeToNotebook: () => void;
}) {
  const isResult  = status === 'success' || status === 'failure' || status === 'stopped';
  const isRunning = status === 'running';
  const isEmpty   = status === 'idle';

  const seenPhases = useMemo(() => {
    const seen: string[] = [];
    const seenSet = new Set<string>();
    for (const log of logs) {
      if (!PHASE_SKIP.has(log.phase) && !seenSet.has(log.phase)) {
        seen.push(log.phase);
        seenSet.add(log.phase);
      }
    }
    return seen;
  }, [logs]);

  const completedPhases = useMemo(() => {
    if (status === 'success') return new Set(seenPhases);
    const lastIdx = seenPhases.findIndex(p => p === currentPhase);
    if (lastIdx > 0) return new Set(seenPhases.slice(0, lastIdx));
    return new Set<string>();
  }, [seenPhases, status, currentPhase]);

  const breadcrumbDetail = (() => {
    switch (action.id) {
      case 'deep': case 'lit': case 'draft':       return state.topic || '';
      case 'peer': case 'replicate': case 'audit': return state.artifact || '';
      case 'compare': return state.artifactA && state.artifactB ? `${state.artifactA} vs ${state.artifactB}` : '';
      case 'search': case 'scholarly': return state.query || '';
      case 'getpaper': return state.arxivId || '';
      case 'cfgset':   return state.cfgKey || '';
      case 'notebook': return state.srcPath || 'notebook build';
      default: return '';
    }
  })();

  function renderResult() {
    if (status === 'stopped') return <ResultStopped />;
    if (status === 'failure') return <ResultFailure />;
    switch (action.id) {
      case 'search':
      case 'scholarly':  return <ResultSearch query={state.query} />;
      case 'getpaper':   return <ResultGetPaper />;
      case 'notebook':   return <ResultNotebook />;
      case 'cfgshow':    return <ResultConfigShow />;
      case 'cfgset':     return <ResultConfigSet cfgKey={state.cfgKey} />;
      case 'compare':    return <ResultCompare a={state.artifactA} b={state.artifactB} />;
      default:           return <ResultResearchSuccess topic={state.topic} action={action} dest={state.dest} doneData={doneData} onSaveAsPreset={onSaveAsPreset} onPipeToNotebook={onPipeToNotebook} />;
    }
  }

  return (
    <section style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'transparent', overflow: 'hidden' }}>
      {!isEmpty && (
        <div style={{ flexShrink: 0, padding: '14px 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            {isRunning && <span style={{ width: 8, height: 8, borderRadius: '50%', background: BRAND, animation: 'logo-dot-blink 1.2s step-end infinite', flexShrink: 0 }} />}
            {status === 'stopped' && <span style={{ width: 8, height: 8, borderRadius: '50%', background: AMBER_BORDER, flexShrink: 0 }} />}
            <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', whiteSpace: 'nowrap' }}>{action.label}</span>
            {breadcrumbDetail && <>
              <span style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--gray200)' }}>·</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--fg3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>{breadcrumbDetail}</span>
            </>}
          </div>
          {isResult && <GhostBtn onClick={onReset}>Clear</GhostBtn>}
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {isEmpty && <OutputEmpty />}

        {(isRunning || isResult) && (
          <div style={{ padding: '12px 24px 0' }}>
            <PhaseStrip seenPhases={seenPhases} completedPhases={completedPhases} currentPhase={currentPhase} status={status} />
          </div>
        )}

        {isRunning && sources.length > 0 && (
          <div style={{ padding: '0 24px' }}>
            <SourceChips sources={sources} />
          </div>
        )}

        {(isRunning || isResult) && logs.length > 0 && (
          <div style={{ padding: '14px 22px', borderBottom: isResult ? '1px solid var(--border)' : 'none' }}>
            <LogStream logs={logs} status={status} />
          </div>
        )}

        {isResult && (
          <div style={{ padding: '18px 24px 24px' }}>
            {renderResult()}
          </div>
        )}
      </div>
    </section>
  );
}

// ── Research outputs panel ─────────────────────────────────────────────────────

interface OutputFile { path: string; name: string; folder: string; size: number; mtime: number; }

export function OutputsPanel({ onClose }: { onClose: () => void }) {
  const [files, setFiles] = useState<OutputFile[]>([]);
  const [outputDir, setOutputDir] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState<{ path: string; content: string | null; loading: boolean } | null>(null);

  useEffect(() => {
    fetch('/api/studio/outputs')
      .then(r => r.json())
      .then((j: { files: OutputFile[]; output_dir: string | null }) => { setFiles(j.files); setOutputDir(j.output_dir); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function openPreview(f: OutputFile) {
    if (preview?.path === f.path) { setPreview(null); return; }
    setPreview({ path: f.path, content: null, loading: true });
    try {
      const r = await fetch('/api/fs/read?path=' + encodeURIComponent(f.path));
      const j = await r.json() as { content?: string };
      setPreview({ path: f.path, content: j.content ?? '', loading: false });
    } catch {
      setPreview({ path: f.path, content: 'Failed to load preview.', loading: false });
    }
  }

  function fmt(bytes: number) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }
  function fmtDate(ts: number) {
    return new Date(ts * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
  }

  return (
    <aside style={{ width: 340, flexShrink: 0, height: '100%', borderLeft: '1px solid var(--border)', background: 'var(--bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ flex: 1, fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)' }}>Research outputs</span>
        {outputDir && (
          <button onClick={() => fetch('/api/fs/open?path=' + encodeURIComponent(outputDir))}
            title="Open output folder"
            style={{ width: 24, height: 24, border: 'none', background: 'transparent', color: 'var(--fg4)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 5 }}>
            <ExternalLink size={12} strokeWidth={1.5} />
          </button>
        )}
        <button onClick={onClose} title="Close" style={{ width: 24, height: 24, border: 'none', background: 'transparent', color: 'var(--fg4)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 5 }}>
          <X size={12} strokeWidth={2} />
        </button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {loading && <div style={{ padding: '20px 18px', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)' }}>Loading…</div>}
        {!loading && files.length === 0 && (
          <div style={{ padding: '24px 18px', textAlign: 'center', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', lineHeight: 1.6 }}>
            No research files yet.<br />Completed runs will appear here.
          </div>
        )}
        {files.map(f => (
          <div key={f.path}>
            <button onClick={() => openPreview(f)}
              style={{ width: '100%', textAlign: 'left', padding: '9px 18px', border: 'none', background: preview?.path === f.path ? BRAND + '0d' : 'transparent', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 3 }}>
              <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 500, color: 'var(--fg1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</div>
              <div style={{ display: 'flex', gap: 8, fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)' }}>
                <span>{f.folder}</span>
                <span>{fmt(f.size)}</span>
                <span>{fmtDate(f.mtime)}</span>
              </div>
            </button>
            {preview?.path === f.path && (
              <div style={{ borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)', background: 'var(--bg-subtle)', maxHeight: 240, overflow: 'hidden' }}>
                {preview.loading
                  ? <div style={{ padding: '12px 18px', fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg4)' }}>Loading…</div>
                  : <div style={{ padding: '10px 18px', overflowY: 'auto', maxHeight: 240 }} className="md-preview md-preview-sm"><ReactMarkdown>{preview.content ?? ''}</ReactMarkdown></div>
                }
              </div>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}

// ── History drawer ─────────────────────────────────────────────────────────────

export function HistoryDrawer({ runs, currentRunId, onSelect, onClose, onClear, onDelete }: {
  runs: RunRecord[]; currentRunId: string | null;
  onSelect: (id: string) => void; onClose: () => void; onClear: () => void; onDelete: (id: string) => void;
}) {
  return (
    <aside style={{ width: 300, flexShrink: 0, height: '100%', borderLeft: '1px solid var(--border)', background: 'var(--bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: 'var(--fg3)', display: 'flex' }}><History size={14} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)' }}>Run history</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.5px' }}>{runs.length}</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
          {runs.length > 0 && (
            <button onClick={onClear} title="Clear all" style={{ width: 24, height: 24, border: 'none', background: 'transparent', color: 'var(--fg4)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 5 }}>
              <Trash size={12} strokeWidth={1.5} />
            </button>
          )}
          <button onClick={onClose} title="Close" style={{ width: 24, height: 24, border: 'none', background: 'transparent', color: 'var(--fg4)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 5 }}>
            <X size={12} strokeWidth={2} />
          </button>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 10px' }}>
        {runs.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 8, color: 'var(--fg4)', padding: '24px 14px', textAlign: 'center' }}>
            <History size={14} strokeWidth={1.5} style={{ opacity: 0.4 }} />
            <span style={{ fontFamily: 'var(--sans)', fontSize: 12 }}>No runs yet</span>
            <span style={{ fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg4)', lineHeight: 1.5 }}>Completed runs will appear here.</span>
          </div>
        ) : runs.map(r => {
          const active   = r.id === currentRunId;
          const dotColor = r.status === 'running' ? AMBER_BORDER
            : r.status === 'failure' ? '#E53535'
            : r.status === 'stopped' ? AMBER_BORDER
            : BRAND;
          const dotAnim  = r.status === 'running' ? 'logo-dot-blink 1.1s step-end infinite' : 'none';
          return (
            <div key={r.id} style={{ position: 'relative', marginBottom: 4 }} className="history-item">
              <button onClick={() => onSelect(r.id)}
                style={{ width: '100%', textAlign: 'left', padding: '10px 12px', borderRadius: 8, border: `1px solid ${active ? BRAND + '66' : 'transparent'}`, background: active ? BRAND + '10' : 'transparent', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 5, paddingRight: 32 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: dotColor, animation: dotAnim, flexShrink: 0 }} />
                  <span style={{ fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: active ? 600 : 500, color: 'var(--fg1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0, flex: 1 }}>{r.actionLabel}</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--fg4)', letterSpacing: '0.4px', flexShrink: 0 }}>{r.timeAgo}</span>
                </div>
                {r.detail && (
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--fg3)', letterSpacing: '0.2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingLeft: 13 }}>{r.detail}</div>
                )}
              </button>
              <button onClick={(e) => { e.stopPropagation(); onDelete(r.id); }} title="Delete entry"
                style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', width: 20, height: 20, border: 'none', background: 'transparent', color: 'var(--fg4)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 4, opacity: 0, transition: 'opacity 0.1s' }}
                className="history-delete-btn">
                <Trash size={11} strokeWidth={1.5} />
              </button>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
