'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { Wrench, Play, ChevronRight, AlertTriangle, CheckCircle, Terminal, ExternalLink } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
interface ToolMeta {
  tool: string;
  description: string;
  category: string | null;
  source: 'bundled' | 'plugin';
  actions: ActionMeta[];
}

type ShapeData =
  | { type: 'markdown'; content: string }
  | { type: 'data_table'; columns: string[]; rows: string[][] }
  | { type: 'metric'; label: string; value: string | number; unit?: string | null }
  | { type: 'link'; label: string; url: string }
  | { type: 'message'; text: string; level: 'info' | 'success' | 'warning' | 'error' }
  | { type: 'error'; reason: string; hint?: string | null }
  | { type: 'progress'; phase: string; message: string; level: string };

interface InvokeResult {
  ok: boolean;
  error?: string;
  confirmation_required?: boolean;
  notes?: string[];
  result?: unknown;
  shapes?: ShapeData[];
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
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set());
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
        // Auto-select first action of first plugin, falling back to first built-in.
        const first = data.find(t => t.source === 'plugin') ?? data[0];
        if (first?.actions[0]) {
          setSelTool(first.tool);
          setSelAction(first.actions[0].action);
          setExpandedTools(new Set([first.tool]));
        }
      })
      .catch(() => setLoadError(true));
  }, []);

  const pluginTools = useMemo(() => catalogue?.filter(t => t.source === 'plugin') ?? [], [catalogue]);
  const builtinTools = useMemo(() => catalogue?.filter(t => t.source === 'bundled') ?? [], [catalogue]);

  const activeAction = useMemo<ActionMeta | null>(() => {
    if (!catalogue || !selTool || !selAction) return null;
    const t = catalogue.find(x => x.tool === selTool);
    return t?.actions.find(a => a.action === selAction) ?? null;
  }, [catalogue, selTool, selAction]);

  const fields = useMemo<ResolvedField[]>(
    () => (activeAction ? resolveFields(activeAction.schema) : []),
    [activeAction],
  );

  // Reset form + telemetry + result when the selected action changes.
  const selKey = `${selTool}::${selAction}`;
  const [prevSelKey, setPrevSelKey] = useState<string | null>(null);
  if (selKey !== prevSelKey) {
    setPrevSelKey(selKey);
    setValues(initialValues(fields));
    setResult(null);
    setLogLines([]);
  }

  function selectAction(tool: string, action: string) {
    setSelTool(tool);
    setSelAction(action);
    // Keep the parent tool expanded.
    setExpandedTools(prev => new Set([...prev, tool]));
  }

  function toggleTool(toolName: string) {
    setExpandedTools(prev => {
      const next = new Set(prev);
      if (next.has(toolName)) next.delete(toolName);
      else next.add(toolName);
      return next;
    });
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
            setResult({
              ok: msg.ok === true,
              error: typeof msg.error === 'string' ? msg.error : undefined,
              confirmation_required: msg.confirmation_required === true,
              notes: Array.isArray(msg.notes) ? msg.notes as string[] : undefined,
              result: msg.result,
              shapes: Array.isArray(msg.shapes) ? msg.shapes as ShapeData[] : undefined,
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
          if (f.kind === 'string_array')
            return (values[f.name] as string[]).map(x => ` ${flag} ${shellQuote(x)}`).join('');
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
            <h1 style={{ fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 600, letterSpacing: '-0.3px', color: 'var(--fg1)', margin: 0 }}>
              Tools
            </h1>
          </div>
          <p style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)', margin: 0 }}>
            Run any registered tool action. Custom plugins from{' '}
            <code style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>~/.docent/plugins/</code>{' '}
            appear automatically — no extra code needed.
          </p>
        </div>

        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          {/* Left: collapsible catalogue */}
          <aside style={{
            width: 280, flexShrink: 0, borderRight: '1px solid var(--border)',
            overflowY: 'auto', padding: '14px 10px',
          }}>
            {loadError ? (
              <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: RED }}>
                Could not load tools. Is the server running?
              </div>
            ) : !catalogue ? (
              <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg4)' }}>Loading…</div>
            ) : (
              <>
                {/* Custom Plugins */}
                <SectionHeader label="Custom Plugins" count={pluginTools.length} />
                {pluginTools.length === 0
                  ? <EmptyPluginsState />
                  : pluginTools.map(tool => (
                    <ToolGroup
                      key={tool.tool}
                      tool={tool}
                      expanded={expandedTools.has(tool.tool)}
                      onToggle={() => toggleTool(tool.tool)}
                      selTool={selTool}
                      selAction={selAction}
                      onSelectAction={selectAction}
                    />
                  ))
                }

                {/* Built-in Tools */}
                <SectionHeader label="Built-in Tools" count={builtinTools.length} topMargin />
                {builtinTools.map(tool => (
                  <ToolGroup
                    key={tool.tool}
                    tool={tool}
                    expanded={expandedTools.has(tool.tool)}
                    onToggle={() => toggleTool(tool.tool)}
                    selTool={selTool}
                    selAction={selAction}
                    onSelectAction={selectAction}
                  />
                ))}
              </>
            )}
          </aside>

          {/* Right: form + telemetry + result */}
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

                <SchemaForm
                  fields={fields}
                  values={values}
                  onChange={(name, v) => setValues(prev => ({ ...prev, [name]: v }))}
                />

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
                  <button
                    onClick={() => run(false)}
                    disabled={running || !complete}
                    title={!complete ? 'Fill all required fields' : undefined}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 7,
                      padding: '9px 20px', borderRadius: 9999,
                      background: (running || !complete) ? 'var(--gray200)' : INDIGO,
                      color: '#fff', fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
                      border: 'none', cursor: (running || !complete) ? 'not-allowed' : 'pointer',
                    }}
                  >
                    <Play size={13} strokeWidth={2} />
                    {running ? 'Running…' : 'Run'}
                  </button>
                  {!complete && (
                    <span style={{ fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg4)' }}>
                      Required fields are marked with *
                    </span>
                  )}
                </div>

                <TelemetryStrip lines={logLines} running={running} />
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

// ── Catalogue components ──────────────────────────────────────────────────────

function SectionHeader({ label, count, topMargin }: { label: string; count: number; topMargin?: boolean }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 7,
      padding: '4px 6px 6px',
      marginTop: topMargin ? 16 : 0,
      fontFamily: 'var(--mono)', fontSize: 9.5, fontWeight: 600,
      color: 'var(--fg4)', letterSpacing: '0.6px', textTransform: 'uppercase',
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: BRAND, flexShrink: 0 }} />
      {label}
      <span style={{ marginLeft: 'auto', fontWeight: 400, letterSpacing: 0 }}>{count}</span>
    </div>
  );
}

function EmptyPluginsState() {
  return (
    <div style={{
      margin: '2px 4px 4px', padding: '12px 14px',
      border: '1px dashed var(--border-md)', borderRadius: 8,
    }}>
      <p style={{ fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg4)', margin: 0, lineHeight: 1.65 }}>
        Drop a{' '}
        <code style={{ fontFamily: 'var(--mono)', fontSize: 10.5 }}>.py</code>
        {' '}file into{' '}
        <code style={{ fontFamily: 'var(--mono)', fontSize: 10.5 }}>~/.docent/plugins/</code>
        {' '}to get started. See the{' '}
        <a href="/docs" style={{ color: BRAND_DEEP, textDecoration: 'none' }}>plugin guide</a>
        {' '}for the API.
      </p>
    </div>
  );
}

function ToolGroup({
  tool, expanded, onToggle, selTool, selAction, onSelectAction,
}: {
  tool: ToolMeta;
  expanded: boolean;
  onToggle: () => void;
  selTool: string | null;
  selAction: string | null;
  onSelectAction: (tool: string, action: string) => void;
}) {
  const hasActiveChild = tool.tool === selTool;
  return (
    <div style={{ marginBottom: 2 }}>
      {/* Tool header — click to collapse / expand */}
      <button
        onClick={onToggle}
        style={{
          display: 'flex', alignItems: 'center', gap: 6, width: '100%', textAlign: 'left',
          padding: '7px 10px', borderRadius: 7, border: 'none', cursor: 'pointer',
          background: hasActiveChild && !expanded ? BRAND + '15' : 'transparent',
        }}
      >
        <ChevronRight
          size={12} strokeWidth={2}
          style={{
            transform: expanded ? 'rotate(90deg)' : 'none',
            transition: 'transform 0.15s',
            flexShrink: 0,
            color: 'var(--fg4)',
          }}
        />
        <span style={{
          fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600,
          color: hasActiveChild ? BRAND_DEEP : 'var(--fg2)',
          flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {tool.tool}
        </span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--fg4)', flexShrink: 0 }}>
          {tool.actions.length}
        </span>
      </button>

      {/* Action list */}
      {expanded && (
        <div style={{ paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 1, paddingBottom: 4 }}>
          {tool.actions.map(a => {
            const isActive = tool.tool === selTool && a.action === selAction;
            return (
              <button
                key={a.action}
                onClick={() => onSelectAction(tool.tool, a.action)}
                title={a.description}
                style={{
                  display: 'flex', alignItems: 'center', gap: 7, width: '100%', textAlign: 'left',
                  padding: '5px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
                  background: isActive ? BRAND + '1f' : 'transparent',
                  color: isActive ? BRAND_DEEP : 'var(--fg2)',
                  fontFamily: 'var(--mono)', fontSize: 11.5, fontWeight: isActive ? 600 : 400,
                }}
              >
                <span style={{
                  width: 4, height: 4, borderRadius: '50%',
                  background: isActive ? BRAND_DEEP : 'var(--fg4)', flexShrink: 0,
                }} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {a.action}
                </span>
              </button>
            );
          })}
        </div>
      )}
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
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: running ? BRAND : 'var(--fg4)', flexShrink: 0 }} />
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
            <span style={{ color: lineColor(line.level), flexShrink: 0 }}>[{line.phase}]</span>
            <span style={{ color: 'var(--fg2)', wordBreak: 'break-word' }}>{line.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Result panel ─────────────────────────────────────────────────────────────

function ResultPanel({ result, onConfirm, running }: { result: InvokeResult; onConfirm: () => void; running: boolean }) {
  const [showRaw, setShowRaw] = useState(false);
  const confirmation = result.confirmation_required;
  const ok = result.ok && !confirmation;
  const notes = confirmation
    ? (result.notes ?? (isRecord(result.result) ? result.result.notes as string[] | undefined : undefined))
    : undefined;
  const pretty = (() => {
    try { return JSON.stringify(result.result, null, 2); } catch { return String(result.result); }
  })();
  const hasShapes = ok && Array.isArray(result.shapes) && result.shapes.length > 0;

  const tone = confirmation ? '#C97B00' : ok ? BRAND_DEEP : RED;
  const bg = confirmation ? 'rgba(201,123,0,0.07)' : ok ? 'rgba(24,226,153,0.06)' : 'rgba(212,86,86,0.05)';

  return (
    <div style={{ marginTop: 24, border: `1px solid ${tone}40`, borderRadius: 10, overflow: 'hidden', background: bg }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderBottom: `1px solid ${tone}30` }}>
        {ok
          ? <CheckCircle size={14} strokeWidth={2} color={tone} />
          : <AlertTriangle size={14} strokeWidth={2} color={tone} />}
        <span style={{ fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600, color: tone }}>
          {confirmation ? 'Confirmation required' : ok ? 'Success' : 'Failed'}
        </span>
        {hasShapes && (
          <button
            onClick={() => setShowRaw(r => !r)}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--fg4)', padding: '2px 6px' }}
          >
            {showRaw ? 'Hide raw' : 'View raw'}
          </button>
        )}
      </div>

      <div style={{ padding: '14px' }}>
        {result.error && (
          <p style={{ margin: '0 0 10px', fontFamily: 'var(--sans)', fontSize: 12.5, color: RED, lineHeight: 1.5 }}>
            {result.error}
          </p>
        )}
        {notes && notes.length > 0 && (
          <ul style={{ margin: '0 0 12px', paddingLeft: 18 }}>
            {notes.map((n, i) => (
              <li key={i} style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.6 }}>{n}</li>
            ))}
          </ul>
        )}
        {confirmation && (
          <button
            onClick={onConfirm}
            disabled={running}
            style={{ marginBottom: 14, padding: '7px 16px', borderRadius: 8, border: 'none', background: '#C97B00', color: '#fff', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600, cursor: running ? 'wait' : 'pointer' }}
          >
            {running ? 'Running…' : 'Confirm and run'}
          </button>
        )}
        {hasShapes && !showRaw
          ? <ShapesRenderer shapes={result.shapes!} />
          : result.result != null && (
            <pre style={{ margin: 0, fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--fg2)', background: 'var(--code-bg)', border: '1px solid var(--code-border)', borderRadius: 8, padding: '12px', overflowX: 'auto', maxHeight: 360, lineHeight: 1.5 }}>
              {pretty}
            </pre>
          )}
      </div>
    </div>
  );
}

// ── Artifact viewer — shape renderers ────────────────────────────────────────

function ShapesRenderer({ shapes }: { shapes: ShapeData[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {shapes.map((shape, i) => <ShapeItem key={i} shape={shape} />)}
    </div>
  );
}

function ShapeItem({ shape }: { shape: ShapeData }) {
  switch (shape.type) {
    case 'markdown':   return <MarkdownShapeView shape={shape} />;
    case 'data_table': return <DataTableShapeView shape={shape} />;
    case 'metric':     return <MetricShapeView shape={shape} />;
    case 'link':       return <LinkShapeView shape={shape} />;
    case 'message':    return <MessageShapeView shape={shape} />;
    case 'error':      return <ErrorShapeView shape={shape} />;
    default:           return null;
  }
}

function MarkdownShapeView({ shape }: { shape: Extract<ShapeData, { type: 'markdown' }> }) {
  return (
    <div style={{ fontFamily: 'var(--sans)', fontSize: 13, lineHeight: 1.65, color: 'var(--fg1)' }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p style={{ margin: '0 0 8px', color: 'var(--fg1)', lineHeight: 1.65 }}>{children}</p>,
          pre: ({ children }) => <pre style={{ fontFamily: 'var(--mono)', fontSize: 12, background: 'var(--code-bg)', border: '1px solid var(--code-border)', borderRadius: 8, padding: '10px 12px', overflowX: 'auto', lineHeight: 1.5, margin: '8px 0' }}>{children}</pre>,
          code: ({ children, className }) => (
            className
              ? <code style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{children}</code>
              : <code style={{ fontFamily: 'var(--mono)', fontSize: 12, background: 'var(--code-bg)', padding: '1px 5px', borderRadius: 4, color: 'var(--fg2)' }}>{children}</code>
          ),
          ul: ({ children }) => <ul style={{ margin: '0 0 8px', paddingLeft: 20 }}>{children}</ul>,
          ol: ({ children }) => <ol style={{ margin: '0 0 8px', paddingLeft: 20 }}>{children}</ol>,
          li: ({ children }) => <li style={{ marginBottom: 3, color: 'var(--fg2)' }}>{children}</li>,
          h1: ({ children }) => <h1 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 8px', color: 'var(--fg1)' }}>{children}</h1>,
          h2: ({ children }) => <h2 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 8px', color: 'var(--fg1)' }}>{children}</h2>,
          h3: ({ children }) => <h3 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 6px', color: 'var(--fg2)' }}>{children}</h3>,
          a: ({ href, children }) => <a href={href ?? '#'} target="_blank" rel="noreferrer" style={{ color: BRAND_DEEP, textDecoration: 'none' }}>{children}</a>,
          hr: () => <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '10px 0' }} />,
          strong: ({ children }) => <strong style={{ fontWeight: 700 }}>{children}</strong>,
          blockquote: ({ children }) => <blockquote style={{ borderLeft: '3px solid var(--border)', margin: '8px 0', paddingLeft: 12, color: 'var(--fg3)', fontStyle: 'italic' }}>{children}</blockquote>,
        }}
      >
        {shape.content}
      </ReactMarkdown>
    </div>
  );
}

function DataTableShapeView({ shape }: { shape: Extract<ShapeData, { type: 'data_table' }> }) {
  return (
    <div style={{ overflowX: 'auto', borderRadius: 8, border: '1px solid var(--border)' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--sans)', fontSize: 12.5 }}>
        <thead>
          <tr style={{ background: 'var(--code-bg)' }}>
            {shape.columns.map((col, i) => (
              <th key={i} style={{ padding: '7px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)', color: 'var(--fg3)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.4px', whiteSpace: 'nowrap' }}>
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shape.rows.map((row, ri) => (
            <tr key={ri} style={{ background: ri % 2 === 1 ? 'var(--code-bg)' : 'transparent' }}>
              {row.map((cell, ci) => (
                <td key={ci} style={{ padding: '7px 12px', borderBottom: ri < shape.rows.length - 1 ? '1px solid var(--border)' : 'none', color: 'var(--fg2)', lineHeight: 1.4 }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricShapeView({ shape }: { shape: Extract<ShapeData, { type: 'metric' }> }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)', flexShrink: 0, width: 148, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {shape.label}
      </span>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--fg1)', fontWeight: 600, flex: 1, wordBreak: 'break-all' }}>
        {String(shape.value)}
      </span>
      {shape.unit && (
        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)', flexShrink: 0 }}>
          {shape.unit}
        </span>
      )}
    </div>
  );
}

function LinkShapeView({ shape }: { shape: Extract<ShapeData, { type: 'link' }> }) {
  return (
    <a
      href={shape.url}
      target="_blank"
      rel="noreferrer"
      style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: BRAND_DEEP, fontFamily: 'var(--sans)', fontSize: 13, textDecoration: 'none', fontWeight: 500 }}
    >
      {shape.label}
      <ExternalLink size={12} strokeWidth={1.5} />
    </a>
  );
}

const MSG_COLOR: Record<string, string> = {
  info: 'var(--fg2)',
  success: BRAND_DEEP,
  warning: '#C97B00',
  error: RED,
};
const MSG_BG: Record<string, string> = {
  info: 'var(--code-bg)',
  success: 'rgba(24,226,153,0.09)',
  warning: 'rgba(201,123,0,0.09)',
  error: 'rgba(212,86,86,0.07)',
};
const MSG_BORDER: Record<string, string> = {
  info: 'var(--code-border)',
  success: `${BRAND}40`,
  warning: '#C97B0040',
  error: `${RED}30`,
};

function MessageShapeView({ shape }: { shape: Extract<ShapeData, { type: 'message' }> }) {
  return (
    <div style={{ padding: '8px 12px', borderRadius: 7, background: MSG_BG[shape.level] ?? MSG_BG.info, border: `1px solid ${MSG_BORDER[shape.level] ?? MSG_BORDER.info}`, fontFamily: 'var(--sans)', fontSize: 13, color: MSG_COLOR[shape.level] ?? MSG_COLOR.info, lineHeight: 1.5 }}>
      {shape.text}
    </div>
  );
}

function ErrorShapeView({ shape }: { shape: Extract<ShapeData, { type: 'error' }> }) {
  return (
    <div style={{ padding: '10px 12px', borderRadius: 7, background: 'rgba(212,86,86,0.07)', border: `1px solid ${RED}30` }}>
      <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 13, color: RED, lineHeight: 1.5 }}>{shape.reason}</p>
      {shape.hint && <p style={{ margin: '6px 0 0', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.4 }}>{shape.hint}</p>}
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
