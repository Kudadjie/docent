'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { Wrench, Play, ChevronRight, AlertTriangle, CheckCircle, Terminal } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';
import {
  SchemaForm, resolveFields, initialValues, isComplete, buildPayload,
  type ResolvedField,
} from './_schema-form';

const BRAND = '#18E299';
const BRAND_DEEP = '#0fa76e';
const INDIGO = '#6366f1';
const RED = '#D45656';

interface ActionMeta { action: string; description: string; schema: Record<string, unknown>; }
interface ToolMeta { tool: string; description: string; category: string | null; actions: ActionMeta[]; }

interface InvokeResult {
  ok: boolean;
  error?: string;
  confirmation_required?: boolean;
  notes?: string[];
  result?: unknown;
}

interface LogLine {
  phase: string;
  message: string;
  level: 'info' | 'warn' | 'error';
}

export default function ToolsPage() {
  const { dark, toggleDark } = useDarkMode();

  const [catalogue, setCatalogue] = useState<ToolMeta[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selTool, setSelTool] = useState<string | null>(null);
  const [selAction, setSelAction] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<InvokeResult | null>(null);
  const [logLines, setLogLines] = useState<LogLine[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch('/api/tools')
      .then(r => r.json())
      .then((data: ToolMeta[]) => {
        setCatalogue(data);
        // Auto-select the first action of the first tool.
        const first = data[0];
        if (first && first.actions[0]) { setSelTool(first.tool); setSelAction(first.actions[0].action); }
      })
      .catch(() => setLoadError(true));
  }, []);

  const activeAction = useMemo<ActionMeta | null>(() => {
    if (!catalogue || !selTool || !selAction) return null;
    const t = catalogue.find(x => x.tool === selTool);
    return t?.actions.find(a => a.action === selAction) ?? null;
  }, [catalogue, selTool, selAction]);

  const fields = useMemo<ResolvedField[]>(
    () => (activeAction ? resolveFields(activeAction.schema) : []),
    [activeAction],
  );

  // Reset the form when the selected action changes — done during render (the
  // React-recommended "adjust state on prop change" pattern) rather than in an
  // effect, which would trigger a cascading re-render.
  const selKey = `${selTool}::${selAction}`;
  const [prevSelKey, setPrevSelKey] = useState<string | null>(null);
  if (selKey !== prevSelKey) {
    setPrevSelKey(selKey);
    setValues(initialValues(fields));
    setResult(null);
  }

  function selectAction(tool: string, action: string) {
    setSelTool(tool);
    setSelAction(action);
  }

  async function run(confirmed = false) {
    if (!selTool || !selAction) return;
    let payload: Record<string, unknown>;
    try {
      payload = buildPayload(fields, values);
    } catch (e) {
      setResult({ ok: false, error: e instanceof Error ? e.message : String(e) });
      return;
    }
    if (confirmed) payload.confirmed = true;

    // Cancel any prior in-flight stream.
    if (abortRef.current) abortRef.current.abort();
    const abort = new AbortController();
    abortRef.current = abort;

    setRunning(true);
    setLogLines([]);
    setResult(null);

    try {
      const resp = await fetch('/api/tools/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: selTool, action: selAction, inputs: payload }),
        signal: abort.signal,
      });

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      outer: while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let msg: Record<string, unknown>;
          try { msg = JSON.parse(line.slice(6)); } catch { continue; }

          if (msg.type === 'progress') {
            setLogLines(prev => [...prev, {
              phase: String(msg.phase ?? ''),
              message: String(msg.message ?? msg.phase ?? ''),
              level: (msg.level === 'warn' || msg.level === 'error') ? msg.level : 'info',
            }]);
          } else {
            // result or error — terminal event
            setResult({
              ok: msg.ok === true,
              error: typeof msg.error === 'string' ? msg.error : undefined,
              confirmation_required: msg.confirmation_required === true,
              notes: Array.isArray(msg.notes) ? msg.notes as string[] : undefined,
              result: msg.result,
            });
            setRunning(false);
            break outer;
          }
        }
      }
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setResult({ ok: false, error: 'Could not reach the server.' });
    } finally {
      setRunning(false);
    }
  }

  const complete = isComplete(fields, values);
  const cliPreview = activeAction
    ? `docent ${selTool} ${selAction}` + fields
        .filter(f => {
          const v = values[f.name];
          if (f.kind === 'boolean') return !!v;
          if (f.kind === 'string_array') return Array.isArray(v) && v.length > 0;
          return v != null && String(v).trim() !== '';
        })
        .map(f => {
          const flag = '--' + f.name.replace(/_/g, '-');
          if (f.kind === 'boolean') return ` ${flag}`;
          if (f.kind === 'string_array') return (values[f.name] as string[]).map(x => ` ${flag} ${shellQuote(x)}`).join('');
          return ` ${flag} ${shellQuote(String(values[f.name]))}`;
        })
        .join('')
    : '';

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="tools" queueCount={0} dark={dark} />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner dark={dark} onToggleDark={toggleDark} dotState={running ? 'working' : 'idle'} />

        {/* Header */}
        <div style={{ padding: '20px 28px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <Wrench size={16} strokeWidth={1.5} color={BRAND_DEEP} />
            <h1 style={{ fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 600, letterSpacing: '-0.3px', color: 'var(--fg1)', margin: 0 }}>Tools</h1>
          </div>
          <p style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)', margin: 0 }}>
            Run any registered tool action. Forms are generated automatically from each action&apos;s schema —
            new plugins appear here with no extra code.
          </p>
        </div>

        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          {/* Left: tool/action catalogue */}
          <aside style={{ width: 280, flexShrink: 0, borderRight: '1px solid var(--border)', overflowY: 'auto', padding: '16px 14px' }}>
            {loadError ? (
              <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: RED }}>Could not load tools. Is the server running?</div>
            ) : !catalogue ? (
              <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg4)' }}>Loading…</div>
            ) : (
              catalogue.map(tool => (
                <div key={tool.tool} style={{ marginBottom: 18 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '0 6px 7px', fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase' }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: BRAND, flexShrink: 0 }} />
                    {tool.tool}
                    <span style={{ marginLeft: 'auto', fontWeight: 400, letterSpacing: 0 }}>{tool.actions.length}</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {tool.actions.map(a => {
                      const active = tool.tool === selTool && a.action === selAction;
                      return (
                        <button key={a.action} onClick={() => selectAction(tool.tool, a.action)}
                          title={a.description}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 4, width: '100%', textAlign: 'left',
                            padding: '6px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
                            background: active ? BRAND + '1f' : 'transparent',
                            color: active ? BRAND_DEEP : 'var(--fg2)',
                            fontFamily: 'var(--mono)', fontSize: 12, fontWeight: active ? 600 : 400,
                          }}>
                          <ChevronRight size={12} strokeWidth={2} style={{ opacity: active ? 1 : 0.3, flexShrink: 0 }} />
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.action}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </aside>

          {/* Right: form + result */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '22px 28px', minWidth: 0 }}>
            {activeAction ? (
              <div style={{ maxWidth: 640 }}>
                <div style={{ marginBottom: 18 }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', marginBottom: 4 }}>
                    {selTool} {selAction}
                  </div>
                  <p style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)', margin: 0, lineHeight: 1.5 }}>
                    {activeAction.description}
                  </p>
                </div>

                <SchemaForm fields={fields} values={values}
                  onChange={(name, v) => setValues(prev => ({ ...prev, [name]: v }))} />

                {/* CLI preview */}
                <div style={{ marginTop: 18 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                    <Terminal size={11} strokeWidth={1.5} /> Equivalent CLI
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--fg2)', background: 'var(--code-bg)', border: '1px solid var(--code-border)', borderRadius: 8, padding: '9px 12px', wordBreak: 'break-all', lineHeight: 1.5 }}>
                    {cliPreview}
                  </div>
                </div>

                {/* Run */}
                <div style={{ marginTop: 18, display: 'flex', alignItems: 'center', gap: 12 }}>
                  <button onClick={() => run(false)} disabled={running || !complete}
                    title={!complete ? 'Fill all required fields' : undefined}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 7, padding: '9px 20px', borderRadius: 9999,
                      background: (running || !complete) ? 'var(--gray200)' : INDIGO, color: '#fff',
                      fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, border: 'none',
                      cursor: (running || !complete) ? 'not-allowed' : 'pointer',
                    }}>
                    <Play size={13} strokeWidth={2} />
                    {running ? 'Running…' : 'Run'}
                  </button>
                  {!complete && <span style={{ fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg4)' }}>Required fields are marked with *</span>}
                </div>

                {/* Telemetry strip — visible only when progress events arrive */}
                <TelemetryStrip lines={logLines} running={running} />

                {/* Result */}
                {result && <ResultPanel result={result} onConfirm={() => run(true)} running={running} />}
              </div>
            ) : (
              <div style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg4)' }}>
                Select an action from the left to begin.
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

// ── Telemetry strip ──────────────────────────────────────────────────────────

function TelemetryStrip({ lines, running }: { lines: LogLine[]; running: boolean }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [lines]);

  if (lines.length === 0) return null;

  const lineColor = (level: LogLine['level']) =>
    level === 'error' ? RED : level === 'warn' ? '#C97B00' : BRAND;

  return (
    <div style={{ marginTop: 16, border: '1px solid var(--code-border)', borderRadius: 8, overflow: 'hidden' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 7, padding: '6px 12px',
        borderBottom: '1px solid var(--code-border)', background: 'var(--code-bg)',
      }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: running ? BRAND : 'var(--fg4)',
          flexShrink: 0,
        }} />
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
          {running ? 'Running' : 'Done'}
        </span>
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--fg4)' }}>
          {lines.length} {lines.length === 1 ? 'event' : 'events'}
        </span>
      </div>
      <div ref={scrollRef} style={{
        maxHeight: 180, overflowY: 'auto', padding: '10px 12px',
        background: 'var(--code-bg)', display: 'flex', flexDirection: 'column', gap: 3,
      }}>
        {lines.map((line, i) => (
          <div key={i} style={{ display: 'flex', gap: 8, fontFamily: 'var(--mono)', fontSize: 11.5, lineHeight: 1.45 }}>
            <span style={{ color: lineColor(line.level), flexShrink: 0, minWidth: 0 }}>
              [{line.phase}]
            </span>
            <span style={{ color: 'var(--fg2)', wordBreak: 'break-word' }}>
              {line.message}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Result panel ─────────────────────────────────────────────────────────────

function ResultPanel({ result, onConfirm, running }: { result: InvokeResult; onConfirm: () => void; running: boolean }) {
  const confirmation = result.confirmation_required;
  const ok = result.ok && !confirmation;
  // notes may come at the top level (stream path) or nested in result (invoke path)
  const notes = confirmation
    ? (result.notes ?? (isRecord(result.result) ? result.result.notes as string[] | undefined : undefined))
    : undefined;
  const pretty = (() => {
    try { return JSON.stringify(result.result, null, 2); } catch { return String(result.result); }
  })();
  const message = isRecord(result.result) && typeof result.result.message === 'string' ? result.result.message : null;

  const tone = confirmation ? '#C97B00' : ok ? BRAND_DEEP : RED;
  const bg = confirmation ? 'rgba(201,123,0,0.07)' : ok ? 'rgba(24,226,153,0.06)' : 'rgba(212,86,86,0.05)';

  return (
    <div style={{ marginTop: 24, border: `1px solid ${tone}40`, borderRadius: 10, overflow: 'hidden', background: bg }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderBottom: `1px solid ${tone}30` }}>
        {confirmation ? <AlertTriangle size={14} strokeWidth={2} color={tone} />
          : ok ? <CheckCircle size={14} strokeWidth={2} color={tone} />
          : <AlertTriangle size={14} strokeWidth={2} color={tone} />}
        <span style={{ fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600, color: tone }}>
          {confirmation ? 'Confirmation required' : ok ? 'Success' : 'Failed'}
        </span>
      </div>

      <div style={{ padding: '14px' }}>
        {result.error && (
          <p style={{ margin: '0 0 10px', fontFamily: 'var(--sans)', fontSize: 12.5, color: RED, lineHeight: 1.5 }}>{result.error}</p>
        )}
        {message && (
          <p style={{ margin: '0 0 10px', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg1)', lineHeight: 1.55 }}>{message}</p>
        )}
        {notes && notes.length > 0 && (
          <ul style={{ margin: '0 0 12px', paddingLeft: 18 }}>
            {notes.map((n, i) => <li key={i} style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.6 }}>{n}</li>)}
          </ul>
        )}
        {confirmation && (
          <button onClick={onConfirm} disabled={running}
            style={{ marginBottom: 14, padding: '7px 16px', borderRadius: 8, border: 'none', background: '#C97B00', color: '#fff', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600, cursor: running ? 'wait' : 'pointer' }}>
            {running ? 'Running…' : 'Confirm and run'}
          </button>
        )}
        {result.result != null && (
          <pre style={{ margin: 0, fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--fg2)', background: 'var(--code-bg)', border: '1px solid var(--code-border)', borderRadius: 8, padding: '12px', overflowX: 'auto', maxHeight: 360, lineHeight: 1.5 }}>
            {pretty}
          </pre>
        )}
      </div>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function shellQuote(s: string): string {
  return /[\s"']/.test(s) ? `"${s.replace(/"/g, '\\"')}"` : s;
}
