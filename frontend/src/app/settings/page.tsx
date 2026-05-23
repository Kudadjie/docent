'use client';

import { useState, useEffect, useRef } from 'react';
import { Settings, Trash2, Pencil, Check, X, BookOpen, RefreshCw, Activity, Key, EyeOff, Zap, HardDriveDownload, CloudUpload, RotateCcw, AlertTriangle } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import StatusBanner, { type DotState } from '@/components/StatusBanner';
import Toast, { type ToastData } from '@/components/Toast';
import { useDarkMode } from '@/hooks/useDarkMode';
import { useNotifications } from '@/lib/notifications';
import { useTour } from '@/hooks/useTour';
import { TOUR_KEYS, TOUR_LABELS, tourHasSeen, tourReset, tourResetAll } from '@/lib/tour';
import { extractMessage } from '@/lib/toast-utils';

interface ReadingConfig {
  database_dir: string | null;
  queue_collection: string;
  output_dir: string | null;
}

interface ResearchConfig {
  tavily_api_key: string | null;
  semantic_scholar_api_key: string | null;
  alphaxiv_api_key: string | null;
  groq_api_key: string | null;
  gemini_api_key: string | null;
  openrouter_api_key: string | null;
  mistral_api_key: string | null;
  cerebras_api_key: string | null;
}

interface ConfigData {
  reading: ReadingConfig;
  research: ResearchConfig;
}

interface DoctorCheck {
  label: string;
  status: 'OK' | 'WARN' | 'FAIL' | 'SKIP';
  version: string;
  detail: string;
}

// ── Config row (for non-secret values) ───────────────────────────────────────

const READING_FIELDS: {
  key: keyof ReadingConfig;
  label: string;
  description: string;
  placeholder: string;
}[] = [
  {
    key: 'database_dir',
    label: 'Database directory',
    description: 'Local folder where your PDFs are stored. Docent counts PDFs here and uses this path for paper scanning.',
    placeholder: '~/Documents/Papers',
  },
  {
    key: 'queue_collection',
    label: 'Mendeley collection',
    description: 'Name of the Mendeley collection to sync from. Must exactly match the collection name in the Mendeley desktop app.',
    placeholder: 'Docent-Queue',
  },
  {
    key: 'output_dir',
    label: 'Research output directory',
    description: 'Folder where Studio research outputs are saved. Defaults to ~/docent/research/ if not set.',
    placeholder: '~/docent/research',
  },
];

const RESEARCH_KEY_FIELDS: {
  key: keyof ResearchConfig;
  label: string;
  description: string;
  placeholder: string;
}[] = [
  {
    key: 'tavily_api_key',
    label: 'Tavily',
    description: 'Web search for research workflows. Free tier: 1,000 calls/month. Get a key at app.tavily.com — no credit card needed.',
    placeholder: 'tvly-...',
  },
  {
    key: 'alphaxiv_api_key',
    label: 'alphaXiv',
    description: 'Academic paper search and AI overviews. Free key at alphaxiv.org/settings.',
    placeholder: 'ax-...',
  },
  {
    key: 'semantic_scholar_api_key',
    label: 'Semantic Scholar',
    description: 'Optional — raises API rate limits for scholarly search. api.semanticscholar.org',
    placeholder: 'your-key',
  },
  {
    key: 'groq_api_key',
    label: 'Groq',
    description: 'Fast, cheap AI backend. Free tier at console.groq.com.',
    placeholder: 'gsk_...',
  },
  {
    key: 'gemini_api_key',
    label: 'Gemini',
    description: 'Google AI backend. Free tier at aistudio.google.com.',
    placeholder: 'AIza...',
  },
  {
    key: 'openrouter_api_key',
    label: 'OpenRouter',
    description: 'Access multiple AI models via one key. Pay-as-you-go at openrouter.ai.',
    placeholder: 'sk-or-...',
  },
  {
    key: 'mistral_api_key',
    label: 'Mistral',
    description: 'Mistral AI backend. console.mistral.ai.',
    placeholder: 'your-key',
  },
  {
    key: 'cerebras_api_key',
    label: 'Cerebras',
    description: 'Cerebras AI backend. cloud.cerebras.ai.',
    placeholder: 'your-key',
  },
];

function ConfigRow({
  label,
  description,
  value,
  placeholder,
  onSave,
}: {
  label: string;
  description: string;
  value: string | null;
  placeholder: string;
  onSave: (v: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);

  function startEdit() {
    setDraft(value ?? '');
    setEditing(true);
  }

  async function save() {
    setSaving(true);
    await onSave(draft.trim());
    setSaving(false);
    setEditing(false);
  }

  function cancel() {
    setEditing(false);
    setDraft('');
  }

  return (
    <div style={{
      padding: '16px 0',
      borderBottom: '1px solid var(--border)',
      display: 'grid',
      gridTemplateColumns: '1fr auto',
      gap: '12px 24px',
      alignItems: 'start',
    }}>
      <div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', marginBottom: 3 }}>
          {label}
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', lineHeight: 1.5 }}>
          {description}
        </div>
        <div style={{ marginTop: 8 }}>
          {editing ? (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                autoFocus
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') cancel(); }}
                placeholder={placeholder}
                style={{
                  fontFamily: 'var(--mono)', fontSize: 12,
                  padding: '5px 10px', borderRadius: 6,
                  border: '1px solid #18E299',
                  background: 'var(--bg-card)', color: 'var(--fg1)',
                  outline: 'none', width: 320,
                }}
              />
              <button
                onClick={save}
                disabled={saving}
                aria-label="Save"
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: 28, height: 28, borderRadius: 6, border: 'none',
                  background: 'rgba(24,226,153,0.15)', color: '#0fa76e',
                  cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.6 : 1,
                }}
              >
                <Check size={14} strokeWidth={2} />
              </button>
              <button
                onClick={cancel}
                aria-label="Cancel"
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: 28, height: 28, borderRadius: 6, border: 'none',
                  background: 'var(--gray100)', color: 'var(--fg3)',
                  cursor: 'pointer',
                }}
              >
                <X size={14} strokeWidth={2} />
              </button>
            </div>
          ) : (
            <span style={{
              fontFamily: 'var(--mono)', fontSize: 12,
              color: value ? 'var(--fg2)' : 'var(--fg4)',
              fontStyle: value ? 'normal' : 'italic',
            }}>
              {value ?? 'not set'}
            </span>
          )}
        </div>
      </div>

      {!editing && (
        <button
          onClick={startEdit}
          aria-label={`Edit ${label}`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '5px 10px', borderRadius: 6,
            border: '1px solid var(--border-md)',
            background: 'transparent', color: 'var(--fg3)',
            fontFamily: 'var(--sans)', fontSize: 12,
            cursor: 'pointer', whiteSpace: 'nowrap', marginTop: 2,
          }}
        >
          <Pencil size={12} strokeWidth={1.5} />
          Edit
        </button>
      )}
    </div>
  );
}

// ── Secret key row (always starts empty on edit, never shows raw value) ──────

function SecretKeyRow({
  label,
  description,
  masked,
  placeholder,
  onSave,
}: {
  label: string;
  description: string;
  masked: string | null;
  placeholder: string;
  onSave: (v: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    await onSave(draft.trim());
    setSaving(false);
    setEditing(false);
    setDraft('');
  }

  function cancel() {
    setEditing(false);
    setDraft('');
  }

  const isSet = !!masked;

  return (
    <div style={{
      padding: '14px 0',
      borderBottom: '1px solid var(--border)',
      display: 'grid',
      gridTemplateColumns: '1fr auto',
      gap: '8px 24px',
      alignItems: 'start',
    }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
          <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)' }}>
            {label}
          </span>
          {isSet && (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 3,
              fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 500,
              padding: '1px 6px', borderRadius: 9999,
              background: 'rgba(24,226,153,0.15)', color: '#0fa76e',
              textTransform: 'uppercase', letterSpacing: '0.3px',
            }}>
              set
            </span>
          )}
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', lineHeight: 1.5 }}>
          {description}
        </div>
        <div style={{ marginTop: 6 }}>
          {editing ? (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                autoFocus
                type="password"
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') cancel(); }}
                placeholder={isSet ? 'Enter new key to replace…' : placeholder}
                style={{
                  fontFamily: 'var(--mono)', fontSize: 12,
                  padding: '5px 10px', borderRadius: 6,
                  border: '1px solid #18E299',
                  background: 'var(--bg-card)', color: 'var(--fg1)',
                  outline: 'none', width: 320,
                }}
              />
              <button
                onClick={save}
                disabled={saving || !draft.trim()}
                aria-label="Save"
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: 28, height: 28, borderRadius: 6, border: 'none',
                  background: 'rgba(24,226,153,0.15)', color: '#0fa76e',
                  cursor: saving || !draft.trim() ? 'default' : 'pointer',
                  opacity: saving || !draft.trim() ? 0.5 : 1,
                }}
              >
                <Check size={14} strokeWidth={2} />
              </button>
              <button
                onClick={cancel}
                aria-label="Cancel"
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: 28, height: 28, borderRadius: 6, border: 'none',
                  background: 'var(--gray100)', color: 'var(--fg3)',
                  cursor: 'pointer',
                }}
              >
                <X size={14} strokeWidth={2} />
              </button>
            </div>
          ) : (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              fontFamily: 'var(--mono)', fontSize: 12,
              color: isSet ? 'var(--fg2)' : 'var(--fg4)',
              fontStyle: isSet ? 'normal' : 'italic',
            }}>
              {isSet ? (
                <>
                  <EyeOff size={11} strokeWidth={1.5} style={{ color: 'var(--fg4)' }} />
                  {masked}
                </>
              ) : 'not set'}
            </span>
          )}
        </div>
      </div>

      {!editing && (
        <button
          onClick={() => setEditing(true)}
          aria-label={`${isSet ? 'Replace' : 'Set'} ${label} key`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '5px 10px', borderRadius: 6,
            border: '1px solid var(--border-md)',
            background: 'transparent', color: 'var(--fg3)',
            fontFamily: 'var(--sans)', fontSize: 12,
            cursor: 'pointer', whiteSpace: 'nowrap', marginTop: 2,
          }}
        >
          <Key size={11} strokeWidth={1.5} />
          {isSet ? 'Replace' : 'Set key'}
        </button>
      )}
    </div>
  );
}

// ── Doctor status badge ───────────────────────────────────────────────────────

const STATUS_COLOR: Record<DoctorCheck['status'], string> = {
  OK: '#0fa76e',
  WARN: '#C97B00',
  FAIL: '#D45656',
  SKIP: 'var(--fg4)',
};

const STATUS_BG: Record<DoctorCheck['status'], string> = {
  OK: 'rgba(24,226,153,0.12)',
  WARN: 'rgba(201,123,0,0.1)',
  FAIL: 'rgba(212,86,86,0.1)',
  SKIP: 'var(--gray100)',
};

function StatusBadge({ status }: { status: DoctorCheck['status'] }) {
  return (
    <span style={{
      fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600,
      padding: '2px 7px', borderRadius: 9999,
      background: STATUS_BG[status],
      color: STATUS_COLOR[status],
      textTransform: 'uppercase', letterSpacing: '0.4px',
      flexShrink: 0,
    }}>
      {status}
    </span>
  );
}

// ── Section card ─────────────────────────────────────────────────────────────

function SectionCard({ icon, title, description, children }: {
  icon: React.ReactNode;
  title: string;
  description: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ padding: '16px 20px 14px', borderBottom: '1px solid var(--border)', background: 'linear-gradient(135deg, #18E29920 0%, transparent 60%)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
          {icon}
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', margin: 0 }}>
            {title}
          </h2>
        </div>
        <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', lineHeight: 1.5, margin: 0 }}>
          {description}
        </p>
      </div>
      <div style={{ padding: '0 20px' }}>{children}</div>
    </div>
  );
}

function KeyGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{
        padding: '12px 0 2px',
        fontFamily: 'var(--mono)', fontSize: 9.5, fontWeight: 600,
        color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase',
      }}>
        {label}
      </div>
      {children}
    </div>
  );
}

// ── OpenCode section ──────────────────────────────────────────────────────────

function OpenCodeSection() {
  const [running, setRunning] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/opencode/status')
      .then(r => r.json())
      .then((j: { running: boolean }) => setRunning(j.running))
      .catch(() => setRunning(false));
  }, []);

  async function toggle() {
    setBusy(true); setMsg(null);
    try {
      const url = running ? '/api/opencode/stop' : '/api/opencode/start';
      const r = await fetch(url, { method: 'POST' });
      const j = await r.json() as { ok?: boolean; status?: string; error?: string };
      if (!j.ok && j.error) { setMsg(j.error); return; }
      setRunning(j.status !== 'stopped');
      setMsg(j.status === 'already_running' ? 'Already running.' : j.status === 'started' ? 'Server started on :4096.' : 'Server stopped.');
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  const dotColor = running === true ? '#18E299' : running === false ? '#D45656' : '#999';

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Zap size={13} strokeWidth={1.5} color="#6366f1" />
        <h2 style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', margin: 0 }}>OpenCode server</h2>
      </div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: dotColor, flexShrink: 0, animation: running === true ? 'logo-dot-blink 2s step-end infinite' : 'none' }} />
            <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)' }}>
              {running === null ? 'Checking…' : running ? 'Running on :4096' : 'Stopped'}
            </span>
          </div>
          <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.55 }}>
            Required for the Docent research backend. Uses your configured LLM API key.
          </div>
          {msg && <div style={{ marginTop: 6, fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg4)' }}>{msg}</div>}
        </div>
        <button onClick={toggle} disabled={busy || running === null}
          style={{ padding: '7px 16px', borderRadius: 8, border: '1px solid var(--border-md)', background: running ? 'rgba(212,86,86,0.08)' : 'rgba(99,102,241,0.08)', color: running ? '#D45656' : '#6366f1', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600, cursor: busy ? 'wait' : 'pointer', opacity: (busy || running === null) ? 0.6 : 1 }}>
          {busy ? 'Working…' : running ? 'Stop server' : 'Start server'}
        </button>
      </div>
    </div>
  );
}

// ── NotebookLM auth section ───────────────────────────────────────────────────

interface NlmStatus {
  installed: boolean;
  playwright_ok: boolean;
  authenticated: boolean;
  fix?: string;
}

function NotebookLMSection() {
  const [nlmStatus, setNlmStatus] = useState<NlmStatus | null>(null);
  const [nlmBusy, setNlmBusy] = useState(false);
  const [nlmMsg, setNlmMsg] = useState<string | null>(null);
  const [nlmChecking, setNlmChecking] = useState(false);

  async function checkNlmStatus() {
    setNlmChecking(true);
    try {
      const r = await fetch('/api/notebooklm/auth-status');
      const j = await r.json() as NlmStatus;
      setNlmStatus(j);
    } catch {
      setNlmStatus({ installed: false, playwright_ok: false, authenticated: false });
    } finally {
      setNlmChecking(false);
    }
  }

  useEffect(() => { checkNlmStatus(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleNlmAuth() {
    setNlmBusy(true); setNlmMsg(null);
    try {
      const r = await fetch('/api/notebooklm/auth', { method: 'POST' });
      const j = await r.json() as { ok: boolean; message?: string; error?: string };
      if (j.ok) {
        setNlmMsg('A terminal window has opened. Complete authentication there, then click "Refresh status".');
      } else {
        setNlmMsg(j.error ?? 'Could not open terminal.');
      }
    } catch (e) {
      setNlmMsg(String(e));
    } finally {
      setNlmBusy(false);
    }
  }

  const notReady = !nlmStatus?.installed || !nlmStatus?.playwright_ok;

  const nlmDot = nlmStatus === null ? '#999'
    : !nlmStatus.installed ? '#C97B00'
    : !nlmStatus.playwright_ok ? '#C97B00'
    : nlmStatus.authenticated ? '#18E299' : '#D45656';

  const nlmLabel = nlmStatus === null ? 'Checking…'
    : !nlmStatus.installed ? 'Not installed'
    : !nlmStatus.playwright_ok ? 'Playwright browser missing'
    : nlmStatus.authenticated ? 'Authenticated' : 'Not authenticated';

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <BookOpen size={13} strokeWidth={1.5} color="#0ea5e9" />
        <h2 style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', margin: 0 }}>NotebookLM</h2>
      </div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: nlmDot, flexShrink: 0 }} />
            <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)' }}>
              {nlmLabel}
            </span>
          </div>
          <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.55 }}>
            {!nlmStatus?.installed ? (
              <>Not installed. Install with: <code style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)' }}>pip install notebooklm</code></>
            ) : !nlmStatus.playwright_ok ? (
              <>
                Playwright&apos;s Chromium browser is not downloaded — required for the login flow.
                Run:{' '}
                <code style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)' }}>
                  {nlmStatus.fix ?? 'playwright install chromium'}
                </code>
                {' '}then click <strong style={{ color: 'var(--fg2)', fontWeight: 500 }}>Refresh status</strong>.
                This may need repeating after <code style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>notebooklm</code> updates.
              </>
            ) : (
              <>
                Required for the <em>to-notebook</em> action. Authentication opens a browser — complete it
                in the terminal window, then click{' '}
                <strong style={{ color: 'var(--fg2)', fontWeight: 500 }}>Refresh status</strong> to confirm.
              </>
            )}
          </div>
          {nlmMsg && (
            <div style={{ marginTop: 8, fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg4)', lineHeight: 1.5 }}>
              {nlmMsg}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end', flexShrink: 0 }}>
          <button
            onClick={handleNlmAuth}
            disabled={nlmBusy || notReady}
            style={{
              padding: '7px 16px', borderRadius: 8,
              border: '1px solid rgba(14,165,233,0.4)',
              background: 'rgba(14,165,233,0.08)', color: '#0ea5e9',
              fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600,
              cursor: (nlmBusy || notReady) ? 'not-allowed' : 'pointer',
              opacity: notReady ? 0.5 : 1,
              whiteSpace: 'nowrap',
            }}
          >
            {nlmBusy ? 'Opening…' : 'Authenticate'}
          </button>
          <button
            onClick={checkNlmStatus}
            disabled={nlmChecking}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '5px 12px', borderRadius: 7,
              border: '1px solid var(--border-md)',
              background: 'transparent', color: 'var(--fg3)',
              fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
              cursor: nlmChecking ? 'default' : 'pointer',
              opacity: nlmChecking ? 0.6 : 1,
              whiteSpace: 'nowrap',
            }}
          >
            <RefreshCw size={12} strokeWidth={1.5} style={{ animation: nlmChecking ? 'spin 1s linear infinite' : 'none' }} />
            {nlmChecking ? 'Checking…' : 'Refresh status'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { dark, toggleDark } = useDarkMode();
  const { addNotification } = useNotifications();

  useTour('settings', [
    {
      popover: {
        title: 'Settings',
        description: "Configure everything about how Docent works — your reference manager connection, AI API keys, cloud backup, and system health.",
      },
    },
    {
      popover: {
        title: 'Reading configuration',
        description: 'Set your Mendeley collection name and local PDF folder. These tell Docent where your papers live and which collection to sync from.',
      },
    },
    {
      popover: {
        title: 'API keys',
        description: 'Add keys for research backends: Tavily for web search, alphaXiv for academic papers, Gemini or Groq for AI synthesis. Each key unlocks a different Studio capability.',
      },
    },
    {
      popover: {
        title: 'Health check & Backup',
        description: "The Health check at the bottom verifies every tool is wired up correctly. Backup lets you save your queue and research history to Google Drive.",
      },
    },
  ]);

  const [tourSeenMap, setTourSeenMap] = useState<Record<string, boolean>>({});
  useEffect(() => {
    const map: Record<string, boolean> = {};
    TOUR_KEYS.forEach(k => { map[k] = tourHasSeen(k); });
    setTourSeenMap(map);
  }, []);

  function handleTourReset(key: string) {
    tourReset(key as Parameters<typeof tourReset>[0]);
    setTourSeenMap(prev => ({ ...prev, [key]: false }));
    setToast({ type: 'success', message: `Tour reset — visit ${TOUR_LABELS[key as keyof typeof TOUR_LABELS]} to start the walkthrough.` });
  }

  function handleTourResetAll() {
    tourResetAll();
    const map: Record<string, boolean> = {};
    TOUR_KEYS.forEach(k => { map[k] = false; });
    setTourSeenMap(map);
    setToast({ type: 'success', message: 'All tours reset — visit each page to see the walkthrough.' });
  }

  const [config, setConfig] = useState<ConfigData | null>(null);
  const [toast, setToast] = useState<ToastData | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [doctorChecks, setDoctorChecks] = useState<DoctorCheck[] | null>(null);
  const [loadingDoctor, setLoadingDoctor] = useState(false);
  const [dotState, setDotState] = useState<DotState>('idle');

  // ── Backup state ───────────────────────────────────────────────────────────
  interface BackupStatus { credentials_configured: boolean; deps_installed: boolean; token_exists: boolean; install_cmd: string | null }
  interface DriveBackup { id: string; name: string; size_mb: number; created: string }
  function fmtSize(mb: number): string {
    if (mb >= 1) return `${mb.toFixed(1)} MB`;
    const kb = Math.round(mb * 1024);
    return kb > 0 ? `${kb} KB` : '< 1 KB';
  }
  const [backupStatus, setBackupStatus] = useState<BackupStatus | null>(null);
  const [driveBackups, setDriveBackups] = useState<DriveBackup[] | null>(null);
  const [loadingBackups, setLoadingBackups] = useState(false);
  const [backingUp, setBackingUp] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [confirmRestoreId, setConfirmRestoreId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showSetup, setShowSetup] = useState(false);
  const [credentialsText, setCredentialsText] = useState('');
  const [savingCreds, setSavingCreds] = useState(false);
  const [installingDeps, setInstallingDeps] = useState(false);
  const dotResetRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function signalDot(state: DotState) {
    setDotState(state);
    if (dotResetRef.current) clearTimeout(dotResetRef.current);
    if (state === 'done' || state === 'error') {
      dotResetRef.current = setTimeout(() => setDotState('idle'), 2000);
    }
  }

  async function runDoctor() {
    setLoadingDoctor(true);
    signalDot('working');
    try {
      const res = await fetch('/api/doctor');
      const data = await res.json() as DoctorCheck[];
      setDoctorChecks(data);
      signalDot('done');

      const issues = data.filter(c => c.status === 'FAIL' || c.status === 'WARN');
      if (issues.length > 0) {
        addNotification({
          type: 'update',
          title: `${issues.length} health ${issues.length === 1 ? 'issue' : 'issues'} found`,
          body: issues.map(c => c.label).join(', '),
        });
      }
    } catch {
      setDoctorChecks([]);
      signalDot('error');
    } finally {
      setLoadingDoctor(false);
    }
  }

  /* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  // runDoctor is stable (function declaration, not recreated per render)
  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then((d: ConfigData) => setConfig(d))
      .catch(() => {});

    runDoctor();
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

  // ── Backup handlers ─────────────────────────────────────────────────────────
  useEffect(() => {
    fetch('/api/backup/status').then(r => r.json()).then(setBackupStatus).catch(() => {});
  }, []);

  async function loadDriveBackups() {
    setLoadingBackups(true);
    try {
      const res = await fetch('/api/backup/list');
      const data = await res.json() as { ok: boolean; backups?: DriveBackup[]; error?: string };
      if (data.ok) setDriveBackups(data.backups ?? []);
      else setToast({ type: 'error', message: data.error ?? 'Failed to list backups' });
    } catch { setToast({ type: 'error', message: 'Could not reach backup service' }); }
    finally { setLoadingBackups(false); }
  }

  async function handleBackupToDrive() {
    setBackingUp(true); signalDot('working');
    try {
      const res = await fetch('/api/backup/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ local_only: false }) });
      const data = await res.json() as { ok: boolean; archive_name?: string; size_mb?: number; files_excluded?: number; error?: string };
      if (data.ok) {
        const excWarn = (data.files_excluded ?? 0) > 0 ? ` (${data.files_excluded} file(s) >100 MB excluded)` : '';
        setToast({ type: 'success', message: `Backed up to Google Drive — ${fmtSize(data.size_mb ?? 0)}${excWarn}` });
        signalDot('done');
        setDriveBackups(null); // force refresh on next open
      } else {
        setToast({ type: 'error', message: data.error ?? 'Backup failed' });
        signalDot('error');
      }
    } catch { setToast({ type: 'error', message: 'Backup request failed' }); signalDot('error'); }
    finally { setBackingUp(false); }
  }

  function handleDownloadZip() {
    setDownloading(true);
    const a = document.createElement('a');
    a.href = '/api/backup/download';
    a.click();
    setTimeout(() => setDownloading(false), 3000);
  }

  async function handleRestoreFromDrive(backupId: string, name: string) {
    setRestoringId(backupId); setConfirmRestoreId(null); signalDot('working');
    try {
      const res = await fetch('/api/backup/restore', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ backup_id: backupId }) });
      const data = await res.json() as { ok: boolean; restored_from?: string; error?: string };
      if (data.ok) {
        setToast({ type: 'success', message: `Restored from ${data.restored_from}. Restart docent ui to apply.` });
        signalDot('done');
      } else {
        setToast({ type: 'error', message: data.error ?? 'Restore failed' });
        signalDot('error');
      }
    } catch { setToast({ type: 'error', message: 'Restore request failed' }); signalDot('error'); }
    finally { setRestoringId(null); }
  }

  async function handleInstallDeps() {
    setInstallingDeps(true); signalDot('working');
    try {
      const res = await fetch('/api/backup/install-deps', { method: 'POST' });
      const data = await res.json() as { ok: boolean; error?: string };
      if (data.ok) {
        setToast({ type: 'success', message: 'Dependencies installed.' });
        signalDot('done');
        fetch('/api/backup/status').then(r => r.json()).then(setBackupStatus).catch(() => {});
      } else {
        setToast({ type: 'error', message: data.error ?? 'Installation failed' });
        signalDot('error');
      }
    } catch { setToast({ type: 'error', message: 'Install request failed' }); signalDot('error'); }
    finally { setInstallingDeps(false); }
  }

  async function handleDeleteBackup(backupId: string) {
    setDeletingId(backupId);
    try {
      const res = await fetch('/api/backup/delete', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backup_id: backupId }),
      });
      const data = await res.json() as { ok: boolean; error?: string };
      if (data.ok) {
        setDriveBackups(prev => prev ? prev.filter(b => b.id !== backupId) : null);
        setToast({ type: 'success', message: 'Backup deleted from Google Drive.' });
      } else {
        setToast({ type: 'error', message: data.error ?? 'Delete failed' });
      }
    } catch { setToast({ type: 'error', message: 'Delete request failed' }); }
    finally { setDeletingId(null); }
  }

  async function handleSaveCredentials() {
    if (!credentialsText.trim()) return;
    setSavingCreds(true);
    try {
      const res = await fetch('/api/backup/setup', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credentials_json: credentialsText.trim() }),
      });
      const data = await res.json() as { ok: boolean; error?: string };
      if (data.ok) {
        setToast({ type: 'success', message: 'Credentials saved. Run a backup to authenticate with Google.' });
        setShowSetup(false);
        setCredentialsText('');
        // Refresh status
        fetch('/api/backup/status').then(r => r.json()).then(setBackupStatus).catch(() => {});
      } else {
        setToast({ type: 'error', message: data.error ?? 'Could not save credentials' });
      }
    } catch { setToast({ type: 'error', message: 'Request failed' }); }
    finally { setSavingCreds(false); }
  }

  async function handleSaveReading(key: keyof ReadingConfig, value: string) {
    signalDot('working');
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section: 'reading', key, value }),
      });
      const body = await res.json() as { ok: boolean; reading?: ReadingConfig; error?: string };
      if (!res.ok || !body.ok) {
        const clean = extractMessage((body.error ?? 'Unknown error').replace(/\x1b\[[0-9;]*m/g, '').trim());
        setToast({ type: 'error', message: `Could not save: ${clean.slice(0, 120)}` });
        signalDot('error');
      } else {
        if (body.reading) setConfig(c => c ? { ...c, reading: body.reading! } : c);
        setToast({ type: 'success', message: `Saved reading.${key}.` });
        signalDot('done');
      }
    } catch {
      setToast({ type: 'error', message: 'Network error.' });
      signalDot('error');
    }
  }

  async function handleSaveResearch(key: keyof ResearchConfig, value: string) {
    signalDot('working');
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section: 'research', key, value }),
      });
      const body = await res.json() as { ok: boolean; research?: ResearchConfig; error?: string };
      if (!res.ok || !body.ok) {
        const clean = extractMessage((body.error ?? 'Unknown error').replace(/\x1b\[[0-9;]*m/g, '').trim());
        setToast({ type: 'error', message: `Could not save: ${clean.slice(0, 120)}` });
        signalDot('error');
      } else {
        if (body.research) setConfig(c => c ? { ...c, research: body.research! } : c);
        setToast({ type: 'success', message: `Saved ${key.replace(/_api_key$/, '')} key.` });
        signalDot('done');
      }
    } catch {
      setToast({ type: 'error', message: 'Network error.' });
      signalDot('error');
    }
  }

  async function handleClearQueue() {
    setClearing(true);
    signalDot('working');
    try {
      const res = await fetch('/api/actions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'queue-clear', confirmed: true }),
      });
      const body = await res.json().catch(() => ({})) as Record<string, string>;
      if (!res.ok) {
        const clean = extractMessage((body.error ?? body.stderr ?? 'Unknown error').replace(/\x1b\[[0-9;]*m/g, '').trim());
        setToast({ type: 'error', message: `Clear failed: ${clean.slice(0, 120)}` });
        signalDot('error');
      } else {
        setToast({ type: 'success', message: 'Reading queue cleared.' });
        signalDot('done');
      }
    } catch {
      setToast({ type: 'error', message: 'Network error.' });
      signalDot('error');
    } finally {
      setClearing(false);
      setConfirmClear(false);
    }
  }

  const rc = config?.reading;
  const res = config?.research;

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="settings" queueCount={0} dark={dark} />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner dark={dark} onToggleDark={toggleDark} dotState={dotState} />

        <div style={{ flex: 1, overflowY: 'auto', position: 'relative',
          backgroundImage: 'var(--hero-grad)',
          backgroundRepeat: 'no-repeat',
          backgroundSize: '100% 100%',
          backgroundAttachment: 'local',
        }}>
          {/* Header */}
          <div style={{ position: 'relative', padding: '28px 32px 24px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <Settings size={16} strokeWidth={1.5} color="#0fa76e" />
              <h1 style={{
                fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 600,
                letterSpacing: '-0.3px', color: 'var(--fg1)', margin: 0,
              }}>
                Settings
              </h1>
            </div>
            <p style={{ position: 'relative', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)', margin: 0 }}>
              Manage your Docent preferences and data.
            </p>
          </div>

          <div style={{ padding: '32px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, maxWidth: 1100, alignItems: 'start' }}>

            {/* Left column: Reading config + System health */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <SectionCard
                icon={<BookOpen size={14} strokeWidth={1.5} color="#0fa76e" />}
                title="Reading"
                description="Controls how Docent syncs your reading queue with Mendeley and your local paper database."
              >
                {READING_FIELDS.map(f => (
                  <ConfigRow
                    key={f.key}
                    label={f.label}
                    description={f.description}
                    value={rc ? (rc[f.key] as string | null) : null}
                    placeholder={f.placeholder}
                    onSave={v => handleSaveReading(f.key, v)}
                  />
                ))}
              </SectionCard>

            {/* System health — directly under Reading in left column */}
            <section>
              <div style={{
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 12, overflow: 'hidden',
              }}>
                <div style={{
                  padding: '16px 20px 14px', borderBottom: '1px solid var(--border)',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  background: 'linear-gradient(135deg, #18E29920 0%, transparent 60%)',
                }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                      <Activity size={14} strokeWidth={1.5} color="#0fa76e" />
                      <h2 style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', margin: 0 }}>
                        System health
                      </h2>
                    </div>
                    <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', margin: 0, lineHeight: 1.5 }}>
                      Environment checks for all Docent dependencies.
                    </p>
                  </div>
                  <button
                    onClick={runDoctor} disabled={loadingDoctor}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      padding: '5px 12px', borderRadius: 7,
                      border: '1px solid var(--border-md)',
                      background: 'transparent', color: 'var(--fg3)',
                      fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
                      cursor: loadingDoctor ? 'default' : 'pointer', opacity: loadingDoctor ? 0.6 : 1,
                    }}
                  >
                    <RefreshCw size={12} strokeWidth={1.5} style={{ animation: loadingDoctor ? 'spin 1s linear infinite' : 'none' }} />
                    {loadingDoctor ? 'Checking…' : 'Refresh'}
                  </button>
                </div>

                {doctorChecks === null ? (
                  <div style={{ padding: '28px 20px', textAlign: 'center', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg4)' }}>
                    Checking your environment…
                  </div>
                ) : doctorChecks.length === 0 ? (
                  <div style={{ padding: '16px 20px', fontFamily: 'var(--sans)', fontSize: 13, color: '#D45656' }}>
                    Could not run health checks.
                  </div>
                ) : (
                  <>
                    {doctorChecks.map((check, i) => (
                      <div key={check.label} style={{
                        display: 'grid',
                        gridTemplateColumns: '150px 52px 90px 1fr',
                        gap: '0 12px', alignItems: 'start',
                        padding: '11px 20px',
                        borderBottom: i < doctorChecks.length - 1 ? '1px solid var(--border)' : 'none',
                        background: check.status === 'FAIL' ? 'rgba(212,86,86,0.03)'
                          : check.status === 'WARN' ? 'rgba(201,123,0,0.02)' : 'transparent',
                      }}>
                        <span style={{ fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 500, color: 'var(--fg1)', paddingTop: 1 }}>
                          {check.label}
                        </span>
                        <div style={{ paddingTop: 2 }}><StatusBadge status={check.status} /></div>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--fg4)', paddingTop: 2, wordBreak: 'break-all' }}>
                          {check.version !== '-' ? check.version : ''}
                        </span>
                        <span style={{
                          fontFamily: 'var(--sans)', fontSize: 11.5, lineHeight: 1.5,
                          color: check.status === 'FAIL' ? '#D45656'
                            : check.status === 'WARN' ? '#C97B00' : 'var(--fg4)',
                        }}>
                          {check.detail !== '-' ? check.detail : ''}
                        </span>
                      </div>
                    ))}
                    {(() => {
                      const issues = doctorChecks.filter(c => c.status === 'FAIL' || c.status === 'WARN').length;
                      const ok = doctorChecks.filter(c => c.status === 'OK').length;
                      return (
                        <div style={{
                          padding: '9px 20px', borderTop: '1px solid var(--border)',
                          background: 'var(--bg-subtle)',
                          fontFamily: 'var(--sans)', fontSize: 11.5,
                          color: issues === 0 ? '#0fa76e' : '#C97B00',
                        }}>
                          {issues === 0 ? `All ${ok} checks passed` : `${issues} ${issues === 1 ? 'issue' : 'issues'} found`}
                        </div>
                      );
                    })()}
                  </>
                )}
              </div>
            </section>
            </div> {/* end left column */}

            {/* Right column: API keys */}
            <SectionCard
              icon={<Key size={14} strokeWidth={1.5} color="#0fa76e" />}
              title="API keys"
              description={<>Keys for research backends and paper search. Stored in <span style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>~/.docent/config.toml</span> — never sent anywhere except the respective provider.</>}
            >
              <KeyGroup label="Search & discovery">
                {RESEARCH_KEY_FIELDS.filter(f => ['tavily_api_key','alphaxiv_api_key','semantic_scholar_api_key'].includes(f.key)).map(f => (
                  <SecretKeyRow key={f.key} label={f.label} description={f.description}
                    masked={res ? (res[f.key] ?? null) : null} placeholder={f.placeholder}
                    onSave={v => handleSaveResearch(f.key, v)} />
                ))}
              </KeyGroup>
              <KeyGroup label="AI backends">
                {RESEARCH_KEY_FIELDS.filter(f => !['tavily_api_key','alphaxiv_api_key','semantic_scholar_api_key'].includes(f.key)).map(f => (
                  <SecretKeyRow key={f.key} label={f.label} description={f.description}
                    masked={res ? (res[f.key] ?? null) : null} placeholder={f.placeholder}
                    onSave={v => handleSaveResearch(f.key, v)} />
                ))}
              </KeyGroup>
            </SectionCard>

            {/* OpenCode server */}
            <section style={{ gridColumn: '1 / -1' }}>
              <OpenCodeSection />
            </section>

            {/* NotebookLM auth */}
            <section style={{ gridColumn: '1 / -1' }}>
              <NotebookLMSection />
            </section>

            {/* Backup & Restore — full width */}
            <section style={{ gridColumn: '1 / -1' }}>
              <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
                {/* Header */}
                <div style={{ padding: '16px 20px 14px', borderBottom: '1px solid var(--border)', background: 'linear-gradient(135deg, #3B82F620 0%, transparent 60%)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                      <HardDriveDownload size={14} strokeWidth={1.5} color="#3B82F6" />
                      <h2 style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', margin: 0 }}>Backup & Restore</h2>
                    </div>
                    <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', margin: 0 }}>
                      Snapshot your queue, config, and research outputs. Files over 100 MB are excluded.
                    </p>
                  </div>
                </div>

                <div style={{ padding: '20px' }}>
                  {/* Status row */}
                  {backupStatus && (
                    <div style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 8, background: 'var(--bg-subtle)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                      {backupStatus.credentials_configured && backupStatus.deps_installed ? (
                        <>
                          <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#18E299', flexShrink: 0 }} />
                          <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)' }}>
                            Google Drive configured{backupStatus.token_exists ? ' · authenticated' : ' · will authenticate on first run'}
                          </span>
                        </>
                      ) : backupStatus.credentials_configured && !backupStatus.deps_installed ? (
                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <AlertTriangle size={13} strokeWidth={2} color="#C37D0D" style={{ flexShrink: 0 }} />
                            <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)', flex: 1 }}>
                              Credentials found but dependencies missing.
                            </span>
                            <button
                              onClick={handleInstallDeps}
                              disabled={installingDeps}
                              style={{
                                display: 'inline-flex', alignItems: 'center', gap: 6,
                                fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
                                color: '#fff', background: '#C37D0D',
                                border: 'none', borderRadius: 6,
                                padding: '4px 12px', cursor: installingDeps ? 'wait' : 'pointer',
                                whiteSpace: 'nowrap', flexShrink: 0,
                              }}
                            >
                              <RefreshCw size={11} strokeWidth={2} style={{ animation: installingDeps ? 'spin 1s linear infinite' : 'none' }} />
                              {installingDeps ? 'Installing…' : 'Install now'}
                            </button>
                          </div>
                          {/* Terminal command for techy users */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <code style={{
                              flex: 1, fontFamily: 'var(--mono)', fontSize: 11,
                              color: 'var(--fg3)', background: 'var(--gray100)',
                              border: '1px solid var(--border)', borderRadius: 5,
                              padding: '4px 10px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                            }}>
                              pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
                            </code>
                            <button
                              onClick={() => navigator.clipboard.writeText('pip install google-api-python-client google-auth-oauthlib google-auth-httplib2').then(() => setToast({ type: 'success', message: 'Copied!' }))}
                              title="Copy to clipboard"
                              style={{ background: 'var(--gray100)', border: '1px solid var(--border)', borderRadius: 5, padding: '4px 8px', cursor: 'pointer', color: 'var(--fg4)', display: 'flex', flexShrink: 0 }}
                            >
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--fg4)', flexShrink: 0 }} />
                          <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', flex: 1 }}>
                            Google Drive not configured.
                          </span>
                          <button
                            onClick={() => setShowSetup(s => !s)}
                            style={{ fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500, color: '#3B82F6', background: 'transparent', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 6, padding: '3px 10px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                          >
                            {showSetup ? 'Hide setup' : 'Set up Google Drive'}
                          </button>
                        </>
                      )}
                    </div>
                  )}

                  {/* Setup panel */}
                  {showSetup && (
                    <div style={{ marginBottom: 16, border: '1px solid rgba(59,130,246,0.25)', borderRadius: 10, overflow: 'hidden' }}>
                      {/* Steps */}
                      <div style={{ padding: '14px 18px', background: 'rgba(59,130,246,0.04)', borderBottom: '1px solid rgba(59,130,246,0.15)' }}>
                        <div style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', marginBottom: 10 }}>
                          Google Drive — four steps
                        </div>
                        {[
                          { n: '1', text: <>Go to <a href="https://console.cloud.google.com" target="_blank" rel="noreferrer" style={{ color: '#3B82F6', textDecoration: 'none', fontWeight: 500 }}>console.cloud.google.com</a> → create or select a project → enable the <strong style={{ color: 'var(--fg1)' }}>Google Drive API</strong>.</> },
                          { n: '2', text: <>Credentials → Create Credentials → <strong style={{ color: 'var(--fg1)' }}>OAuth client ID</strong> → Application type: <strong style={{ color: 'var(--fg1)' }}>Desktop app</strong> → Download JSON.</> },
                          { n: '3', text: <><strong style={{ color: 'var(--fg1)' }}>OAuth consent screen</strong> → fill in <strong style={{ color: 'var(--fg1)' }}>App name</strong>, <strong style={{ color: 'var(--fg1)' }}>User support email</strong>, and <strong style={{ color: 'var(--fg1)' }}>Developer contact email</strong> (required — missing any of these causes a Google 500 error). Then under <strong style={{ color: 'var(--fg1)' }}>Audience</strong> click <strong style={{ color: 'var(--fg1)' }}>Publish app</strong>. On first sign-in Google shows an "unverified app" warning — click <em>Advanced → Go to app</em> to proceed.</> },
                          { n: '4', text: <>Paste the downloaded credentials JSON below and click <strong style={{ color: 'var(--fg1)' }}>Save</strong>. A browser window will open for sign-in on the first backup run.</> },
                        ].map(({ n, text }) => (
                          <div key={n} style={{ display: 'flex', gap: 12, marginBottom: 8, alignItems: 'flex-start' }}>
                            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color: '#3B82F6', background: 'rgba(59,130,246,0.12)', borderRadius: '50%', width: 20, height: 20, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>{n}</span>
                            <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.55 }}>{text}</span>
                          </div>
                        ))}
                      </div>

                      {/* Paste / upload area */}
                      <div style={{ padding: '14px 18px' }}>
                        <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', marginBottom: 8 }}>
                          Paste credentials JSON
                          <span style={{ color: 'var(--fg4)', marginLeft: 8 }}>— or —</span>
                          <label style={{ marginLeft: 8, color: '#3B82F6', cursor: 'pointer', fontSize: 12 }}>
                            choose file
                            <input
                              type="file" accept=".json" style={{ display: 'none' }}
                              onChange={e => {
                                const f = e.target.files?.[0];
                                if (!f) return;
                                const reader = new FileReader();
                                reader.onload = ev => setCredentialsText(ev.target?.result as string ?? '');
                                reader.readAsText(f);
                              }}
                            />
                          </label>
                        </div>
                        <textarea
                          value={credentialsText}
                          onChange={e => setCredentialsText(e.target.value)}
                          placeholder='{"installed":{"client_id":"...","client_secret":"...",...}}'
                          rows={5}
                          style={{
                            width: '100%', boxSizing: 'border-box',
                            fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)',
                            background: 'var(--bg-subtle)', border: '1px solid var(--border-md)',
                            borderRadius: 7, padding: '10px 12px', resize: 'vertical', outline: 'none',
                          }}
                        />
                        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                          <button
                            onClick={handleSaveCredentials}
                            disabled={savingCreds || !credentialsText.trim()}
                            style={{
                              padding: '6px 16px', borderRadius: 7,
                              border: 'none', background: '#3B82F6', color: '#fff',
                              fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                              cursor: (savingCreds || !credentialsText.trim()) ? 'not-allowed' : 'pointer',
                              opacity: !credentialsText.trim() ? 0.5 : 1,
                            }}
                          >
                            {savingCreds ? 'Saving…' : 'Save credentials'}
                          </button>
                          <button
                            onClick={() => { setShowSetup(false); setCredentialsText(''); }}
                            style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid var(--border-md)', background: 'transparent', color: 'var(--fg3)', fontFamily: 'var(--sans)', fontSize: 13, cursor: 'pointer' }}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Action buttons */}
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
                    {/* Drive backup */}
                    <button
                      onClick={handleBackupToDrive}
                      disabled={backingUp || !backupStatus?.credentials_configured || !backupStatus?.deps_installed}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 7,
                        padding: '7px 16px', borderRadius: 8,
                        border: '1px solid rgba(59,130,246,0.4)',
                        background: 'rgba(59,130,246,0.08)', color: '#3B82F6',
                        fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                        cursor: (backingUp || !backupStatus?.credentials_configured || !backupStatus?.deps_installed) ? 'not-allowed' : 'pointer',
                        opacity: (!backupStatus?.credentials_configured || !backupStatus?.deps_installed) ? 0.5 : 1,
                      }}
                    >
                      <CloudUpload size={14} strokeWidth={1.5} style={{ animation: backingUp ? 'spin 1s linear infinite' : 'none' }} />
                      {backingUp ? 'Backing up…' : 'Backup to Drive'}
                    </button>

                    {/* Local zip download */}
                    <button
                      onClick={handleDownloadZip}
                      disabled={downloading}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 7,
                        padding: '7px 16px', borderRadius: 8,
                        border: '1px solid var(--border-md)',
                        background: 'transparent', color: 'var(--fg2)',
                        fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                        cursor: downloading ? 'wait' : 'pointer',
                      }}
                    >
                      <HardDriveDownload size={14} strokeWidth={1.5} />
                      {downloading ? 'Preparing…' : 'Download local zip'}
                    </button>

                    {/* List Drive backups */}
                    {backupStatus?.credentials_configured && backupStatus?.deps_installed && (
                      <button
                        onClick={() => { if (driveBackups === null) loadDriveBackups(); else setDriveBackups(null); }}
                        disabled={loadingBackups}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: 7,
                          padding: '7px 16px', borderRadius: 8,
                          border: '1px solid var(--border-md)',
                          background: 'transparent', color: 'var(--fg3)',
                          fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 400,
                          cursor: loadingBackups ? 'wait' : 'pointer',
                        }}
                      >
                        <RefreshCw size={13} strokeWidth={1.5} style={{ animation: loadingBackups ? 'spin 1s linear infinite' : 'none' }} />
                        {driveBackups !== null ? 'Hide Drive backups' : 'Show Drive backups'}
                      </button>
                    )}
                  </div>

                  {/* Drive backup list */}
                  {driveBackups !== null && (
                    <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
                      {driveBackups.length === 0 ? (
                        <div style={{ padding: '20px', textAlign: 'center', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg4)' }}>
                          No backups found in Google Drive.
                        </div>
                      ) : (
                        <>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto', gap: 0, background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border)', padding: '7px 16px' }}>
                            {['Name', 'Size', 'Date', ''].map((h, i) => (
                              <span key={i} style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase', textAlign: i > 1 ? 'right' : 'left', paddingRight: i < 3 ? 16 : 0 }}>{h}</span>
                            ))}
                          </div>
                          {driveBackups.map(b => (
                            <div key={b.id} style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto', gap: 0, padding: '10px 16px', borderBottom: '1px solid var(--border)', alignItems: 'center' }}>
                              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingRight: 16 }}>{b.name}</span>
                              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)', paddingRight: 16, textAlign: 'right' }}>{fmtSize(b.size_mb)}</span>
                              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)', paddingRight: 16, textAlign: 'right' }}>{b.created}</span>
                              <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                                {confirmRestoreId === b.id ? (
                                  <>
                                    <button onClick={() => handleRestoreFromDrive(b.id, b.name)} disabled={restoringId === b.id} style={{ fontFamily: 'var(--sans)', fontSize: 11, fontWeight: 600, color: '#fff', background: '#D45656', border: 'none', borderRadius: 5, padding: '3px 10px', cursor: 'pointer' }}>
                                      {restoringId === b.id ? 'Restoring…' : 'Confirm'}
                                    </button>
                                    <button onClick={() => setConfirmRestoreId(null)} style={{ fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg3)', background: 'transparent', border: '1px solid var(--border-md)', borderRadius: 5, padding: '3px 10px', cursor: 'pointer' }}>
                                      Cancel
                                    </button>
                                  </>
                                ) : (
                                  <>
                                    <button onClick={() => setConfirmRestoreId(b.id)} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg3)', background: 'transparent', border: '1px solid var(--border-md)', borderRadius: 5, padding: '3px 10px', cursor: 'pointer' }}>
                                      <RotateCcw size={11} strokeWidth={1.5} />
                                      Restore
                                    </button>
                                    <button
                                      onClick={() => handleDeleteBackup(b.id)}
                                      disabled={deletingId === b.id}
                                      title="Delete from Google Drive"
                                      style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 26, height: 26, borderRadius: 5, border: '1px solid var(--border-md)', background: 'transparent', color: deletingId === b.id ? 'var(--fg4)' : '#D45656', cursor: deletingId === b.id ? 'wait' : 'pointer' }}
                                    >
                                      {deletingId === b.id
                                        ? <RefreshCw size={11} strokeWidth={1.5} style={{ animation: 'spin 1s linear infinite' }} />
                                        : <Trash2 size={11} strokeWidth={1.5} />}
                                    </button>
                                  </>
                                )}
                              </div>
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </section>

            {/* Walkthrough — full width */}
            <section style={{ gridColumn: '1 / -1' }}>
              <SectionCard
                icon={<Zap size={14} strokeWidth={1.5} color="#8B5CF6" />}
                title="Walkthrough tours"
                description="Each page has a guided walkthrough that runs the first time you visit it. Reset individual tours below or restart all of them at once."
              >
                <div style={{ padding: '16px 0' }}>
                  {TOUR_KEYS.map(key => (
                    <div
                      key={key}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '10px 0', borderBottom: '1px solid var(--border)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg1)' }}>
                          {TOUR_LABELS[key]}
                        </span>
                        <span style={{
                          fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600,
                          padding: '2px 7px', borderRadius: 9999,
                          background: tourSeenMap[key] ? 'rgba(24,226,153,0.12)' : 'var(--gray100)',
                          color: tourSeenMap[key] ? '#0fa76e' : 'var(--fg4)',
                          textTransform: 'uppercase', letterSpacing: '0.4px',
                        }}>
                          {tourSeenMap[key] ? 'seen' : 'not yet'}
                        </span>
                      </div>
                      <button
                        onClick={() => handleTourReset(key)}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: 5,
                          padding: '4px 12px', borderRadius: 6,
                          border: '1px solid var(--border-md)',
                          background: 'transparent', color: 'var(--fg3)',
                          fontFamily: 'var(--sans)', fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        <RotateCcw size={11} strokeWidth={1.5} />
                        Replay
                      </button>
                    </div>
                  ))}
                  <div style={{ paddingTop: 14 }}>
                    <button
                      onClick={handleTourResetAll}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '6px 14px', borderRadius: 7,
                        border: '1px solid rgba(139,92,246,0.35)',
                        background: 'rgba(139,92,246,0.07)', color: '#8B5CF6',
                        fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                        cursor: 'pointer',
                      }}
                    >
                      <RotateCcw size={13} strokeWidth={1.5} />
                      Reset all tours
                    </button>
                  </div>
                </div>
              </SectionCard>
            </section>

            {/* Danger zone — full width */}
            <section style={{ gridColumn: '1 / -1' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Trash2 size={13} strokeWidth={1.5} color="#D45656" />
                <h2 style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: '#D45656', margin: 0 }}>
                  Danger zone
                </h2>
              </div>

              <div style={{
                border: '1px solid rgba(212,86,86,0.3)',
                borderRadius: 10,
                padding: '20px 24px',
                background: 'rgba(212,86,86,0.03)',
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24 }}>
                  <div>
                    <div style={{
                      fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 500,
                      color: 'var(--fg1)', marginBottom: 4,
                    }}>
                      Clear reading queue
                    </div>
                    <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.5 }}>
                      Removes all entries from the local queue. Your Mendeley library is not affected —
                      you can restore the queue by running{' '}
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)' }}>
                        Sync Mendeley
                      </span>{' '}
                      on the Reading page.
                    </div>
                  </div>

                  {confirmClear ? (
                    <div style={{ display: 'flex', gap: 8, flexShrink: 0, alignItems: 'center' }}>
                      <button
                        onClick={handleClearQueue}
                        disabled={clearing}
                        style={{
                          padding: '6px 14px', borderRadius: 7, border: 'none',
                          background: '#D45656', color: '#fff',
                          fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
                          cursor: clearing ? 'default' : 'pointer',
                          opacity: clearing ? 0.6 : 1, whiteSpace: 'nowrap',
                        }}
                      >
                        {clearing ? 'Clearing…' : 'Yes, clear'}
                      </button>
                      <button
                        onClick={() => setConfirmClear(false)}
                        style={{
                          padding: '6px 12px', borderRadius: 7,
                          border: '1px solid var(--border-md)',
                          background: 'transparent', color: 'var(--fg3)',
                          fontFamily: 'var(--sans)', fontSize: 13, cursor: 'pointer',
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmClear(true)}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '6px 14px', borderRadius: 7,
                        border: '1px solid rgba(212,86,86,0.4)',
                        background: 'transparent', color: '#D45656',
                        fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                        cursor: 'pointer', flexShrink: 0,
                      }}
                    >
                      <Trash2 size={14} strokeWidth={1.5} />
                      Clear queue
                    </button>
                  )}
                </div>
              </div>
            </section>
          </div>
        </div>
      </main>

      {toast && <Toast toast={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
