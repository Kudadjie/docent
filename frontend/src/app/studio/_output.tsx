'use client';

import { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { ExternalLink, X, History, Trash, Square } from 'lucide-react';
import {
  type ActionMeta, type FormState, type LogEntry, type Source, type RunRecord,
} from './_shared';
import { type ActiveRunView } from '@/lib/studio-run-context';
import { GhostBtn } from './_form';

// Activity + result panels live in components/studio/* (v2.3 split).
import { PhaseStrip, SourceChips, LogStream } from '@/components/studio/activity';
import {
  OutputEmpty, ResultResearchSuccess, ResultStopped, ResultFailure,
  ResultSearch, ResultGetPaper, ResultCiteGraph, ResultNotebook,
  ResultConfigShow, ResultConfigSet,
} from '@/components/studio/results';
import { BRAND, BRAND_DEEP, AMBER_BORDER } from '@/components/studio/palette';

const PHASE_SKIP = new Set(['error', 'warn', 'cost', 'console', 'nlm-wait']);

function _runDotColor(status: string): string {
  if (status === 'running') return BRAND;
  if (status === 'failure') return '#D45656';
  if (status === 'stopped' || status === 'queued') return AMBER_BORDER;
  return BRAND_DEEP; // success
}

/** Tabs across the top of the output panel — one per concurrent run. */
function RunSwitcher({ runs, currentRunId, onViewRun }: {
  runs: ActiveRunView[]; currentRunId: string | null; onViewRun: (id: string) => void;
}) {
  if (runs.length < 2) return null;
  return (
    <div style={{ flexShrink: 0, display: 'flex', gap: 6, padding: '8px 24px 0', overflowX: 'auto' }}>
      {runs.map(r => {
        const active = r.runId === currentRunId;
        return (
          <button key={r.runId} onClick={() => onViewRun(r.runId)} title={r.detail}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 11px', borderRadius: 8,
              border: '1px solid ' + (active ? 'var(--border-md)' : 'var(--border)'),
              background: active ? 'var(--gray100)' : 'transparent', cursor: 'pointer', whiteSpace: 'nowrap',
              fontFamily: 'var(--sans)', fontSize: 12, color: active ? 'var(--fg1)' : 'var(--fg3)', fontWeight: active ? 600 : 400,
            }}>
            <span style={{
              width: 7, height: 7, borderRadius: '50%', background: _runDotColor(r.status), flexShrink: 0,
              animation: r.status === 'running' ? 'logo-dot-blink 1.2s step-end infinite' : undefined,
            }} />
            {r.actionLabel}
          </button>
        );
      })}
    </div>
  );
}

export function OutputPanel({ action, state, status, logs, sources, currentPhase, doneData, activeRuns, currentRunId, onViewRun, onStop, onReset, onSaveAsPreset, onPipeToNotebook }: {
  action: ActionMeta; state: FormState; status: string;
  logs: LogEntry[]; sources: Source[]; currentPhase: string | null;
  doneData?: Record<string, unknown> | null;
  activeRuns: ActiveRunView[]; currentRunId: string | null;
  onViewRun: (id: string) => void; onStop: () => void;
  onReset: () => void; onSaveAsPreset: () => void; onPipeToNotebook: (srcPath: string) => void;
}) {
  const isResult  = status === 'success' || status === 'failure' || status === 'stopped';
  const isRunning = status === 'running';
  const isQueued  = status === 'queued';
  const isEmpty   = status === 'idle';
  const queuedReason = activeRuns.find(r => r.runId === currentRunId)?.queuedReason;

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
    if (status === 'failure') {
      const errorEntry = [...logs].reverse().find(l => l.phase === 'error');
      // Fallback: if no structured error log, surface the last non-empty console line
      // (raw subprocess output) so the failure is never completely silent.
      const consoleFallback = errorEntry ? undefined
        : [...logs].reverse().find(l => l.phase === 'console' && l.text.trim());
      return <ResultFailure errorText={errorEntry?.text ?? consoleFallback?.text} />;
    }
    const data = (doneData?.data ?? null) as Record<string, unknown> | null;
    switch (action.id) {
      case 'search':
      case 'scholarly':  return <ResultSearch query={state.query} data={data} />;
      case 'getpaper':   return <ResultGetPaper data={data} />;
      case 'citegraph':  return <ResultCiteGraph data={data} />;
      case 'notebook':   return <ResultNotebook data={data} doneData={doneData} />;
      case 'cfgshow':    return <ResultConfigShow data={data} />;
      case 'cfgset':     return <ResultConfigSet cfgKey={state.cfgKey} data={data} />;
      // compare returns a ResearchResult (output file + message), not a structured
      // diff — render it with the same real-data panel as deep/lit/draft.
      default:           return <ResultResearchSuccess topic={state.topic} action={action} dest={state.dest} doneData={doneData} onSaveAsPreset={onSaveAsPreset} onPipeToNotebook={onPipeToNotebook} />;
    }
  }

  return (
    <section style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'transparent', overflow: 'hidden' }}>
      <RunSwitcher runs={activeRuns} currentRunId={currentRunId} onViewRun={onViewRun} />
      {!isEmpty && (
        <div style={{ flexShrink: 0, padding: '14px 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            {isRunning && <span style={{ width: 8, height: 8, borderRadius: '50%', background: BRAND, animation: 'logo-dot-blink 1.2s step-end infinite', flexShrink: 0 }} />}
            {(status === 'stopped' || isQueued) && <span style={{ width: 8, height: 8, borderRadius: '50%', background: AMBER_BORDER, flexShrink: 0 }} />}
            <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', whiteSpace: 'nowrap' }}>{action.label}</span>
            {breadcrumbDetail && <>
              <span style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--gray200)' }}>·</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--fg3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>{breadcrumbDetail}</span>
            </>}
          </div>
          {(isRunning || isQueued)
            ? <GhostBtn onClick={onStop}><span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><Square size={11} strokeWidth={2} /> {isQueued ? 'Cancel' : 'Stop'}</span></GhostBtn>
            : isResult && <GhostBtn onClick={onReset}>Clear</GhostBtn>}
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {isEmpty && <OutputEmpty />}

        {isQueued && (
          <div style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: AMBER_BORDER, flexShrink: 0 }} />
              <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Queued</span>
            </div>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.55 }}>
              {queuedReason || 'Waiting to start…'} It will start automatically when a slot frees up — no action needed.
            </div>
          </div>
        )}

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
          <button onClick={() => fetch('/api/fs/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: outputDir }) })}
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
