'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  FlaskConical, Play, Square, CheckCircle, XCircle, AlertTriangle,
  Copy, Plus, ChevronDown, ChevronRight, File, X, ExternalLink,
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';

// ── Types ─────────────────────────────────────────────────────────────────────

type Status = 'idle' | 'running' | 'success' | 'failure';
type ActionId =
  | 'deep' | 'lit' | 'peer' | 'compare' | 'draft' | 'replicate' | 'audit'
  | 'search' | 'getpaper' | 'scholarly' | 'notebook'
  | 'cfgshow' | 'cfgset';

interface ActionMeta { id: ActionId; label: string; form: string; }
interface LogEntry { phase: string; text: string; }

interface FormState {
  topic: string; backend: string; dest: string; guides: string[];
  artifact: string; artifactA: string; artifactB: string;
  query: string; maxResults: number; arxivId: string;
  outPath: string; srcPath: string; maxSources: number;
  nlm: boolean; gate: boolean; persp: boolean;
  cfgKey: string; cfgVal: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const ACTIONS: { label: string; items: ActionMeta[] }[] = [
  {
    label: 'Research',
    items: [
      { id: 'deep',      label: 'Deep research',     form: 'topic' },
      { id: 'lit',       label: 'Literature review',  form: 'topic' },
      { id: 'peer',      label: 'Peer review',        form: 'artifact' },
      { id: 'compare',   label: 'Compare',            form: 'compare' },
      { id: 'draft',     label: 'Draft',              form: 'topic' },
      { id: 'replicate', label: 'Replicate',          form: 'artifact' },
      { id: 'audit',     label: 'Audit',              form: 'artifact' },
    ],
  },
  {
    label: 'Utilities',
    items: [
      { id: 'search',    label: 'Search papers',      form: 'search' },
      { id: 'getpaper',  label: 'Get paper',          form: 'getpaper' },
      { id: 'scholarly', label: 'Scholarly search',   form: 'search' },
      { id: 'notebook',  label: 'To notebook',        form: 'notebook' },
    ],
  },
  {
    label: 'Config',
    items: [
      { id: 'cfgshow', label: 'Show config',    form: 'cfgshow' },
      { id: 'cfgset',  label: 'Set config key', form: 'cfgset' },
    ],
  },
];

const ALL_ACTIONS = ACTIONS.flatMap(g => g.items);
const findAction = (id: ActionId): ActionMeta => ALL_ACTIONS.find(a => a.id === id) ?? ALL_ACTIONS[0];

const BACKENDS = ['Free', 'Feynman', 'Docent', 'Groq', 'Gemini', 'OpenRouter', 'Anthropic', 'OpenAI', 'Ollama', 'LM Studio'];

const SCRIPTS: Record<string, LogEntry[]> = {
  deep: [
    { phase: 'plan',   text: 'Decomposing topic into 4 sub-questions' },
    { phase: 'search', text: 'arXiv: 47 candidates; filtering by relevance' },
    { phase: 'search', text: 'Semantic Scholar: 18 candidates' },
    { phase: 'fetch',  text: 'Downloading 12 PDFs in parallel' },
    { phase: 'parse',  text: 'Extracting sections, tables, figures' },
    { phase: 'cost',   text: 'Estimated synthesis cost: $0.42 (4k tokens)' },
    { phase: 'synth',  text: 'Drafting outline → 7 sections, 18 citations' },
    { phase: 'synth',  text: 'Writing body paragraphs (section 3 of 7)' },
    { phase: 'save',   text: 'Wrote report.md and citations.bib' },
    { phase: 'done',   text: 'Run complete in 4m 12s' },
  ],
  notebook: [
    { phase: 'plan',   text: 'Loading sources.json (24 entries)' },
    { phase: 'fetch',  text: 'Resolving DOIs and arXiv IDs' },
    { phase: 'parse',  text: 'Quality gate: scanning for contradictions' },
    { phase: 'search', text: 'NLM web research: 5 supplementary sources' },
    { phase: 'synth',  text: 'Generating perspectives (3 personas)' },
    { phase: 'warn',   text: '2 sources failed quality gate (broken DOI)' },
    { phase: 'save',   text: 'Notebook nb_4f2c updated' },
    { phase: 'done',   text: '18 sources added in 1m 38s' },
  ],
  search: [
    { phase: 'search', text: 'Querying arXiv API' },
    { phase: 'parse',  text: 'Ranking by recency × citation count' },
    { phase: 'done',   text: '5 results' },
  ],
  scholarly: [
    { phase: 'search', text: 'Querying Semantic Scholar' },
    { phase: 'search', text: 'Cross-referencing with arXiv' },
    { phase: 'done',   text: '5 results' },
  ],
  getpaper: [
    { phase: 'fetch',  text: 'Resolving arXiv:2401.12345' },
    { phase: 'parse',  text: 'Extracting abstract and metadata' },
    { phase: 'synth',  text: 'Generating AI overview' },
    { phase: 'done',   text: 'Paper details ready' },
  ],
  cfgshow: [{ phase: 'done', text: 'Loaded ~/.docent/config.toml' }],
  cfgset:  [{ phase: 'save', text: 'Writing ~/.docent/config.toml' }, { phase: 'done', text: 'Key saved' }],
};
const scriptFor = (id: ActionId) => SCRIPTS[id] ?? SCRIPTS.deep;

const PHASE_TONE: Record<string, string> = {
  plan: 'info', search: 'info', fetch: 'info', parse: 'info',
  synth: 'info', save: 'info', done: 'info',
  warn: 'warn', cost: 'warn',
  error: 'error',
};

function runLabel(action: ActionMeta): string {
  if (action.id === 'search' || action.id === 'scholarly') return 'Search';
  if (action.id === 'getpaper') return 'Look up';
  if (action.id === 'cfgshow') return 'Show config';
  if (action.id === 'cfgset') return 'Save';
  if (action.id === 'notebook') return 'Build notebook';
  return `Run ${action.label.toLowerCase()}`;
}

// ── Primitives ─────────────────────────────────────────────────────────────────

function PrimaryBtn({ icon, children, onClick, disabled, full }: {
  icon?: React.ReactNode; children: React.ReactNode;
  onClick?: () => void; disabled?: boolean; full?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
      padding: '9px 18px', borderRadius: 9999,
      background: disabled ? '#a8e8cf' : '#18E299',
      color: '#0d0d0d', fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
      border: 'none', cursor: disabled ? 'not-allowed' : 'pointer',
      width: full ? '100%' : 'auto', opacity: disabled ? 0.7 : 1,
      transition: 'opacity 0.12s',
    }}>
      {icon}{children}
    </button>
  );
}

function GhostBtn({ icon, children, onClick, size = 'md', danger }: {
  icon?: React.ReactNode; children?: React.ReactNode;
  onClick?: () => void; size?: 'sm' | 'md'; danger?: boolean;
}) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: size === 'sm' ? '4px 10px' : '5px 12px', borderRadius: 9999,
        border: '1px solid var(--border-md)',
        background: hov ? 'var(--gray100)' : 'transparent',
        color: danger ? '#D45656' : 'var(--fg2)',
        fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
        cursor: 'pointer', transition: 'background 0.12s', whiteSpace: 'nowrap',
      }}
    >
      {icon && <span style={{ color: danger ? '#D45656' : 'var(--fg4)', display: 'flex' }}>{icon}</span>}
      {children}
    </button>
  );
}

function PillToggle({ active, onClick, disabled, tooltip, children }: {
  active?: boolean; onClick?: () => void; disabled?: boolean;
  tooltip?: string; children: React.ReactNode;
}) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      title={tooltip}
      style={{
        padding: '5px 12px', borderRadius: 9999,
        border: active ? '1px solid #18E299' : '1px solid var(--border-md)',
        background: active ? '#18E299' : (hov && !disabled ? 'var(--gray100)' : 'transparent'),
        color: active ? '#0d0d0d' : (disabled ? 'var(--fg4)' : 'var(--fg2)'),
        fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.55 : 1,
        transition: 'all 0.12s', whiteSpace: 'nowrap',
      }}
    >
      {children}
    </button>
  );
}

function Segmented({ value, onChange, options }: {
  value: string; onChange: (v: string) => void; options: string[];
}) {
  return (
    <div style={{
      display: 'inline-flex', padding: 2, background: 'var(--gray100)',
      borderRadius: 9999, border: '1px solid var(--border)',
    }}>
      {options.map(opt => {
        const active = opt === value;
        return (
          <button key={opt} onClick={() => onChange(opt)} style={{
            padding: '4px 14px', borderRadius: 9999, border: 'none',
            background: active ? 'var(--bg-card)' : 'transparent',
            color: active ? 'var(--fg1)' : 'var(--fg3)',
            fontFamily: 'var(--sans)', fontSize: 12,
            fontWeight: active ? 500 : 400, cursor: 'pointer',
            transition: 'all 0.12s',
            boxShadow: active ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
          }}>{opt}</button>
        );
      })}
    </div>
  );
}

function StudioInput({ value, onChange, placeholder, mono }: {
  value: string; onChange: (v: string) => void;
  placeholder?: string; mono?: boolean;
}) {
  const [focus, setFocus] = useState(false);
  return (
    <input
      type="text" value={value} onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
      style={{
        width: '100%', padding: '8px 12px',
        border: `1px solid ${focus ? '#18E299' : 'var(--border-md)'}`,
        borderRadius: 8,
        fontFamily: mono ? 'var(--mono)' : 'var(--sans)',
        fontSize: 13, color: 'var(--fg1)', background: 'var(--bg)',
        outline: 'none', transition: 'border-color 0.15s',
      }}
    />
  );
}

function FieldLabel({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <label style={{
      display: 'block', marginBottom: 6,
      fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500, color: 'var(--fg3)',
    }}>
      {children}
      {hint && <span style={{ color: 'var(--fg4)', fontWeight: 400, marginLeft: 6 }}>{hint}</span>}
    </label>
  );
}

function Field({ label, hint, children }: {
  label: string; hint?: string; children: React.ReactNode;
}) {
  return (
    <div>
      <FieldLabel hint={hint}>{label}</FieldLabel>
      {children}
    </div>
  );
}

function Note({ tone = 'info', children }: { tone?: 'info' | 'warn'; children: React.ReactNode }) {
  return (
    <div style={{
      fontFamily: 'var(--sans)', fontSize: 11.5, lineHeight: 1.5,
      color: tone === 'warn' ? 'var(--amber-text)' : 'var(--fg3)',
      padding: tone === 'warn' ? '6px 10px' : '4px 0',
      borderRadius: tone === 'warn' ? 6 : 0,
      background: tone === 'warn' ? 'var(--amber-bg)' : 'transparent',
      borderLeft: tone === 'warn' ? '2px solid var(--amber-border)' : 'none',
      marginTop: 8,
    }}>
      {children}
    </div>
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!checked)} style={{
      width: 30, height: 18, borderRadius: 9999, border: 'none',
      background: checked ? '#18E299' : 'var(--gray200)',
      position: 'relative', cursor: 'pointer', padding: 0,
      transition: 'background 0.15s', flexShrink: 0,
    }}>
      <span style={{
        position: 'absolute', top: 2, left: checked ? 14 : 2,
        width: 14, height: 14, borderRadius: '50%', background: '#fff',
        boxShadow: '0 1px 2px rgba(0,0,0,0.2)', transition: 'left 0.15s',
      }} />
    </button>
  );
}

function Stepper({ value, onChange, min = 1, max = 99 }: {
  value: number; onChange: (v: number) => void; min?: number; max?: number;
}) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center',
      border: '1px solid var(--border-md)', borderRadius: 8,
      overflow: 'hidden', background: 'var(--bg)',
    }}>
      <button onClick={() => onChange(Math.max(min, value - 1))} style={{
        width: 28, height: 30, border: 'none', background: 'transparent',
        cursor: 'pointer', color: 'var(--fg3)', fontSize: 16, fontFamily: 'var(--sans)',
      }}>−</button>
      <div style={{
        width: 36, textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 12,
        color: 'var(--fg1)', fontWeight: 500,
        borderLeft: '1px solid var(--border)', borderRight: '1px solid var(--border)',
        padding: '7px 0',
      }}>{value}</div>
      <button onClick={() => onChange(Math.min(max, value + 1))} style={{
        width: 28, height: 30, border: 'none', background: 'transparent',
        cursor: 'pointer', color: 'var(--fg3)', fontSize: 14, fontFamily: 'var(--sans)',
      }}>+</button>
    </div>
  );
}

function CodeBlock({ children }: { children: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div style={{
      position: 'relative', background: 'var(--code-bg)',
      border: '1px solid var(--border)', borderRadius: 8,
      padding: '10px 36px 10px 12px',
      fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--fg2)',
      lineHeight: 1.55, letterSpacing: '0.2px',
      wordBreak: 'break-all', whiteSpace: 'pre-wrap',
    }}>
      {children}
      <button
        onClick={() => {
          navigator.clipboard?.writeText(children);
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        }}
        title="Copy"
        style={{
          position: 'absolute', top: 6, right: 6, width: 24, height: 24,
          borderRadius: 6, border: 'none', background: 'transparent',
          color: copied ? '#0fa76e' : 'var(--fg4)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        {copied ? <CheckCircle size={12} strokeWidth={1.5} /> : <Copy size={12} strokeWidth={1.6} />}
      </button>
    </div>
  );
}

function Chip({ color, children }: { color?: string; children: React.ReactNode }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '4px 10px', borderRadius: 9999,
      background: color ? color + '1f' : 'var(--gray100)',
      color: color ?? 'var(--fg2)',
      fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
      letterSpacing: '0.4px', textTransform: 'uppercase',
    }}>
      {children}
    </span>
  );
}

// ── Action list ────────────────────────────────────────────────────────────────

function ActionList({ activeId, onSelect }: {
  activeId: ActionId; onSelect: (id: ActionId) => void;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {ACTIONS.map(group => (
        <div key={group.label}>
          <div style={{
            padding: '0 4px 6px',
            fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
            color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase',
          }}>
            {group.label}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {group.items.map(item => {
              const isActive = item.id === activeId;
              return (
                <button key={item.id} onClick={() => onSelect(item.id as ActionId)} style={{
                  width: '100%', textAlign: 'left', padding: '6px 10px',
                  borderRadius: 6, border: 'none', cursor: 'pointer',
                  fontFamily: 'var(--sans)', fontSize: 12.5,
                  fontWeight: isActive ? 500 : 400,
                  color: isActive ? '#0fa76e' : 'var(--fg2)',
                  background: isActive ? 'rgba(24,226,153,0.12)' : 'transparent',
                  transition: 'all 0.1s',
                  display: 'flex', alignItems: 'center',
                }}>
                  <span style={{
                    width: 4, height: 4, borderRadius: '50%', marginRight: 9, flexShrink: 0,
                    background: isActive ? '#18E299' : 'transparent',
                  }} />
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Backend selector + Guide files ────────────────────────────────────────────

function BackendSelector({ value, onChange, freeDisabled }: {
  value: string; onChange: (v: string) => void; freeDisabled?: boolean;
}) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
      {BACKENDS.map(b => (
        <PillToggle
          key={b}
          active={value === b}
          onClick={() => onChange(b)}
          disabled={freeDisabled && b === 'Free'}
          tooltip={freeDisabled && b === 'Free' ? 'Not available for this action' : undefined}
        >
          {b}
        </PillToggle>
      ))}
    </div>
  );
}

function GuideFiles({ files, setFiles }: {
  files: string[]; setFiles: (f: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  return (
    <div>
      <button onClick={() => setOpen(o => !o)} style={{
        display: 'flex', alignItems: 'center', gap: 5, background: 'transparent',
        border: 'none', cursor: 'pointer', padding: '2px 0',
        color: 'var(--fg3)', fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
      }}>
        <span style={{
          display: 'flex', transition: 'transform 0.12s',
          transform: open ? 'rotate(0deg)' : 'rotate(-90deg)',
        }}>
          <ChevronDown size={14} strokeWidth={2} />
        </span>
        Add guide files <span style={{ color: 'var(--fg4)', fontWeight: 400, marginLeft: 4 }}>(optional)</span>
      </button>
      {open && (
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', gap: 6 }}>
            <div style={{ flex: 1 }}>
              <StudioInput value={draft} onChange={setDraft} placeholder="path/to/guide.pdf" mono />
            </div>
            <button
              onClick={() => { if (draft.trim()) { setFiles([...files, draft.trim()]); setDraft(''); } }}
              style={{
                padding: '8px 12px', borderRadius: 8,
                border: '1px solid var(--border-md)', background: 'var(--gray100)',
                color: 'var(--fg2)', fontFamily: 'var(--sans)', fontSize: 12,
                fontWeight: 500, cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: 4,
              }}
            >
              <Plus size={14} strokeWidth={2} /> Add
            </button>
          </div>
          {files.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {files.map((f, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '4px 8px', background: 'var(--gray100)', borderRadius: 6,
                  fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)',
                }}>
                  <span style={{ color: 'var(--fg4)', display: 'flex' }}>
                    <File size={13} strokeWidth={1.5} />
                  </span>
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f}</span>
                  <button
                    onClick={() => setFiles(files.filter((_, j) => j !== i))}
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--fg4)', display: 'flex', padding: 2 }}
                  >
                    <X size={12} strokeWidth={2} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Form variants ─────────────────────────────────────────────────────────────

function FormTopic({ state, set }: { state: FormState; set: (k: keyof FormState, v: unknown) => void }) {
  return (
    <>
      <Field label="Topic">
        <StudioInput value={state.topic} onChange={v => set('topic', v)}
          placeholder="e.g. storm surge inundation under climate change" />
      </Field>
      <Field label="Backend">
        <BackendSelector value={state.backend} onChange={v => set('backend', v)} />
        {state.backend === 'Free'
          ? <Note>No API key needed.</Note>
          : <Note tone="warn">Runs 3–30 min. May time out over MCP.</Note>}
      </Field>
      <Field label="Output destination">
        <Segmented value={state.dest} onChange={v => set('dest', v)} options={['Local', 'Notebook', 'Vault']} />
      </Field>
      <GuideFiles files={state.guides} setFiles={v => set('guides', v)} />
    </>
  );
}

function FormArtifact({ state, set }: { state: FormState; set: (k: keyof FormState, v: unknown) => void }) {
  const backend = state.backend === 'Free' ? 'Anthropic' : state.backend;
  return (
    <>
      <Field label="Artifact" hint="arXiv ID, PDF path, or URL">
        <StudioInput value={state.artifact} onChange={v => set('artifact', v)}
          placeholder="2401.12345 / paper.pdf / https://…" mono />
      </Field>
      <Field label="Backend">
        <BackendSelector value={backend} onChange={v => set('backend', v)} freeDisabled />
        <Note tone="warn">Runs 3–30 min. May time out over MCP.</Note>
      </Field>
      <GuideFiles files={state.guides} setFiles={v => set('guides', v)} />
    </>
  );
}

function FormCompare({ state, set }: { state: FormState; set: (k: keyof FormState, v: unknown) => void }) {
  const backend = state.backend === 'Free' ? 'Anthropic' : state.backend;
  return (
    <>
      <Field label="Artifact A" hint="arXiv / PDF / URL">
        <StudioInput value={state.artifactA} onChange={v => set('artifactA', v)} placeholder="2401.12345" mono />
      </Field>
      <Field label="Artifact B" hint="arXiv / PDF / URL">
        <StudioInput value={state.artifactB} onChange={v => set('artifactB', v)} placeholder="2310.06825" mono />
      </Field>
      <Field label="Backend">
        <BackendSelector value={backend} onChange={v => set('backend', v)} freeDisabled />
        <Note tone="warn">Runs 3–30 min. May time out over MCP.</Note>
      </Field>
      <GuideFiles files={state.guides} setFiles={v => set('guides', v)} />
    </>
  );
}

function FormSearch({ state, set }: { state: FormState; set: (k: keyof FormState, v: unknown) => void }) {
  return (
    <>
      <Field label="Query">
        <StudioInput value={state.query} onChange={v => set('query', v)}
          placeholder="e.g. coastal flooding bayesian" />
      </Field>
      <Field label="Max results">
        <Stepper value={state.maxResults} onChange={v => set('maxResults', v)} min={1} max={100} />
      </Field>
    </>
  );
}

function FormGetPaper({ state, set }: { state: FormState; set: (k: keyof FormState, v: unknown) => void }) {
  return (
    <Field label="arXiv ID or URL">
      <StudioInput value={state.arxivId} onChange={v => set('arxivId', v)}
        placeholder="e.g. 2401.12345 or arxiv.org/abs/…" mono />
    </Field>
  );
}

function FormNotebook({ state, set }: { state: FormState; set: (k: keyof FormState, v: unknown) => void }) {
  return (
    <>
      <Field label="Output file path" hint="(optional)">
        <StudioInput value={state.outPath} onChange={v => set('outPath', v)}
          placeholder="Auto-detect most recent" mono />
      </Field>
      <Field label="Sources file path" hint="(optional)">
        <StudioInput value={state.srcPath} onChange={v => set('srcPath', v)}
          placeholder="sources.json" mono />
      </Field>
      <Field label="Max sources">
        <Stepper value={state.maxSources} onChange={v => set('maxSources', v)} min={1} max={200} />
      </Field>
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 8,
        padding: '10px 12px', background: 'var(--gray100)', borderRadius: 8,
      }}>
        {([['nlm', 'NLM research'], ['gate', 'Quality gate'], ['persp', 'Perspectives']] as const).map(([k, lbl]) => (
          <div key={k} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)' }}>{lbl}</span>
            <Toggle checked={state[k]} onChange={v => set(k, v)} />
          </div>
        ))}
      </div>
    </>
  );
}

function FormCfgShow() {
  return (
    <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)', lineHeight: 1.5 }}>
      Display current configuration values. API keys are masked.
    </div>
  );
}

function FormCfgSet({ state, set }: { state: FormState; set: (k: keyof FormState, v: unknown) => void }) {
  return (
    <>
      <Field label="Key">
        <StudioInput value={state.cfgKey} onChange={v => set('cfgKey', v)}
          placeholder="tavily_api_key" mono />
      </Field>
      <Field label="Value">
        <StudioInput value={state.cfgVal} onChange={v => set('cfgVal', v)}
          placeholder="tvly-…" mono />
      </Field>
    </>
  );
}

const FORM_MAP: Record<string, React.ComponentType<{ state: FormState; set: (k: keyof FormState, v: unknown) => void }>> = {
  topic: FormTopic, artifact: FormArtifact, compare: FormCompare,
  search: FormSearch, getpaper: FormGetPaper, notebook: FormNotebook,
  cfgshow: FormCfgShow, cfgset: FormCfgSet,
};

// ── Free-tier gate ────────────────────────────────────────────────────────────

function FreeTierGate({ onCancel, onProceed }: { onCancel: () => void; onProceed: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel]);

  return (
    <div style={{
      background: 'var(--amber-bg)', borderLeft: '3px solid var(--amber-border)',
      borderRadius: '4px 8px 8px 4px', padding: '14px 16px',
      animation: 'fadeInUp 0.18s ease',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8,
        color: 'var(--amber-text)', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600,
      }}>
        <AlertTriangle size={14} strokeWidth={2} /> Free tier — confirm before running
      </div>
      <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 12px', display: 'flex', flexDirection: 'column', gap: 4 }}>
        {[
          'No AI synthesis — sources only',
          'Quality depends on search coverage',
          'Tavily optional (1k/month free); DuckDuckGo fallback',
          'This is a starting point, not a finished report',
        ].map(t => (
          <li key={t} style={{ display: 'flex', gap: 8, fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--amber-text)', lineHeight: 1.55 }}>
            <span style={{ marginTop: 7, width: 3, height: 3, borderRadius: '50%', background: 'var(--amber-text)', flexShrink: 0 }} />
            <span>{t}</span>
          </li>
        ))}
      </ul>
      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
        <GhostBtn size="sm" onClick={onCancel}>Cancel</GhostBtn>
        <button onClick={onProceed} style={{
          padding: '5px 14px', borderRadius: 9999, background: '#18E299',
          color: '#0d0d0d', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600,
          border: 'none', cursor: 'pointer',
        }}>
          Yes, proceed
        </button>
      </div>
    </div>
  );
}

// ── Left column ───────────────────────────────────────────────────────────────

function LeftColumn({ actionId, setActionId, state, set, onRun, gating, setGating }: {
  actionId: ActionId; setActionId: (id: ActionId) => void;
  state: FormState; set: (k: keyof FormState, v: unknown) => void;
  onRun: () => void; gating: boolean; setGating: (v: boolean) => void;
}) {
  const action = findAction(actionId);
  const Form = FORM_MAP[action.form];

  function handleRunClick() {
    const usesFree = action.form === 'topic' && state.backend === 'Free';
    if (usesFree) setGating(true);
    else onRun();
  }

  return (
    <aside style={{
      width: 380, flexShrink: 0, height: '100%',
      borderRight: '1px solid var(--border)', background: 'var(--bg)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ padding: '20px 22px 14px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 4 }}>
          <span style={{ color: '#0fa76e', display: 'flex' }}>
            <FlaskConical size={16} strokeWidth={1.5} />
          </span>
          <h1 style={{
            fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 600,
            color: 'var(--fg1)', letterSpacing: '-0.3px', margin: 0,
          }}>Studio</h1>
        </div>
        <p style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)', margin: 0 }}>
          Run AI research actions on papers and topics
        </p>
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 22px 0' }}>
        <ActionList activeId={actionId} onSelect={setActionId} />

        <div style={{ height: 1, background: 'var(--border)', margin: '18px 0 16px' }} />

        {/* Active action label */}
        <div style={{
          marginBottom: 12, fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
          color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span>{action.label}</span>
          <span style={{ flex: 1, height: 1, background: 'var(--border)' }} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingBottom: 16 }}>
          <Form state={state} set={set} />
        </div>
      </div>

      {/* Footer — Run button or free-tier gate */}
      <div style={{
        padding: '14px 22px 18px', borderTop: '1px solid var(--border)',
        background: 'var(--bg)', flexShrink: 0,
      }}>
        {gating ? (
          <FreeTierGate onCancel={() => setGating(false)} onProceed={() => { setGating(false); onRun(); }} />
        ) : (
          <PrimaryBtn full icon={<Play size={13} strokeWidth={2} />} onClick={handleRunClick}>
            {runLabel(action)}
          </PrimaryBtn>
        )}
      </div>
    </aside>
  );
}

// ── Log line ──────────────────────────────────────────────────────────────────

function LogLine({ phase, text, live }: { phase: string; text: string; live?: boolean }) {
  const tone = PHASE_TONE[phase] ?? 'info';
  const phaseColor = tone === 'warn' ? 'var(--amber-text)' : tone === 'error' ? 'var(--red-text)' : '#0fa76e';
  const phaseBg    = tone === 'warn' ? 'var(--amber-bg)' : tone === 'error' ? 'var(--red-bg)' : 'rgba(24,226,153,0.11)';
  const rowBg      = tone === 'warn' ? 'var(--amber-bg)' : tone === 'error' ? 'var(--red-bg)' : 'transparent';
  const rowBorder  = tone === 'warn' ? 'var(--amber-border)' : tone === 'error' ? '#E53535' : 'transparent';
  return (
    <div
      className={'log-line' + (live ? ' live' : '')}
      style={{
        display: 'flex', gap: 10, padding: '5px 12px 5px 10px',
        background: rowBg, borderLeft: `2px solid ${rowBorder}`,
        borderRadius: '2px 4px 4px 2px', alignItems: 'flex-start',
      }}
    >
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 9.5, fontWeight: 600,
        letterSpacing: '0.6px', textTransform: 'uppercase',
        color: phaseColor, background: phaseBg,
        padding: '2px 6px', borderRadius: 4, flexShrink: 0, marginTop: 1,
      }}>
        {phase}
      </span>
      <span style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.5, flex: 1, wordBreak: 'break-word' }}>
        {text}
        {live && (
          <span style={{ marginLeft: 4 }}>
            <span className="thinking-dot" />
            <span className="thinking-dot" />
            <span className="thinking-dot" />
          </span>
        )}
      </span>
    </div>
  );
}

// ── Result variants ───────────────────────────────────────────────────────────

function ResultResearchSuccess() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: '#0fa76e', display: 'flex' }}><CheckCircle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Done</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
          · 4m 12s · 18 sources
        </span>
      </div>
      <div>
        <FieldLabel>Output file</FieldLabel>
        <CodeBlock>{'~/docent/runs/2026-05-18_deep_storm-surge/report.md'}</CodeBlock>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Chip color="#0fa76e">Notebook · nb_4f2c</Chip>
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
        Backend returned <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5 }}>401 unauthorized</span>.
        The API key is missing or invalid.
      </div>
      <div>
        <FieldLabel>Fix</FieldLabel>
        <CodeBlock>{'docent studio config-set --key anthropic_api_key --value sk-ant-...'}</CodeBlock>
      </div>
    </div>
  );
}

function ResultSearch({ query }: { query: string }) {
  const rows = [
    { title: 'Storm surge attribution under non-stationary sea level rise', year: 2024, authors: 'Lin, N. · Emanuel, K.', source: 'arXiv' },
    { title: 'Bayesian inundation forecasting on US Atlantic coast', year: 2023, authors: 'Park, J. · Walsh, K.', source: 'JGR' },
    { title: 'Compound flooding from tropical cyclones: a review', year: 2022, authors: 'Wahl, T. · Jain, S.', source: 'Nat. Geo.' },
    { title: 'High-resolution coupled modeling of coastal flood risk', year: 2024, authors: 'Marsooli, R. · Lin, N.', source: 'PNAS' },
    { title: 'Tide-surge-wave interaction in shallow estuaries', year: 2021, authors: 'Vatvani, D. · Zijlema, M.', source: 'Ocean Eng.' },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>
        {rows.length} results · query <span style={{ fontFamily: 'var(--mono)', color: 'var(--fg2)' }}>"{query || 'storm surge inundation'}"</span>
      </div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border)' }}>
              {['Title', 'Year', 'Authors', 'Source', ''].map((c, i) => (
                <th key={i} style={{
                  padding: '8px 12px', textAlign: i === 4 ? 'right' : 'left',
                  fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
                  color: 'var(--fg4)', letterSpacing: '0.6px', textTransform: 'uppercase',
                }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} style={{ borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg1)', lineHeight: 1.4 }}>
                  <a href="#" style={{ color: 'var(--fg1)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                    {r.title}
                    <span style={{ color: 'var(--fg4)', opacity: 0.5, display: 'flex' }}>
                      <ExternalLink size={12} strokeWidth={1.5} />
                    </span>
                  </a>
                </td>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg3)', whiteSpace: 'nowrap' }}>{r.year}</td>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', whiteSpace: 'nowrap' }}>{r.authors}</td>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.4px', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{r.source}</td>
                <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                  <GhostBtn size="sm">Look up</GhostBtn>
                </td>
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
  const abstract = `We present a high-resolution coupled ocean-atmosphere model for storm surge attribution on the US Atlantic coast. The framework combines tropical cyclone synthetic tracks with a barotropic surge solver and applies Bayesian downscaling to convert ensemble forecasts into actionable inundation depth probabilities. Validation against historical events shows skill improvements of 12–18% over the prior generation of operational systems.`;
  const overview = `This paper extends Lin & Emanuel (2019) by adding non-stationary sea level rise priors to the Bayesian framework. The key novelty is the joint treatment of tide–surge–wave coupling in shallow estuaries — historically a major source of bias in operational forecasts. The authors release open-source code (GPL-3) and the trained surrogate model. Section 4.2 on hindcast skill is the most actionable for downstream users. The discussion acknowledges that intensity scaling under warmer climates remains uncertain.`;
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
        <div style={{
          maxHeight: 140, overflowY: 'auto',
          background: 'var(--bg-subtle)', border: '1px solid var(--border)',
          borderRadius: 8, padding: '12px 14px',
          fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg2)', lineHeight: 1.55,
        }}>
          {abstract}
        </div>
      </div>
      <div>
        <FieldLabel>AI overview</FieldLabel>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg2)', lineHeight: 1.6 }}>
          {more ? overview : overview.slice(0, 600) + '…'}
          <button onClick={() => setMore(m => !m)} style={{
            marginLeft: 6, background: 'transparent', border: 'none', cursor: 'pointer',
            fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500, color: '#0fa76e', padding: 0,
          }}>
            {more ? 'Show less' : 'Show more'}
          </button>
        </div>
      </div>
      <a href="#" style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '6px 14px', borderRadius: 9999, background: '#18E299',
        color: '#0d0d0d', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600,
        textDecoration: 'none',
      }}>
        <ExternalLink size={12} strokeWidth={1.5} /> Open on arXiv
      </a>
    </div>
  );
}

function PerspectiveSection({ title, color, body }: { title: string; color: string; body: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
      <button onClick={() => setOpen(o => !o)} style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 8,
        padding: '10px 14px', background: 'transparent', border: 'none',
        cursor: 'pointer', fontFamily: 'var(--sans)', fontSize: 13,
        fontWeight: 500, color: 'var(--fg1)', textAlign: 'left',
      }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
        {title}
        <span style={{ marginLeft: 'auto', color: 'var(--fg4)', display: 'flex' }}>
          {open ? <ChevronDown size={14} strokeWidth={2} /> : <ChevronRight size={14} strokeWidth={2} />}
        </span>
      </button>
      {open && (
        <div style={{
          padding: '0 14px 12px', fontFamily: 'var(--sans)', fontSize: 12.5,
          color: 'var(--fg2)', lineHeight: 1.6, borderTop: '1px solid var(--border)',
        }}>
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
        <span style={{ color: '#0fa76e', display: 'flex' }}><CheckCircle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Notebook updated</span>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Chip color="#0fa76e">18 sources added</Chip>
        <Chip color="#C37D0D">2 failed</Chip>
        <Chip color="#3772cf">5 from NLM web</Chip>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          padding: '3px 10px', borderRadius: 9999,
          background: 'rgba(24,226,153,0.15)', color: '#0fa76e',
          fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
          letterSpacing: '0.5px', textTransform: 'uppercase',
        }}>
          <CheckCircle size={11} strokeWidth={1.5} /> Quality gate · clean
        </span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)' }}>
          0 contradictions · 1 gap noted
        </span>
      </div>
      <div>
        <FieldLabel>Perspectives</FieldLabel>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <PerspectiveSection title="Practitioner" color="#3772cf"
            body="Section 4.2 hindcast skill is directly usable; you can replace the prior Lin & Emanuel (2019) module with this one and expect 12–18% improvement." />
          <PerspectiveSection title="Skeptic" color="#C37D0D"
            body="The validation set leans on three named storms. Generalization to compound events (rain + surge) is unclear." />
          <PerspectiveSection title="Beginner" color="#0fa76e"
            body="Read Section 1 and the figures in Section 5 first. Skip the Bayesian downscaling derivation unless you specifically need the math." />
        </div>
      </div>
      <div style={{
        background: 'var(--amber-bg)', borderLeft: '3px solid var(--amber-border)',
        borderRadius: '4px 8px 8px 4px', padding: '12px 14px',
        display: 'flex', flexDirection: 'column', gap: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, color: 'var(--amber-text)', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600 }}>
          <AlertTriangle size={14} strokeWidth={2} /> Save this notebook ID
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--amber-text)', lineHeight: 1.5 }}>
          A new notebook was created. Run this once to make it the default:
        </div>
        <CodeBlock>{'docent studio config-set --key notebooklm_notebook_id --value nb_4f2c'}</CodeBlock>
      </div>
    </div>
  );
}

function ResultConfigShow() {
  const rows = [
    ['output_dir', '~/docent/runs'],
    ['studio_backend', 'feynman'],
    ['notebooklm_notebook_id', 'nb_4f2c'],
    ['tavily_api_key', 'tvly...kQ2m'],
    ['alphaxiv_api_key', '(not set)'],
    ['groq_api_key', '(not set)'],
    ['gemini_api_key', 'AIza...4Aj1'],
    ['feynman_timeout', '900'],
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>
        Configuration ({rows.length} keys)
      </div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
        {rows.map(([k, v], i) => {
          const unset = v === '(not set)';
          return (
            <div key={k} style={{
              display: 'grid', gridTemplateColumns: 'minmax(180px, 0.4fr) 1fr',
              gap: 14, padding: '9px 14px',
              borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none',
              background: i % 2 === 0 ? 'transparent' : 'var(--bg-subtle)',
              alignItems: 'center',
            }}>
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
        <span style={{ color: '#0fa76e', display: 'flex' }}><CheckCircle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Key saved</span>
      </div>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.6 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--fg1)' }}>{cfgKey || 'key'}</span>
        {' was written to:'}
      </div>
      <CodeBlock>{'~/.docent/config.toml'}</CodeBlock>
    </div>
  );
}

// ── Output panel ──────────────────────────────────────────────────────────────

function OutputEmpty() {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24,
    }}>
      <div style={{
        width: 56, height: 56, borderRadius: 14,
        background: 'rgba(24,226,153,0.11)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#0fa76e',
      }}>
        <FlaskConical size={28} strokeWidth={1.5} />
      </div>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 15, fontWeight: 600, color: 'var(--fg1)' }}>
        Run a research action
      </div>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)', textAlign: 'center', maxWidth: 320 }}>
        Select an action on the left and fill in the form to get started.
      </div>
    </div>
  );
}

function OutputPanel({ action, state, status, logs, onStop, onReset }: {
  action: ActionMeta; state: FormState; status: Status;
  logs: LogEntry[]; onStop: () => void; onReset: () => void;
}) {
  const logRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs.length]);

  const isRunning = status === 'running';
  const isResult = status === 'success' || status === 'failure';
  const isEmpty = status === 'idle';

  const breadcrumb =
    state.topic || state.query || state.artifact ||
    (state.artifactA && state.artifactB ? `${state.artifactA} vs ${state.artifactB}` : '') ||
    state.arxivId || state.cfgKey || '';

  function renderResult() {
    if (status === 'failure') return <ResultFailure />;
    switch (action.id) {
      case 'search':
      case 'scholarly':  return <ResultSearch query={state.query} />;
      case 'getpaper':   return <ResultGetPaper />;
      case 'notebook':   return <ResultNotebook />;
      case 'cfgshow':    return <ResultConfigShow />;
      case 'cfgset':     return <ResultConfigSet cfgKey={state.cfgKey} />;
      default:           return <ResultResearchSuccess />;
    }
  }

  return (
    <section style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg)', overflow: 'hidden' }}>
      {/* Header */}
      {!isEmpty && (
        <div style={{
          flexShrink: 0, padding: '14px 24px',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            {isRunning && (
              <span style={{
                width: 8, height: 8, borderRadius: '50%', background: '#18E299', flexShrink: 0,
                animation: 'logo-dot-blink 1.2s step-end infinite',
              }} />
            )}
            <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', whiteSpace: 'nowrap' }}>
              {action.label}
            </span>
            {breadcrumb && (
              <>
                <span style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--gray200)' }}>·</span>
                <span style={{
                  fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--fg3)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0,
                }}>
                  {breadcrumb}
                </span>
              </>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {isRunning && (
              <GhostBtn icon={<Square size={12} strokeWidth={2} />} onClick={onStop} danger>Stop</GhostBtn>
            )}
            {isResult && <GhostBtn onClick={onReset}>Clear</GhostBtn>}
          </div>
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {isEmpty && <OutputEmpty />}

        {(isRunning || isResult) && logs.length > 0 && (
          <div ref={logRef} style={{
            padding: '14px 22px',
            borderBottom: isResult ? '1px solid var(--border)' : 'none',
            maxHeight: isResult ? 260 : undefined,
            overflowY: isResult ? 'auto' : 'visible',
          }}>
            <div style={{
              fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500, color: 'var(--fg4)',
              letterSpacing: '0.7px', textTransform: 'uppercase', marginBottom: 8, paddingLeft: 2,
            }}>
              Activity log
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {logs.map((l, i) => (
                <LogLine key={i} phase={l.phase} text={l.text} live={isRunning && i === logs.length - 1} />
              ))}
            </div>
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

// ── Page ──────────────────────────────────────────────────────────────────────

const DEFAULT_FORM: FormState = {
  topic: '', backend: 'Free', dest: 'Local', guides: [],
  artifact: '', artifactA: '', artifactB: '',
  query: '', maxResults: 10, arxivId: '',
  outPath: '', srcPath: '', maxSources: 20,
  nlm: true, gate: true, persp: true,
  cfgKey: '', cfgVal: '',
};

export default function StudioPage() {
  const { dark, toggleDark } = useDarkMode();
  const [actionId, setActionId] = useState<ActionId>('deep');
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [status, setStatus] = useState<Status>('idle');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [gating, setGating] = useState(false);
  const runRef = useRef<{ timer: ReturnType<typeof setTimeout> | null; idx: number }>({ timer: null, idx: 0 });

  const set = useCallback((k: keyof FormState, v: unknown) => {
    setForm(s => ({ ...s, [k]: v }));
  }, []);

  function stopRun() {
    if (runRef.current.timer) { clearTimeout(runRef.current.timer); runRef.current.timer = null; }
  }

  function startRun() {
    stopRun();
    const script = scriptFor(actionId);
    setLogs([]);
    setStatus('running');
    runRef.current.idx = 0;
    const tick = () => {
      const i = runRef.current.idx;
      if (i >= script.length) { setStatus('success'); runRef.current.timer = null; return; }
      setLogs(prev => [...prev, script[i]]);
      runRef.current.idx = i + 1;
      runRef.current.timer = setTimeout(tick, 650 + Math.random() * 200);
    };
    tick();
  }

  function handleRun() { startRun(); }
  function handleStop() { stopRun(); setStatus('success'); }
  function handleReset() { stopRun(); setStatus('idle'); setLogs([]); }

  useEffect(() => () => stopRun(), []);

  const action = findAction(actionId);

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="studio" queueCount={0} dark={dark} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner dark={dark} onToggleDark={toggleDark} dotState="idle" />
        <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
          <LeftColumn
            actionId={actionId} setActionId={setActionId}
            state={form} set={set}
            onRun={handleRun}
            gating={gating} setGating={setGating}
          />
          <OutputPanel
            action={action} state={form}
            status={status} logs={logs}
            onStop={handleStop} onReset={handleReset}
          />
        </div>
      </div>
    </div>
  );
}
