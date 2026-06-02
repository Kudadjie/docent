'use client';

import { useState, useRef, useEffect } from 'react';
import {
  Blocks, Wand2, RotateCcw, CheckCircle, FlaskConical,
  Download, AlertTriangle, ChevronDown, ChevronUp, Copy, Check,
  History, Trash, X, RefreshCw,
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';

// ── Types ─────────────────────────────────────────────────────────────────────

interface GenerateResult {
  ok: boolean;
  plugin_id?: string;
  code?: string;
  explanation?: string;
  actions?: string[];
  error?: string;
}
interface ValidateResult {
  ok: boolean;
  valid?: boolean;
  errors?: string[];
  warnings?: string[];
}
interface SandboxResult {
  ok: boolean;
  success?: boolean;
  output?: string;
  errors?: string[];
}
interface InstallResult {
  ok: boolean;
  path?: string;
  actions_registered?: string[];
  message?: string;
  error?: string;
}
interface ProgressStep {
  phase: string;
  message: string;
}

export interface HistoryEntry {
  id: string;
  spec: string;
  context: string;
  model: string;
  code: string;
  explanation: string;
  actions: string[];
  pluginId: string | null;
  status: 'success' | 'error';
  startedAt: number;
}

// ── Available models ──────────────────────────────────────────────────────────

const OC_MODELS = [
  { id: 'glm-5.1',          label: 'GLM-5.1 (default)' },
  { id: 'deepseek-v4-pro',  label: 'DeepSeek V4 Pro' },
  { id: 'minimax-m2.7',     label: 'MiniMax M2.7' },
  { id: 'qwen3.5-plus',     label: 'Qwen 3.5 Plus' },
];

const LS_KEY = 'pb-history';
const MAX_HISTORY = 20;

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(ts: number): string {
  const secs = Math.floor((Date.now() - ts) / 1000);
  if (secs < 60) return 'just now';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function specSnippet(spec: string, maxLen = 48): string {
  const s = spec.trim().replace(/\s+/g, ' ');
  return s.length > maxLen ? s.slice(0, maxLen) + '…' : s;
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function invokeAction(action: string, inputs: Record<string, unknown>) {
  const res = await fetch('/api/tools/invoke', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool: 'plugin_builder', action, inputs }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  const data = await res.json();
  return data.result ?? data;
}

async function streamAction(
  action: string,
  inputs: Record<string, unknown>,
  onStep: (step: ProgressStep) => void,
  signal: AbortSignal,
): Promise<Record<string, unknown>> {
  const resp = await fetch('/api/tools/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool: 'plugin_builder', action, inputs }),
    signal,
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);

  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
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
        onStep({ phase: String(msg.phase ?? ''), message: String(msg.message ?? msg.phase ?? '') });
      } else {
        return msg as Record<string, unknown>;
      }
    }
  }
  throw new Error('Stream ended without a result event.');
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionLabel({ icon: Icon, label }: { icon: React.ElementType; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 14 }}>
      <Icon size={13} style={{ color: 'var(--brand)' }} />
      <span style={{
        fontFamily: 'var(--sans)', fontSize: 10, fontWeight: 700,
        letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--fg4)',
      }}>
        {label}
      </span>
    </div>
  );
}

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border-md)',
      borderRadius: 12,
      padding: '20px 22px',
      marginBottom: 14,
      ...style,
    }}>
      {children}
    </div>
  );
}

function PrimaryBtn({
  onClick, disabled, loading, children,
}: {
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '7px 16px', borderRadius: 8,
        fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
        background: disabled || loading ? 'var(--gray200)' : 'var(--brand)',
        color: disabled || loading ? 'var(--fg4)' : '#000',
        border: 'none', cursor: disabled || loading ? 'not-allowed' : 'pointer',
        transition: 'opacity 0.15s',
        opacity: disabled && !loading ? 0.5 : 1,
      }}
    >
      {loading && (
        <span style={{
          display: 'inline-block', width: 12, height: 12,
          border: '1.5px solid rgba(0,0,0,0.2)',
          borderTopColor: '#000',
          borderRadius: '50%',
          animation: 'spin 0.7s linear infinite',
        }} />
      )}
      {children}
    </button>
  );
}

function GhostBtn({
  onClick, active, children,
}: {
  onClick: () => void;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        padding: '5px 11px', borderRadius: 7,
        fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
        background: active ? 'var(--gray100)' : 'transparent',
        color: active ? 'var(--fg1)' : 'var(--fg3)',
        border: '1px solid var(--border-md)',
        cursor: 'pointer',
        transition: 'background 0.12s, color 0.12s',
      }}
    >
      {children}
    </button>
  );
}

function Textarea({
  value, onChange, placeholder, rows = 4,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <textarea
      rows={rows}
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: '100%', boxSizing: 'border-box',
        background: 'var(--bg-subtle)', border: '1px solid var(--border-md)',
        borderRadius: 8, padding: '10px 12px',
        fontFamily: 'var(--sans)', fontSize: 13,
        color: 'var(--fg1)', resize: 'vertical',
        outline: 'none', marginBottom: 10,
      }}
    />
  );
}

function TextInput({
  value, onChange, placeholder, mono,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  mono?: boolean;
}) {
  return (
    <input
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: '100%', boxSizing: 'border-box',
        background: 'var(--bg-subtle)', border: '1px solid var(--border-md)',
        borderRadius: 8, padding: '8px 11px',
        fontFamily: mono ? 'var(--mono)' : 'var(--sans)', fontSize: 13,
        color: 'var(--fg1)',
        outline: 'none',
      }}
    />
  );
}

function ModelSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label style={{ display: 'block', fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg3)', marginBottom: 5 }}>
        LLM model
      </label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          width: '100%', boxSizing: 'border-box',
          background: 'var(--bg-subtle)', border: '1px solid var(--border-md)',
          borderRadius: 8, padding: '8px 11px',
          fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg1)',
          outline: 'none', cursor: 'pointer', appearance: 'none',
        }}
      >
        {OC_MODELS.map(m => (
          <option key={m.id} value={m.id}>{m.label}</option>
        ))}
      </select>
    </div>
  );
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      title="Copy"
      style={{
        position: 'absolute', top: 10, right: 10,
        background: 'var(--gray100)', border: '1px solid var(--border-md)',
        borderRadius: 6, padding: '3px 7px',
        color: 'var(--fg3)', cursor: 'pointer', fontSize: 11,
        display: 'flex', alignItems: 'center', gap: 4,
      }}
    >
      {copied ? <Check size={11} /> : <Copy size={11} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

function Alert({ type, children }: { type: 'error' | 'warn' | 'success'; children: React.ReactNode }) {
  const styles = {
    error: { bg: 'var(--red-bg)', color: 'var(--red-text)' },
    warn: { bg: 'var(--amber-bg)', color: 'var(--amber-text)' },
    success: { bg: 'rgba(24,226,153,0.10)', color: 'var(--brand)' },
  }[type];
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 8,
      background: styles.bg, color: styles.color,
      borderRadius: 8, padding: '8px 12px',
      fontSize: 12, fontFamily: 'var(--sans)',
      marginTop: 8,
    }}>
      {type === 'success' ? <CheckCircle size={13} style={{ marginTop: 1, flexShrink: 0 }} /> : <AlertTriangle size={13} style={{ marginTop: 1, flexShrink: 0 }} />}
      <span>{children}</span>
    </div>
  );
}

function ProgressSteps({ steps, done }: { steps: ProgressStep[]; done: boolean }) {
  if (steps.length === 0) return null;
  return (
    <div style={{
      marginTop: 14, padding: '12px 14px',
      background: 'var(--bg-subtle)', borderRadius: 8,
      border: '1px solid var(--border-md)',
    }}>
      {steps.map((step, i) => {
        const isLast = i === steps.length - 1;
        const isDone = !isLast || done;
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0' }}>
            {isDone ? (
              <CheckCircle size={13} style={{ color: 'var(--brand)', flexShrink: 0 }} />
            ) : (
              <span style={{
                display: 'inline-block', width: 13, height: 13, flexShrink: 0,
                border: '1.5px solid var(--fg4)', borderTopColor: 'var(--brand)',
                borderRadius: '50%', animation: 'spin 0.7s linear infinite',
              }} />
            )}
            <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: isDone ? 'var(--fg3)' : 'var(--fg1)' }}>
              {step.message}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', marginLeft: 'auto' }}>
              {step.phase}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── History drawer ─────────────────────────────────────────────────────────────

function PBHistoryDrawer({
  entries, activeId, onSelect, onDelete, onClear, onClose,
}: {
  entries: HistoryEntry[];
  activeId: string | null;
  onSelect: (e: HistoryEntry) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
  onClose: () => void;
}) {
  return (
    <aside style={{
      width: 300, flexShrink: 0, height: '100%',
      borderLeft: '1px solid var(--border)',
      background: 'var(--bg)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 18px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <History size={14} strokeWidth={1.5} style={{ color: 'var(--fg3)' }} />
        <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)' }}>
          Plugin history
        </span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.5px' }}>
          {entries.length}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
          {entries.length > 0 && (
            <button onClick={onClear} title="Clear all" style={{
              width: 24, height: 24, border: 'none', background: 'transparent',
              color: 'var(--fg4)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 5,
            }}>
              <Trash size={12} strokeWidth={1.5} />
            </button>
          )}
          <button onClick={onClose} title="Close" style={{
            width: 24, height: 24, border: 'none', background: 'transparent',
            color: 'var(--fg4)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 5,
          }}>
            <X size={12} strokeWidth={2} />
          </button>
        </div>
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 10px' }}>
        {entries.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', height: '100%', gap: 8,
            color: 'var(--fg4)', padding: '24px 14px', textAlign: 'center',
          }}>
            <History size={14} strokeWidth={1.5} style={{ opacity: 0.4 }} />
            <span style={{ fontFamily: 'var(--sans)', fontSize: 12 }}>No history yet</span>
            <span style={{ fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg4)', lineHeight: 1.5 }}>
              Generated plugins will appear here.
            </span>
          </div>
        ) : entries.map(e => {
          const active = e.id === activeId;
          const dotColor = e.status === 'error' ? '#E53535' : '#18E299';
          return (
            <div key={e.id} style={{ position: 'relative', marginBottom: 4 }} className="pb-history-item">
              <button
                onClick={() => onSelect(e)}
                style={{
                  width: '100%', textAlign: 'left',
                  padding: '10px 12px', paddingRight: 32,
                  borderRadius: 8,
                  border: `1px solid ${active ? '#18E29966' : 'transparent'}`,
                  background: active ? '#18E29910' : 'transparent',
                  cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 5,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: dotColor, flexShrink: 0 }} />
                  <span style={{
                    fontFamily: 'var(--mono)', fontSize: 10,
                    background: 'var(--gray100)', color: 'var(--fg3)',
                    borderRadius: 4, padding: '1px 5px', flexShrink: 0,
                  }}>
                    {e.model}
                  </span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--fg4)', marginLeft: 'auto', flexShrink: 0 }}>
                    {timeAgo(e.startedAt)}
                  </span>
                </div>
                <div style={{
                  fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg2)',
                  lineHeight: 1.4, paddingLeft: 13,
                  display: '-webkit-box', WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical', overflow: 'hidden',
                }}>
                  {e.spec}
                </div>
                {e.actions.length > 0 && (
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', paddingLeft: 13 }}>
                    {e.actions.map(a => (
                      <span key={a} style={{
                        fontFamily: 'var(--mono)', fontSize: 9.5,
                        background: 'var(--gray100)', color: 'var(--fg4)',
                        borderRadius: 3, padding: '1px 4px',
                      }}>@{a}</span>
                    ))}
                  </div>
                )}
              </button>
              <button
                onClick={ev => { ev.stopPropagation(); onDelete(e.id); }}
                title="Remove"
                style={{
                  position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                  width: 20, height: 20, border: 'none', background: 'transparent',
                  color: 'var(--fg4)', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  borderRadius: 4, opacity: 0, transition: 'opacity 0.1s',
                }}
                className="pb-history-delete"
              >
                <Trash size={11} strokeWidth={1.5} />
              </button>
            </div>
          );
        })}
      </div>
    </aside>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PluginBuilderPage() {
  const { dark, toggleDark } = useDarkMode();

  // History
  const [history, setHistory] = useState<HistoryEntry[]>(() => {
    try {
      const s = localStorage.getItem(LS_KEY);
      return s ? (JSON.parse(s) as HistoryEntry[]) : [];
    } catch { return []; }
  });
  const [historyOpen, setHistoryOpen] = useState(false);
  const [activeHistoryId, setActiveHistoryId] = useState<string | null>(null);
  const [duplicateEntry, setDuplicateEntry] = useState<HistoryEntry | null>(null);

  useEffect(() => {
    try { localStorage.setItem(LS_KEY, JSON.stringify(history)); } catch {}
  }, [history]);

  // Generate
  const [spec, setSpec] = useState('');
  const [context, setContext] = useState('');
  const [selectedModel, setSelectedModel] = useState('glm-5.1');
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);
  const [genDone, setGenDone] = useState(false);
  const genAbortRef = useRef<AbortController | null>(null);

  // Code
  const [code, setCode] = useState('');
  const [pluginId, setPluginId] = useState<string | null>(null);
  const [detectedActions, setDetectedActions] = useState<string[]>([]);
  const [explanation, setExplanation] = useState('');

  // Iterate
  const [showIterate, setShowIterate] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [iterating, setIterating] = useState(false);
  const [iterSteps, setIterSteps] = useState<ProgressStep[]>([]);
  const [iterDone, setIterDone] = useState(false);
  const iterAbortRef = useRef<AbortController | null>(null);

  // Validate
  const [validating, setValidating] = useState(false);
  const [validateResult, setValidateResult] = useState<ValidateResult | null>(null);

  // Sandbox
  const [showSandbox, setShowSandbox] = useState(false);
  const [sandboxAction, setSandboxAction] = useState('');
  const [sandboxInputs, setSandboxInputs] = useState('{}');
  const [sandboxing, setSandboxing] = useState(false);
  const [sandboxResult, setSandboxResult] = useState<SandboxResult | null>(null);

  // Install
  const [showInstall, setShowInstall] = useState(false);
  const [pluginName, setPluginName] = useState('');
  const [forceInstall, setForceInstall] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [installResult, setInstallResult] = useState<InstallResult | null>(null);

  const hasCode = code.length > 0;

  // ── History helpers ───────────────────────────────────────────────────────

  function saveToHistory(entry: HistoryEntry) {
    setHistory(prev => [entry, ...prev.filter(e => e.id !== entry.id)].slice(0, MAX_HISTORY));
    setActiveHistoryId(entry.id);
  }

  function loadHistoryEntry(e: HistoryEntry) {
    setSpec(e.spec);
    setContext(e.context);
    setSelectedModel(e.model);
    setCode(e.code);
    setPluginId(e.pluginId);
    setDetectedActions(e.actions);
    setExplanation(e.explanation);
    if (e.actions.length) setSandboxAction(e.actions[0]);
    const slug = e.spec.toLowerCase().replace(/[^a-z0-9\s]/g, '').trim()
      .split(/\s+/).slice(0, 3).join('_');
    setPluginName(slug || 'my_plugin');
    setActiveHistoryId(e.id);
    setDuplicateEntry(null);
    setGenError(null);
    setValidateResult(null);
    setSandboxResult(null);
    setInstallResult(null);
    setProgressSteps([]);
  }

  // ── Handlers ──────────────────────────────────────────────────────────────

  async function handleGenerate(force = false) {
    if (!spec.trim()) return;

    // Duplicate check
    if (!force) {
      const dup = history.find(
        e => e.spec === spec.trim() && e.context === (context.trim() || '') && e.status === 'success',
      );
      if (dup) {
        setDuplicateEntry(dup);
        return;
      }
    }
    setDuplicateEntry(null);

    if (genAbortRef.current) genAbortRef.current.abort();
    const abort = new AbortController();
    genAbortRef.current = abort;

    setGenerating(true);
    setGenError(null);
    setProgressSteps([]);
    setGenDone(false);
    setValidateResult(null);
    setSandboxResult(null);
    setInstallResult(null);

    const startedAt = Date.now();

    try {
      const msg = await streamAction(
        'generate',
        { spec: spec.trim(), context: context.trim() || null, model: selectedModel },
        step => setProgressSteps(prev => [...prev, step]),
        abort.signal,
      );
      setGenDone(true);
      const result = (msg.result ?? msg) as GenerateResult;

      if (result.ok && result.code) {
        setCode(result.code);
        setPluginId(result.plugin_id ?? null);
        setDetectedActions(result.actions ?? []);
        setExplanation(result.explanation ?? '');
        if (result.actions?.length) setSandboxAction(result.actions[0]);
        const slug = spec.trim().toLowerCase().replace(/[^a-z0-9\s]/g, '').trim()
          .split(/\s+/).slice(0, 3).join('_');
        setPluginName(slug || 'my_plugin');

        saveToHistory({
          id: result.plugin_id ?? crypto.randomUUID(),
          spec: spec.trim(),
          context: context.trim() || '',
          model: selectedModel,
          code: result.code,
          explanation: result.explanation ?? '',
          actions: result.actions ?? [],
          pluginId: result.plugin_id ?? null,
          status: 'success',
          startedAt,
        });
      } else {
        const errMsg = result.error ?? 'Generation failed.';
        setGenError(errMsg);
        saveToHistory({
          id: crypto.randomUUID(),
          spec: spec.trim(),
          context: context.trim() || '',
          model: selectedModel,
          code: '',
          explanation: '',
          actions: [],
          pluginId: null,
          status: 'error',
          startedAt,
        });
      }
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setGenError(String(e));
      setGenDone(true);
    } finally {
      setGenerating(false);
    }
  }

  async function handleIterate() {
    if (!feedback.trim() || !code) return;
    if (iterAbortRef.current) iterAbortRef.current.abort();
    const abort = new AbortController();
    iterAbortRef.current = abort;

    setIterating(true);
    setValidateResult(null);
    setSandboxResult(null);
    setIterSteps([]);
    setIterDone(false);

    try {
      const msg = await streamAction(
        'iterate',
        { plugin_id: pluginId ?? 'draft', code, feedback: feedback.trim(), model: selectedModel },
        step => setIterSteps(prev => [...prev, step]),
        abort.signal,
      );
      setIterDone(true);
      const result = (msg.result ?? msg) as GenerateResult;
      if (result.ok && result.code) {
        const newCode = result.code;
        setCode(newCode);
        setPluginId(result.plugin_id ?? pluginId);
        setFeedback('');
        // Update the active history entry's code
        if (activeHistoryId) {
          setHistory(prev => prev.map(e =>
            e.id === activeHistoryId ? { ...e, code: newCode } : e,
          ));
        }
      } else {
        setGenError(result.error ?? 'Iterate failed.');
      }
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setGenError(String(e));
      setIterDone(true);
    } finally {
      setIterating(false);
    }
  }

  async function handleValidate() {
    if (!code) return;
    setValidating(true); setValidateResult(null);
    try { setValidateResult(await invokeAction('validate', { code })); }
    catch (e) { setValidateResult({ ok: false, errors: [String(e)] }); }
    finally { setValidating(false); }
  }

  async function handleSandbox() {
    if (!code || !sandboxAction.trim()) return;
    setSandboxing(true); setSandboxResult(null);
    try {
      setSandboxResult(await invokeAction('sandbox-test', {
        code, action: sandboxAction.trim(), inputs: sandboxInputs.trim() || '{}',
      }));
    } catch (e) { setSandboxResult({ ok: false, errors: [String(e)] }); }
    finally { setSandboxing(false); }
  }

  async function handleInstall() {
    if (!code || !pluginName.trim()) return;
    setInstalling(true); setInstallResult(null);
    try {
      setInstallResult(await invokeAction('install', {
        code, name: pluginName.trim(), force: forceInstall,
      }));
    } catch (e) { setInstallResult({ ok: false, error: String(e) }); }
    finally { setInstalling(false); }
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes slideInRight { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        .pb-ghostbtn:hover { background: var(--gray100) !important; color: var(--fg1) !important; }
        .pb-history-item:hover .pb-history-delete { opacity: 1 !important; }
        select option { background: var(--bg-card); color: var(--fg1); }
      `}</style>

      <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
        <Sidebar active="plugin-builder" queueCount={0} dark={dark} />

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
          <StatusBanner dark={dark} onToggleDark={toggleDark} dotState="idle" />

          <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>

            {/* ── Main content ── */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px', maxWidth: 720, width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>

              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
                <div style={{
                  padding: 10, borderRadius: 10,
                  background: 'rgba(24,226,153,0.12)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Blocks size={20} style={{ color: 'var(--brand)' }} />
                </div>
                <div style={{ flex: 1 }}>
                  <h1 style={{ fontFamily: 'var(--sans)', fontSize: 20, fontWeight: 600, color: 'var(--fg1)', margin: 0, letterSpacing: '-0.3px' }}>
                    Plugin Builder
                  </h1>
                  <p style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)', margin: '2px 0 0' }}>
                    Describe a workflow → Docent LLM builds a reusable plugin
                  </p>
                </div>
                {/* History toggle */}
                <button
                  onClick={() => setHistoryOpen(o => !o)}
                  title="Plugin history"
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '6px 12px', borderRadius: 8,
                    fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
                    background: historyOpen ? 'var(--gray100)' : 'transparent',
                    color: historyOpen ? 'var(--fg1)' : 'var(--fg3)',
                    border: '1px solid var(--border-md)',
                    cursor: 'pointer', transition: 'background 0.12s',
                  }}
                >
                  <History size={13} />
                  History
                  {history.length > 0 && (
                    <span style={{
                      fontFamily: 'var(--mono)', fontSize: 10,
                      background: 'var(--gray100)', color: 'var(--fg4)',
                      borderRadius: 4, padding: '0 4px',
                    }}>{history.length}</span>
                  )}
                </button>
              </div>

              {/* ── Generate ─────────────────────────────────────────── */}
              <Card>
                <SectionLabel icon={Wand2} label="Generate" />
                <Textarea
                  value={spec}
                  onChange={v => { setSpec(v); setDuplicateEntry(null); }}
                  rows={4}
                  placeholder={"Describe the plugin you want to build…\ne.g. 'A tool that scans my reading queue for papers with upcoming deadlines and exports a CSV'"}
                />
                <Textarea
                  value={context}
                  onChange={v => { setContext(v); setDuplicateEntry(null); }}
                  rows={2}
                  placeholder="Optional: additional context about your workflow or data sources"
                />
                <div style={{ marginBottom: 12 }}>
                  <ModelSelect value={selectedModel} onChange={setSelectedModel} />
                </div>
                <PrimaryBtn onClick={() => handleGenerate(false)} disabled={!spec.trim()} loading={generating}>
                  {!generating && <Wand2 size={13} />}
                  {generating ? 'Generating…' : 'Generate Plugin'}
                </PrimaryBtn>

                {/* Duplicate warning */}
                {duplicateEntry && !generating && (
                  <div style={{
                    marginTop: 12, padding: '10px 14px',
                    background: 'var(--amber-bg)', borderRadius: 8,
                    border: '1px solid var(--border-md)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 10 }}>
                      <RefreshCw size={13} style={{ color: 'var(--amber-text)', marginTop: 1, flexShrink: 0 }} />
                      <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--amber-text)' }}>
                        Already generated {timeAgo(duplicateEntry.startedAt)} with {duplicateEntry.model} — {specSnippet(duplicateEntry.spec)}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        onClick={() => loadHistoryEntry(duplicateEntry)}
                        style={{
                          padding: '5px 12px', borderRadius: 7,
                          fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
                          background: 'var(--brand)', color: '#000',
                          border: 'none', cursor: 'pointer',
                        }}
                      >
                        Restore previous
                      </button>
                      <button
                        onClick={() => handleGenerate(true)}
                        style={{
                          padding: '5px 12px', borderRadius: 7,
                          fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
                          background: 'transparent', color: 'var(--fg2)',
                          border: '1px solid var(--border-md)', cursor: 'pointer',
                        }}
                      >
                        Generate anyway
                      </button>
                    </div>
                  </div>
                )}

                <ProgressSteps steps={progressSteps} done={genDone} />
                {genError && <Alert type="error">{genError}</Alert>}
              </Card>

              {/* ── Code panel ───────────────────────────────────────── */}
              {hasCode && (
                <Card>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                    <SectionLabel icon={Blocks} label="Generated Code" />
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {detectedActions.map(a => (
                        <span key={a} style={{
                          fontFamily: 'var(--mono)', fontSize: 11,
                          background: 'var(--gray100)', color: 'var(--fg3)',
                          borderRadius: 5, padding: '2px 7px',
                        }}>@{a}</span>
                      ))}
                    </div>
                  </div>

                  {explanation && (
                    <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', marginBottom: 12 }}>
                      {explanation}
                    </p>
                  )}

                  <div style={{ position: 'relative' }}>
                    <pre style={{
                      background: 'var(--code-bg)', border: '1px solid var(--code-border)',
                      borderRadius: 8, padding: '14px 16px', overflowX: 'auto',
                      fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--fg2)',
                      maxHeight: 380, overflowY: 'auto', margin: 0, lineHeight: 1.55,
                    }}>
                      {code}
                    </pre>
                    <CopyBtn text={code} />
                  </div>

                  {/* Action row */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16 }}>
                    <GhostBtn onClick={() => setShowIterate(v => !v)} active={showIterate}>
                      <RotateCcw size={12} />
                      Iterate
                      {showIterate ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                    </GhostBtn>
                    <GhostBtn onClick={handleValidate} active={false}>
                      {validating
                        ? <span style={{ display: 'inline-block', width: 11, height: 11, border: '1.5px solid var(--fg4)', borderTopColor: 'var(--brand)', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                        : <CheckCircle size={12} />}
                      {validating ? 'Validating…' : 'Validate'}
                    </GhostBtn>
                    <GhostBtn onClick={() => setShowSandbox(v => !v)} active={showSandbox}>
                      <FlaskConical size={12} />
                      Sandbox Test
                      {showSandbox ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                    </GhostBtn>
                    <GhostBtn onClick={() => setShowInstall(v => !v)} active={showInstall}>
                      <Download size={12} />
                      Install
                      {showInstall ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                    </GhostBtn>
                  </div>

                  {validateResult && (
                    <div style={{ marginTop: 10 }}>
                      {validateResult.valid
                        ? <Alert type="success">Code is valid — no blocking errors.</Alert>
                        : validateResult.errors?.map((e, i) => <Alert key={i} type="error">{e}</Alert>)
                      }
                      {validateResult.warnings?.map((w, i) => <Alert key={i} type="warn">{w}</Alert>)}
                    </div>
                  )}
                </Card>
              )}

              {/* ── Iterate ──────────────────────────────────────────── */}
              {hasCode && showIterate && (
                <Card>
                  <SectionLabel icon={RotateCcw} label="Iterate" />
                  <Textarea
                    value={feedback}
                    onChange={setFeedback}
                    rows={3}
                    placeholder="What would you like to change? e.g. 'Add a --dry-run flag' or 'Return results sorted by date'"
                  />
                  <PrimaryBtn onClick={handleIterate} disabled={!feedback.trim()} loading={iterating}>
                    {!iterating && <RotateCcw size={13} />}
                    {iterating ? 'Revising…' : 'Revise Plugin'}
                  </PrimaryBtn>
                  <ProgressSteps steps={iterSteps} done={iterDone} />
                </Card>
              )}

              {/* ── Sandbox ──────────────────────────────────────────── */}
              {hasCode && showSandbox && (
                <Card>
                  <SectionLabel icon={FlaskConical} label="Sandbox Test" />
                  <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', marginBottom: 14 }}>
                    Runs in an isolated registry — no disk writes until you install.
                  </p>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                    <div>
                      <label style={{ display: 'block', fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg3)', marginBottom: 5 }}>Action name</label>
                      <TextInput value={sandboxAction} onChange={setSandboxAction} placeholder="e.g. scan" />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg3)', marginBottom: 5 }}>Inputs (JSON)</label>
                      <TextInput value={sandboxInputs} onChange={setSandboxInputs} placeholder='{"key": "value"}' mono />
                    </div>
                  </div>
                  <PrimaryBtn onClick={handleSandbox} disabled={!sandboxAction.trim()} loading={sandboxing}>
                    {!sandboxing && <FlaskConical size={13} />}
                    {sandboxing ? 'Testing…' : 'Run in Sandbox'}
                  </PrimaryBtn>

                  {sandboxResult && (
                    <div style={{ marginTop: 12 }}>
                      {sandboxResult.success
                        ? <>
                          <Alert type="success">Action ran successfully.</Alert>
                          {sandboxResult.output && (
                            <pre style={{
                              background: 'var(--code-bg)', border: '1px solid var(--code-border)',
                              borderRadius: 8, padding: '10px 14px', marginTop: 8,
                              fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--fg2)',
                              overflowX: 'auto', maxHeight: 240, overflowY: 'auto', margin: '8px 0 0',
                            }}>
                              {sandboxResult.output}
                            </pre>
                          )}
                        </>
                        : sandboxResult.errors?.map((e, i) => <Alert key={i} type="error">{e}</Alert>)
                      }
                    </div>
                  )}
                </Card>
              )}

              {/* ── Install ──────────────────────────────────────────── */}
              {hasCode && showInstall && (
                <Card>
                  <SectionLabel icon={Download} label="Install" />
                  <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', marginBottom: 14 }}>
                    Writes to{' '}
                    <code style={{ fontFamily: 'var(--mono)', fontSize: 11, background: 'var(--gray100)', padding: '1px 5px', borderRadius: 4 }}>
                      ~/.docent/plugins/{'{'}{pluginName || 'name'}{'}'}.py
                    </code>
                    . Restart <code style={{ fontFamily: 'var(--mono)', fontSize: 11, background: 'var(--gray100)', padding: '1px 5px', borderRadius: 4 }}>docent</code> after installing.
                  </p>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', marginBottom: 14 }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ display: 'block', fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg3)', marginBottom: 5 }}>
                        Plugin name (snake_case)
                      </label>
                      <TextInput value={pluginName} onChange={setPluginName} placeholder="my_plugin" mono />
                    </div>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', cursor: 'pointer', paddingBottom: 2 }}>
                      <input type="checkbox" checked={forceInstall} onChange={e => setForceInstall(e.target.checked)} />
                      Overwrite existing
                    </label>
                  </div>
                  <PrimaryBtn onClick={handleInstall} disabled={!pluginName.trim()} loading={installing}>
                    {!installing && <Download size={13} />}
                    {installing ? 'Installing…' : 'Install Plugin'}
                  </PrimaryBtn>

                  {installResult && (
                    <div style={{ marginTop: 12 }}>
                      {installResult.ok ? (
                        <Alert type="success">
                          Installed to{' '}
                          <code style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{installResult.path}</code>
                          {installResult.actions_registered?.length
                            ? ` · Actions: ${installResult.actions_registered.join(', ')}`
                            : ''}
                        </Alert>
                      ) : (
                        <Alert type="error">{installResult.error}</Alert>
                      )}
                    </div>
                  )}
                </Card>
              )}

              {/* ── Empty state ───────────────────────────────────────── */}
              {!hasCode && !generating && (
                <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--fg4)' }}>
                  <Blocks size={38} style={{ margin: '0 auto 12px', opacity: 0.35, display: 'block' }} />
                  <p style={{ fontFamily: 'var(--sans)', fontSize: 14, marginBottom: 6 }}>
                    Describe a workflow above to generate your first plugin.
                  </p>
                  <p style={{ fontFamily: 'var(--sans)', fontSize: 12, opacity: 0.7 }}>
                    Requires OpenCode server —{' '}
                    <code style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>opencode serve --port 4096</code>
                  </p>
                </div>
              )}

            </div>

            {/* ── History drawer ── */}
            {historyOpen && (
              <div style={{ animation: 'slideInRight 0.18s ease forwards', height: '100%' }}>
                <PBHistoryDrawer
                  entries={history}
                  activeId={activeHistoryId}
                  onSelect={loadHistoryEntry}
                  onDelete={id => setHistory(prev => prev.filter(e => e.id !== id))}
                  onClear={() => setHistory([])}
                  onClose={() => setHistoryOpen(false)}
                />
              </div>
            )}

          </div>
        </div>
      </div>
    </>
  );
}
