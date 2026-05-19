'use client';

import { useState, useEffect, useRef } from 'react';
import {
  FlaskConical, Play, Square, AlertTriangle, CheckCircle,
  Copy, Plus, ChevronDown, File, X, Search,
  Clock, Bookmark, Trash, Upload, Sparkles, Layers, Pin,
} from 'lucide-react';
import {
  ACTIONS, ALL_ACTIONS, findAction, BACKENDS,
  commandFor, costEstimate, runLabel,
  type ActionId, type ActionMeta, type FormState, type Preset,
} from './_shared';

const BRAND      = '#18E299';
const BRAND_DEEP = '#0fa76e';
const RED        = '#D45656';
const INDIGO     = '#6366f1';
const INDIGO_DIM = '#a8b0f7';
const AMBER_HDR  = '#F59E0B';
const BLUE_HDR   = '#3B82F6';

// ── Primitives ─────────────────────────────────────────────────────────────────

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      minWidth: 18, height: 18, padding: '0 5px',
      background: 'var(--gray100)', border: '1px solid var(--border-md)',
      borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 10,
      color: 'var(--fg3)', fontWeight: 500,
    }}>{children}</span>
  );
}

export function PrimaryBtn({ icon, children, onClick, disabled, full, size = 'md' }: {
  icon?: React.ReactNode; children: React.ReactNode;
  onClick?: () => void; disabled?: boolean; full?: boolean; size?: 'sm' | 'md';
}) {
  const pad = size === 'sm' ? '6px 14px' : '9px 18px';
  const fs  = size === 'sm' ? 12.5 : 13;
  return (
    <button onClick={onClick} disabled={disabled} style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
      padding: pad, borderRadius: 9999,
      background: disabled ? INDIGO_DIM : INDIGO,
      color: '#fff', fontFamily: 'var(--sans)', fontSize: fs, fontWeight: 600,
      border: 'none', cursor: disabled ? 'not-allowed' : 'pointer',
      width: full ? '100%' : 'auto', opacity: disabled ? 0.65 : 1,
      transition: 'opacity 0.12s',
    }}>
      {icon}{children}
    </button>
  );
}

export function GhostBtn({ icon, children, onClick, size = 'md', danger, active }: {
  icon?: React.ReactNode; children?: React.ReactNode;
  onClick?: () => void; size?: 'sm' | 'md'; danger?: boolean; active?: boolean;
}) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: size === 'sm' ? '4px 10px' : '5px 12px', borderRadius: 9999,
        border: `1px solid ${active ? BRAND : 'var(--border-md)'}`,
        background: active ? BRAND + '1a' : (hov ? 'var(--gray100)' : 'transparent'),
        color: danger ? RED : (active ? BRAND_DEEP : 'var(--fg2)'),
        fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
        cursor: 'pointer', transition: 'background 0.12s', whiteSpace: 'nowrap',
      }}
    >
      {icon && <span style={{ color: danger ? RED : (active ? BRAND_DEEP : 'var(--fg4)'), display: 'flex' }}>{icon}</span>}
      {children}
    </button>
  );
}

export function PillToggle({ active, onClick, disabled, tooltip, children }: {
  active?: boolean; onClick?: () => void; disabled?: boolean; tooltip?: string; children: React.ReactNode;
}) {
  const [hov, setHov] = useState(false);
  return (
    <button onClick={disabled ? undefined : onClick}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      title={tooltip}
      style={{
        padding: '5px 12px', borderRadius: 9999,
        border: active ? `1px solid ${BRAND}` : '1px solid var(--border-md)',
        background: active ? BRAND : (hov && !disabled ? 'var(--gray100)' : 'transparent'),
        color: active ? '#0d0d0d' : (disabled ? 'var(--fg4)' : 'var(--fg2)'),
        fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
        cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.55 : 1,
        transition: 'all 0.12s', whiteSpace: 'nowrap',
      }}>{children}</button>
  );
}

export function Segmented({ value, onChange, options }: {
  value: string; onChange: (v: string) => void; options: string[];
}) {
  return (
    <div style={{ display: 'inline-flex', padding: 2, background: 'var(--gray100)', borderRadius: 9999, border: '1px solid var(--border)' }}>
      {options.map(opt => {
        const active = opt === value;
        return (
          <button key={opt} onClick={() => onChange(opt)} style={{
            padding: '4px 14px', borderRadius: 9999, border: 'none',
            background: active ? 'var(--bg)' : 'transparent',
            color: active ? 'var(--fg1)' : 'var(--fg3)',
            fontFamily: 'var(--sans)', fontSize: 12, fontWeight: active ? 500 : 400,
            cursor: 'pointer', transition: 'all 0.12s',
            boxShadow: active ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
            display: 'inline-flex', alignItems: 'center', gap: 5,
          }}>{opt}</button>
        );
      })}
    </div>
  );
}

export function StudioInput({ value, onChange, placeholder, mono, autoFocus }: {
  value: string; onChange: (v: string) => void;
  placeholder?: string; mono?: boolean; autoFocus?: boolean;
}) {
  const [focus, setFocus] = useState(false);
  return (
    <input type="text" value={value} onChange={e => onChange(e.target.value)}
      placeholder={placeholder} autoFocus={autoFocus}
      onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
      style={{
        width: '100%', padding: '8px 12px',
        border: `1px solid ${focus ? BRAND : 'var(--border-md)'}`,
        borderRadius: 8,
        fontFamily: mono ? 'var(--mono)' : 'var(--sans)',
        fontSize: 13, color: 'var(--fg1)', background: 'var(--bg)',
        outline: 'none', transition: 'border-color 0.15s',
      }} />
  );
}

export function FieldLabel({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <label style={{ display: 'block', marginBottom: 6, fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500, color: 'var(--fg3)' }}>
      {children}
      {hint && <span style={{ color: 'var(--fg4)', fontWeight: 400, marginLeft: 6 }}>{hint}</span>}
    </label>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return <div><FieldLabel hint={hint}>{label}</FieldLabel>{children}</div>;
}

export function Note({ tone = 'info', children, icon }: {
  tone?: 'info' | 'warn'; children: React.ReactNode; icon?: React.ReactNode;
}) {
  return (
    <div style={{
      fontFamily: 'var(--sans)', fontSize: 11.5, lineHeight: 1.5,
      color: tone === 'warn' ? 'var(--amber-text)' : 'var(--fg3)',
      padding: tone === 'warn' ? '7px 10px' : '4px 0',
      borderRadius: tone === 'warn' ? 6 : 0,
      background: tone === 'warn' ? 'var(--amber-bg)' : 'transparent',
      borderLeft: tone === 'warn' ? '2px solid var(--amber-border)' : 'none',
      marginTop: 8, display: 'flex', alignItems: 'center', gap: 6,
    }}>
      {icon && <span style={{ display: 'flex' }}>{icon}</span>}
      <span>{children}</span>
    </div>
  );
}

export function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!checked)} style={{
      width: 30, height: 18, borderRadius: 9999, border: 'none',
      background: checked ? BRAND : 'var(--gray200)',
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

export function Stepper({ value, onChange, min = 1, max = 99 }: {
  value: number; onChange: (v: number) => void; min?: number; max?: number;
}) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', border: '1px solid var(--border-md)', borderRadius: 8, overflow: 'hidden', background: 'var(--bg)' }}>
      <button onClick={() => onChange(Math.max(min, value - 1))} style={{ width: 28, height: 30, border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--fg3)', fontSize: 16, fontFamily: 'var(--sans)' }}>−</button>
      <div style={{ width: 36, textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--fg1)', fontWeight: 500, borderLeft: '1px solid var(--border)', borderRight: '1px solid var(--border)', padding: '7px 0' }}>{value}</div>
      <button onClick={() => onChange(Math.min(max, value + 1))} style={{ width: 28, height: 30, border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--fg3)', fontSize: 14, fontFamily: 'var(--sans)' }}>+</button>
    </div>
  );
}

export function CodeBlock({ children, small }: { children: string; small?: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <div style={{
      position: 'relative', background: 'var(--code-bg)',
      border: '1px solid var(--code-border)', borderRadius: 8,
      padding: small ? '7px 32px 7px 10px' : '10px 36px 10px 12px',
      fontFamily: 'var(--mono)', fontSize: small ? 11 : 11.5, color: 'var(--fg2)',
      lineHeight: 1.55, letterSpacing: '0.2px', wordBreak: 'break-all', whiteSpace: 'pre-wrap',
    }}>
      {children}
      <button onClick={() => { navigator.clipboard?.writeText(children); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
        title="Copy"
        style={{ position: 'absolute', top: small ? 4 : 6, right: small ? 4 : 6, width: small ? 22 : 24, height: small ? 22 : 24, borderRadius: 6, border: 'none', background: 'transparent', color: copied ? BRAND_DEEP : 'var(--fg4)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {copied ? <CheckCircle size={12} strokeWidth={1.5} /> : <Copy size={12} strokeWidth={1.6} />}
      </button>
    </div>
  );
}

export function Chip({ color, children, icon }: { color?: string; children: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '4px 10px', borderRadius: 9999,
      background: color ? color + '1f' : 'var(--gray100)',
      color: color ?? 'var(--fg2)',
      fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
      letterSpacing: '0.4px', textTransform: 'uppercase',
    }}>
      {icon && <span style={{ display: 'flex' }}>{icon}</span>}
      {children}
    </span>
  );
}

// ── Action list ────────────────────────────────────────────────────────────────

function ActionRow({ id, label, desc, isActive, isPreset, onClick, onDelete }: {
  id: string; label: string; desc?: string; isActive: boolean; isPreset?: boolean;
  onClick: () => void; onDelete?: (e: React.MouseEvent) => void;
}) {
  return (
    <div className="action-row" title={desc} style={{ position: 'relative', display: 'flex', alignItems: 'center', borderRadius: 6, background: isActive ? BRAND + '1f' : 'transparent', transition: 'background 0.1s' }}>
      <button onClick={onClick} style={{
        flex: 1, textAlign: 'left', padding: '6px 10px', borderRadius: 6, border: 'none',
        background: 'transparent', cursor: 'pointer', fontFamily: 'var(--sans)', fontSize: 12.5,
        fontWeight: isActive ? 500 : 400, color: isActive ? BRAND_DEEP : 'var(--fg2)',
        display: 'flex', alignItems: 'center', gap: 0,
      }}>
        <span style={{ width: isActive ? 3 : 4, height: isActive ? 14 : 4, borderRadius: isActive ? 2 : '50%', background: isActive ? BRAND_DEEP : 'transparent', marginRight: 9, flexShrink: 0, transition: 'all 0.15s' }} />
        {isPreset && <span style={{ color: isActive ? BRAND_DEEP : 'var(--fg4)', display: 'flex', marginRight: 6 }}><Bookmark size={13} strokeWidth={1.5} /></span>}
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
      </button>
      {isPreset && onDelete && (
        <button onClick={onDelete} title="Remove preset" className="row-action"
          style={{ width: 22, height: 22, borderRadius: 5, border: 'none', background: 'transparent', color: 'var(--fg4)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: 6, opacity: 0, transition: 'opacity 0.12s' }}>
          <Trash size={12} strokeWidth={1.5} />
        </button>
      )}
    </div>
  );
}

const GROUP_ACCENT: Record<string, string> = {
  research:  AMBER_HDR,
  utilities: BLUE_HDR,
  config:    'var(--fg4)',
};

function ActionList({ activeId, onSelect, presets, onDeletePreset, onSelectPreset }: {
  activeId: string;
  onSelect: (id: ActionId) => void;
  presets: Preset[];
  onDeletePreset: (id: string) => void;
  onSelectPreset: (p: Preset) => void;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {presets.length > 0 && (
        <div>
          <div style={{ padding: '0 4px 6px', display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500, color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase' }}>
            <Pin size={13} strokeWidth={1.5} /> Presets
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {presets.map(p => (
              <ActionRow key={p.id} id={p.id} label={p.name}
                isActive={activeId === 'preset:' + p.id} isPreset
                onClick={() => onSelectPreset(p)}
                onDelete={e => { e.stopPropagation(); onDeletePreset(p.id); }} />
            ))}
          </div>
        </div>
      )}
      {ACTIONS.map(group => {
        const accent = GROUP_ACCENT[group.key] ?? 'var(--fg4)';
        return (
          <div key={group.key}>
            <div style={{ padding: '0 4px 6px', display: 'flex', alignItems: 'center', gap: 5, fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500, color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase' }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: accent, flexShrink: 0 }} />
              {group.label}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {group.items.map(item => (
                <ActionRow key={item.id} id={item.id} label={item.label} desc={item.desc}
                  isActive={item.id === activeId}
                  onClick={() => onSelect(item.id as ActionId)} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Backend selector ───────────────────────────────────────────────────────────

function BackendSelector({ value, onChange, freeDisabled }: {
  value: string; onChange: (v: string) => void; freeDisabled?: boolean;
}) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
      {BACKENDS.map(b => (
        <PillToggle key={b} active={value === b} onClick={() => onChange(b)}
          disabled={freeDisabled && b === 'Free'}
          tooltip={freeDisabled && b === 'Free' ? 'Not available for this action' : undefined}>
          {b}
        </PillToggle>
      ))}
    </div>
  );
}

// ── Guide files ────────────────────────────────────────────────────────────────

function GuideFiles({ files, setFiles }: { files: string[]; setFiles: (f: string[]) => void }) {
  const [open, setOpen] = useState(files.length > 0);
  const [draft, setDraft] = useState('');
  const [picking, setPicking] = useState(false);

  async function handleBrowse() {
    setPicking(true);
    try {
      const r = await fetch('/api/fs/pick', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extensions: ['.pdf', '.md', '.txt', '.docx'], title: 'Select guide files' }),
      });
      const j = await r.json() as { paths?: string[]; error?: string };
      if (j.paths && j.paths.length > 0) {
        const newPaths = j.paths.filter(p => !files.includes(p));
        setFiles([...files, ...newPaths]);
        setOpen(true);
      }
    } catch { /* ignore */ } finally {
      setPicking(false);
    }
  }

  return (
    <div>
      <button onClick={() => setOpen(o => !o)} title="PDFs or text files used to give context or steer the research. The AI reads these alongside the topic." style={{ display: 'flex', alignItems: 'center', gap: 5, background: 'transparent', border: 'none', cursor: 'pointer', padding: '2px 0', color: 'var(--fg3)', fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500 }}>
        <span style={{ display: 'flex', transition: 'transform 0.12s', transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}>
          <ChevronDown size={14} strokeWidth={2} />
        </span>
        Add guide files
        <span style={{ color: 'var(--fg4)', fontWeight: 400 }}> (optional · PDFs / docs that steer the research)</span>
        {files.length > 0 && (
          <span style={{ marginLeft: 4, fontFamily: 'var(--mono)', fontSize: 10, color: BRAND_DEEP, background: BRAND + '1f', padding: '1px 6px', borderRadius: 9999 }}>{files.length}</span>
        )}
      </button>
      {open && (
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', gap: 6 }}>
            <div style={{ flex: 1 }}><StudioInput value={draft} onChange={setDraft} placeholder="path/to/guide.pdf" mono /></div>
            <button onClick={() => { if (draft.trim()) { setFiles([...files, draft.trim()]); setDraft(''); } }}
              style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-md)', background: 'var(--gray100)', color: 'var(--fg2)', fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <Plus size={14} strokeWidth={2} /> Add
            </button>
            <button onClick={handleBrowse} disabled={picking}
              title="Open file picker to browse your machine"
              style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-md)', background: 'var(--gray100)', color: 'var(--fg2)', fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500, cursor: picking ? 'wait' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4, opacity: picking ? 0.6 : 1 }}>
              <Upload size={13} strokeWidth={1.6} /> Browse
            </button>
          </div>
          {files.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {files.map((f, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 8px', background: 'var(--gray100)', borderRadius: 6, fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)' }}>
                  <span style={{ color: 'var(--fg4)', display: 'flex' }}><File size={13} strokeWidth={1.5} /></span>
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f}</span>
                  <button onClick={() => setFiles(files.filter((_, j) => j !== i))} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--fg4)', display: 'flex', padding: 2 }}>
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

// ── Forms ──────────────────────────────────────────────────────────────────────

type SetFn = (k: keyof FormState, v: unknown) => void;

const BACKEND_NOTES: Record<string, string> = {
  Free:       'Tavily search + source aggregation. No API key, no AI synthesis.',
  Feynman:    'Autonomous deep-research agent. Runs 3–30 min.',
  Docent:     'Native 6-stage synthesis pipeline. Requires OpenCode server.',
  Groq:       'Fast LLM synthesis via Groq. Requires groq_api_key.',
  Gemini:     'Google Gemini synthesis. Requires gemini_api_key.',
  OpenRouter: 'Synthesis via OpenRouter. Supports many models.',
  Anthropic:  'Claude synthesis. Requires anthropic_api_key.',
  OpenAI:     'GPT-4o synthesis. Requires openai_api_key.',
  Ollama:     'Local model inference. Ollama server must be running.',
  'LM Studio': 'Local inference via LM Studio server.',
};

const DEST_NOTES: Record<string, string> = {
  Local:      'Saved to your configured docent research folder.',
  Notebook:   'Uploaded to NotebookLM after the run.',
  'Pipe →':   'Output fed directly into the next action\'s input — use to chain actions.',
};

function FormTopic({ state, set }: { state: FormState; set: SetFn }) {
  const backendNote = BACKEND_NOTES[state.backend] ?? 'Runs 3–30 min. May time out over MCP.';
  const destNote    = DEST_NOTES[state.dest] ?? '';
  return <>
    <Field label="Topic">
      <StudioInput value={state.topic} onChange={v => set('topic', v)} placeholder="e.g. storm surge inundation under climate change" />
    </Field>
    <Field label="Backend">
      <BackendSelector value={state.backend} onChange={v => set('backend', v)} />
      <Note icon={state.backend === 'Free' ? <Sparkles size={12} strokeWidth={1.4} /> : undefined}
        tone={state.backend !== 'Free' && state.backend !== 'Docent' ? undefined : undefined}>
        {backendNote}
      </Note>
    </Field>
    <Field label="Output destination">
      <Segmented value={state.dest} onChange={v => set('dest', v)} options={['Local', 'Notebook', 'Pipe →']} />
      {destNote && <Note>{destNote}</Note>}
    </Field>
    <GuideFiles files={state.guides} setFiles={v => set('guides', v)} />
  </>;
}

function FormArtifact({ state, set }: { state: FormState; set: SetFn }) {
  const backend = state.backend === 'Free' ? 'Anthropic' : state.backend;
  return <>
    <Field label="Artifact" hint="arXiv ID, PDF path, or URL">
      <StudioInput value={state.artifact} onChange={v => set('artifact', v)} placeholder="2401.12345 / paper.pdf / https://…" mono />
    </Field>
    <Field label="Backend">
      <BackendSelector value={backend} onChange={v => set('backend', v)} freeDisabled />
      <Note tone="warn">Runs 3–30 min. May time out over MCP.</Note>
    </Field>
    <GuideFiles files={state.guides} setFiles={v => set('guides', v)} />
  </>;
}

function FormCompare({ state, set }: { state: FormState; set: SetFn }) {
  const backend = state.backend === 'Free' ? 'Anthropic' : state.backend;
  return <>
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
  </>;
}

function FormSearch({ state, set }: { state: FormState; set: SetFn }) {
  return <>
    <Field label="Query">
      <StudioInput value={state.query} onChange={v => set('query', v)} placeholder="e.g. coastal flooding bayesian" />
    </Field>
    <Field label="Max results">
      <Stepper value={state.maxResults} onChange={v => set('maxResults', v)} min={1} max={100} />
    </Field>
  </>;
}

function FormGetPaper({ state, set }: { state: FormState; set: SetFn }) {
  return <Field label="arXiv ID or URL">
    <StudioInput value={state.arxivId} onChange={v => set('arxivId', v)} placeholder="e.g. 2401.12345 or arxiv.org/abs/…" mono />
  </Field>;
}

function FormNotebook({ state, set }: { state: FormState; set: SetFn }) {
  return <>
    <Field label="Output file path" hint="(optional)">
      <StudioInput value={state.outPath} onChange={v => set('outPath', v)} placeholder="Auto-detect most recent" mono />
    </Field>
    <Field label="Sources file path" hint="(optional)">
      <StudioInput value={state.srcPath} onChange={v => set('srcPath', v)} placeholder="sources.json" mono />
    </Field>
    <Field label="Max sources">
      <Stepper value={state.maxSources} onChange={v => set('maxSources', v)} min={1} max={200} />
    </Field>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '10px 12px', background: 'var(--gray100)', borderRadius: 8 }}>
      {([['nlm', 'NLM research'], ['gate', 'Quality gate'], ['persp', 'Perspectives']] as const).map(([k, lbl]) => (
        <div key={k} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)' }}>{lbl}</span>
          <Toggle checked={state[k]} onChange={v => set(k, v)} />
        </div>
      ))}
    </div>
  </>;
}

function FormCfgShow() {
  return <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)', lineHeight: 1.5 }}>Display current configuration values. API keys are masked.</div>;
}

const CFG_KEY_OPTIONS: { key: string; label: string }[] = [
  { key: 'tavily_api_key',          label: 'Tavily API key' },
  { key: 'semantic_scholar_api_key', label: 'Semantic Scholar API key' },
  { key: 'alphaxiv_api_key',        label: 'AlphaXiv API key' },
  { key: 'groq_api_key',            label: 'Groq API key' },
  { key: 'groq_model',              label: 'Groq model' },
  { key: 'gemini_api_key',          label: 'Gemini API key' },
  { key: 'gemini_model',            label: 'Gemini model' },
  { key: 'openrouter_api_key',      label: 'OpenRouter API key' },
  { key: 'openrouter_model',        label: 'OpenRouter model' },
  { key: 'mistral_api_key',         label: 'Mistral API key' },
  { key: 'mistral_model',           label: 'Mistral model' },
  { key: 'cerebras_api_key',        label: 'Cerebras API key' },
  { key: 'cerebras_model',          label: 'Cerebras model' },
  { key: 'feynman_model',           label: 'Feynman model override' },
  { key: 'feynman_timeout',         label: 'Feynman timeout (s)' },
  { key: 'output_dir',              label: 'Research output directory' },
  { key: 'studio_backend',          label: 'Default backend' },
  { key: 'notebooklm_notebook_id',  label: 'NotebookLM notebook ID' },
  { key: 'notebooklm_source_limit', label: 'NotebookLM source limit' },
  { key: 'tavily_research_timeout', label: 'Tavily research timeout (s)' },
  { key: 'ollama_model',            label: 'Ollama model' },
  { key: 'ollama_base_url',         label: 'Ollama base URL' },
  { key: 'lm_studio_model',         label: 'LM Studio model' },
  { key: 'lm_studio_base_url',      label: 'LM Studio base URL' },
];

function FormCfgSet({ state, set }: { state: FormState; set: SetFn }) {
  const [focus, setFocus] = useState(false);
  return <>
    <Field label="Key">
      <select value={state.cfgKey} onChange={e => set('cfgKey', e.target.value)}
        onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
        style={{
          width: '100%', padding: '8px 12px',
          border: `1px solid ${focus ? INDIGO : 'var(--border-md)'}`,
          borderRadius: 8, fontFamily: 'var(--mono)', fontSize: 12.5,
          color: 'var(--fg1)', background: 'var(--bg)', outline: 'none',
          transition: 'border-color 0.15s', cursor: 'pointer',
        }}>
        <option value="">— select a key —</option>
        {CFG_KEY_OPTIONS.map(o => (
          <option key={o.key} value={o.key}>{o.label} ({o.key})</option>
        ))}
      </select>
    </Field>
    <Field label="Value">
      <StudioInput value={state.cfgVal} onChange={v => set('cfgVal', v)} placeholder="Paste value here…" mono />
    </Field>
  </>;
}

const FORM_MAP: Record<string, React.ComponentType<{ state: FormState; set: SetFn }>> = {
  topic: FormTopic, artifact: FormArtifact, compare: FormCompare,
  search: FormSearch, getpaper: FormGetPaper, notebook: FormNotebook,
  cfgshow: FormCfgShow, cfgset: FormCfgSet,
};

// ── Command preview + cost estimate ───────────────────────────────────────────

function CommandPreview({ actionId, state }: { actionId: ActionId; state: FormState }) {
  const cmd = commandFor(actionId, state);
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <FieldLabel>Equivalent CLI</FieldLabel>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>copy & paste</span>
      </div>
      <CodeBlock small>{cmd}</CodeBlock>
    </div>
  );
}

function CostEstimate({ actionId, backend }: { actionId: ActionId; backend: string }) {
  const est = costEstimate(actionId, backend);
  if (!est) return null;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', background: 'var(--gray100)', borderRadius: 8, border: '1px solid var(--border)' }}>
      <span style={{ display: 'flex', color: est.free ? BRAND_DEEP : 'var(--fg3)' }}><Clock size={13} strokeWidth={1.5} /></span>
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, gap: 1 }}>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg4)', fontWeight: 500, letterSpacing: '0.3px', textTransform: 'uppercase' }}>Estimate</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--fg1)', fontWeight: 600, letterSpacing: '0.3px' }}>{est.cost} · {est.time}</span>
      </div>
      <span style={{ fontFamily: 'var(--sans)', fontSize: 10.5, color: 'var(--fg4)' }}>{est.free ? 'no API key' : backend}</span>
    </div>
  );
}

// ── Free-tier gate ─────────────────────────────────────────────────────────────

function FreeTierGate({ onCancel, onProceed }: { onCancel: () => void; onProceed: () => void }) {
  const proceedRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', onKey);
    proceedRef.current?.focus();
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel]);
  return (
    <div role="alertdialog" aria-modal="true" style={{ background: 'var(--amber-bg-strong)', borderLeft: '3px solid var(--amber-border)', borderRadius: '4px 8px 8px 4px', padding: '14px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8, color: 'var(--amber-text)', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600 }}>
        <AlertTriangle size={14} strokeWidth={2} /> Free tier — confirm before running
      </div>
      <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 12px', display: 'flex', flexDirection: 'column', gap: 4 }}>
        {['No AI synthesis — sources only', 'Quality depends on search coverage', 'Tavily optional (1k/month free); DuckDuckGo fallback', 'This is a starting point, not a finished report'].map(t => (
          <li key={t} style={{ display: 'flex', gap: 8, fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--amber-text)', lineHeight: 1.55 }}>
            <span style={{ marginTop: 7, width: 3, height: 3, borderRadius: '50%', background: 'var(--amber-text)', flexShrink: 0 }} />
            <span>{t}</span>
          </li>
        ))}
      </ul>
      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
        <GhostBtn size="sm" onClick={onCancel}>Cancel</GhostBtn>
        <button ref={proceedRef} onClick={onProceed} style={{ padding: '5px 14px', borderRadius: 9999, background: BRAND, color: '#0d0d0d', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
          Yes, proceed
        </button>
      </div>
    </div>
  );
}

// ── Left column ────────────────────────────────────────────────────────────────

export function LeftColumn({ actionId, setActionId, state, set, onRun, gating, setGating,
  presets, onDeletePreset, onSelectPreset, onOpenCmdK, isRunning, onStop, activePresetId }: {
  actionId: ActionId; setActionId: (id: ActionId) => void;
  state: FormState; set: SetFn;
  onRun: () => void; gating: boolean; setGating: (v: boolean) => void;
  presets: Preset[]; onDeletePreset: (id: string) => void; onSelectPreset: (p: Preset) => void;
  onOpenCmdK: () => void; isRunning: boolean; onStop: () => void;
  activePresetId?: string | null;
}) {
  const action = findAction(actionId);
  const Form = FORM_MAP[action.form];
  const [dragHover, setDragHover] = useState(false);
  const supportsGuides = ['topic', 'artifact', 'compare'].includes(action.form);

  const runDisabled = (() => {
    if (action.form === 'topic')    return !state.topic.trim();
    if (action.form === 'artifact') return !state.artifact.trim();
    if (action.form === 'compare')  return !state.artifactA.trim() || !state.artifactB.trim();
    if (action.form === 'search')   return !state.query.trim();
    if (action.form === 'getpaper') return !state.arxivId.trim();
    return false;
  })();

  const runDisabledTitle = (() => {
    if (action.form === 'topic' && !state.topic.trim())         return 'Enter a topic to run';
    if (action.form === 'artifact' && !state.artifact.trim())   return 'Enter an artifact to run';
    if (action.form === 'compare' && (!state.artifactA.trim() || !state.artifactB.trim())) return 'Enter both artifacts to run';
    if (action.form === 'search' && !state.query.trim())        return 'Enter a query to run';
    if (action.form === 'getpaper' && !state.arxivId.trim())    return 'Enter an arXiv ID to run';
    return undefined;
  })();

  function handleRunClick() {
    if (runDisabled) return;
    const usesFree = action.form === 'topic' && state.backend === 'Free';
    if (usesFree) setGating(true); else onRun();
  }
  function onDragOver(e: React.DragEvent) {
    if (!supportsGuides) return;
    e.preventDefault();
    if (e.dataTransfer?.types?.includes('Files')) setDragHover(true);
  }
  function onDragLeave(e: React.DragEvent) {
    if (e.relatedTarget && (e.currentTarget as HTMLElement).contains(e.relatedTarget as Node)) return;
    setDragHover(false);
  }
  function onDrop(e: React.DragEvent) {
    if (!supportsGuides) return;
    e.preventDefault(); setDragHover(false);
    const files = Array.from(e.dataTransfer?.files ?? []);
    if (files.length) set('guides', [...(state.guides ?? []), ...files.map(f => f.name)]);
  }

  const listActiveId = activePresetId ? ('preset:' + activePresetId) : actionId;

  return (
    <aside onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
      style={{ width: 380, flexShrink: 0, height: '100%', borderRight: '1px solid var(--border)', background: 'transparent', display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>

      <div style={{ padding: '18px 22px 12px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
        <div style={{ position: 'relative' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 3 }}>
            <span style={{ color: BRAND_DEEP, display: 'flex' }}><FlaskConical size={16} strokeWidth={1.5} /></span>
            <h1 style={{ fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 600, color: 'var(--fg1)', letterSpacing: '-0.3px', margin: 0 }}>Studio</h1>
          </div>
          <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', margin: 0 }}>Run AI research actions</p>
        </div>
        <button onClick={onOpenCmdK} title="Quick action (Ctrl+K)"
          style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5, padding: '5px 10px', borderRadius: 7, border: '1px solid var(--border-md)', background: 'var(--gray100)', cursor: 'pointer', color: 'var(--fg3)' }}>
          <Search size={14} strokeWidth={1.5} />
          <span style={{ display: 'inline-flex', gap: 2 }}><Kbd>Ctrl</Kbd><Kbd>K</Kbd></span>
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 22px 0' }}>
        <ActionList activeId={listActiveId} onSelect={setActionId}
          presets={presets} onDeletePreset={onDeletePreset} onSelectPreset={onSelectPreset} />
        <div style={{ height: 1, background: 'var(--border)', margin: '18px 0 16px' }} />
        <div style={{ marginBottom: 12, fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500, color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>{action.label}</span>
          <span style={{ flex: 1, height: 1, background: 'var(--border)' }} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingBottom: 14 }}>
          <Form state={state} set={set} />
          {!['cfgshow', 'cfgset'].includes(action.id) && (
            <CommandPreview actionId={actionId} state={state} />
          )}
        </div>
      </div>

      <div style={{ padding: '12px 22px 18px', borderTop: '1px solid var(--border)', background: 'transparent', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 10, boxShadow: '0 -4px 16px rgba(0,0,0,0.04)' }}>
        {!gating && !isRunning && <CostEstimate actionId={actionId} backend={state.backend} />}
        {gating ? (
          <FreeTierGate onCancel={() => setGating(false)} onProceed={() => { setGating(false); onRun(); }} />
        ) : isRunning ? (
          <button onClick={onStop} style={{ width: '100%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7, padding: '9px 18px', borderRadius: 9999, background: 'transparent', border: '1px solid var(--border-md)', color: RED, fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
            <Square size={12} strokeWidth={2} /> Stop run
          </button>
        ) : (
          <span title={runDisabledTitle} style={{ display: 'block' }}>
            <PrimaryBtn full icon={<Play size={13} strokeWidth={2} />} onClick={handleRunClick} disabled={runDisabled}>
              {runLabel(action)}
              <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 3, opacity: 0.7 }}>
                <Kbd>Ctrl</Kbd><Kbd>↵</Kbd>
              </span>
            </PrimaryBtn>
          </span>
        )}
      </div>

      {dragHover && supportsGuides && (
        <div style={{ position: 'absolute', inset: 0, background: BRAND + '22', border: `2px dashed ${BRAND_DEEP}`, zIndex: 10, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, pointerEvents: 'none' }}>
          <div style={{ width: 48, height: 48, borderRadius: 12, background: BRAND + '33', display: 'flex', alignItems: 'center', justifyContent: 'center', color: BRAND_DEEP }}>
            <Upload size={13} strokeWidth={1.5} />
          </div>
          <div style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: BRAND_DEEP }}>Drop to add as guide file</div>
        </div>
      )}
    </aside>
  );
}

// ── Cmd-K palette ──────────────────────────────────────────────────────────────

export function CmdKPalette({ onClose, onSelect, recents = [] }: {
  onClose: () => void; onSelect: (a: ActionMeta) => void; recents?: ActionId[];
}) {
  const [q, setQ] = useState('');
  const [idx, setIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const ql = q.toLowerCase();
  const allWithRecent: (ActionMeta & { _recent?: boolean })[] = recents.length
    ? [...recents.map(id => ({ ...findAction(id), _recent: true as const })), ...ALL_ACTIONS.filter(a => !recents.includes(a.id as ActionId))]
    : ALL_ACTIONS;
  const results: (ActionMeta & { _recent?: boolean })[] = ql
    ? ALL_ACTIONS.filter(a => a.label.toLowerCase().includes(ql) || a.group.toLowerCase().includes(ql) || (a.desc ?? '').toLowerCase().includes(ql))
    : allWithRecent;

  useEffect(() => { setIdx(0); }, [q]);

  useEffect(() => {
    inputRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowDown') { setIdx(i => Math.min(i + 1, results.length - 1)); e.preventDefault(); }
      else if (e.key === 'ArrowUp')   { setIdx(i => Math.max(i - 1, 0)); e.preventDefault(); }
      else if (e.key === 'Enter') { if (results[idx]) { onSelect(results[idx]); onClose(); } e.preventDefault(); }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'var(--overlay)', zIndex: 200, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: '12vh' }}>
      <div onClick={e => e.stopPropagation()} style={{ width: 560, maxHeight: '70vh', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 14, boxShadow: 'rgba(0,0,0,0.18) 0px 12px 36px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ color: 'var(--fg4)', display: 'flex' }}><Search size={14} strokeWidth={1.5} /></span>
          <input ref={inputRef} value={q} onChange={e => setQ(e.target.value)}
            placeholder="Search actions, or paste an arXiv ID…"
            style={{ flex: 1, padding: '4px 0', border: 'none', outline: 'none', fontFamily: 'var(--sans)', fontSize: 14, color: 'var(--fg1)', background: 'transparent' }} />
          <Kbd>esc</Kbd>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '6px 6px 8px' }}>
          {!q && recents.length > 0 && (
            <div style={{ padding: '8px 12px 6px', fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase' }}>Recent</div>
          )}
          {results.length === 0 ? (
            <div style={{ padding: '22px 16px', textAlign: 'center', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg4)' }}>No actions match &ldquo;{q}&rdquo;</div>
          ) : results.map((a, i) => {
            const isHov = i === idx;
            const Icon = a._recent ? null : a.group === 'Research' ? <Sparkles size={12} strokeWidth={1.4} /> : a.group === 'Utilities' ? <Search size={14} strokeWidth={1.5} /> : <Layers size={13} strokeWidth={1.5} />;
            return (
              <button key={a.id + String(i)} onClick={() => { onSelect(a); onClose(); }} onMouseEnter={() => setIdx(i)}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', borderRadius: 8, border: 'none', cursor: 'pointer', background: isHov ? BRAND + '1a' : 'transparent', textAlign: 'left' }}>
                <span style={{ display: 'flex', color: isHov ? BRAND_DEEP : 'var(--fg4)', flexShrink: 0 }}>{Icon}</span>
                <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
                  <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: isHov ? BRAND_DEEP : 'var(--fg1)' }}>{a.label}</span>
                  <span style={{ fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg4)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.desc}</span>
                </div>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase', flexShrink: 0 }}>{a.group}</span>
                {isHov && <Kbd>↵</Kbd>}
              </button>
            );
          })}
        </div>
        <div style={{ padding: '8px 14px', borderTop: '1px solid var(--border)', background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--fg4)', letterSpacing: '0.4px', textTransform: 'uppercase' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <Kbd>↑</Kbd><Kbd>↓</Kbd> navigate · <Kbd>↵</Kbd> select
          </span>
          <span>{results.length} actions</span>
        </div>
      </div>
    </div>
  );
}

// ── Preset-save modal ──────────────────────────────────────────────────────────

export function PresetSaveModal({ onClose, onSave, suggested = '' }: {
  onClose: () => void; onSave: (name: string) => void; suggested?: string;
}) {
  const [name, setName] = useState(suggested);
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'Enter' && name.trim()) { onSave(name.trim()); onClose(); }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'var(--overlay)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={e => e.stopPropagation()} style={{ width: 420, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 14, padding: '18px 20px', boxShadow: 'rgba(0,0,0,0.18) 0px 12px 36px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <span style={{ color: BRAND_DEEP, display: 'flex' }}><Bookmark size={13} strokeWidth={1.5} /></span>
          <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Save as preset</span>
        </div>
        <Field label="Preset name">
          <StudioInput autoFocus value={name} onChange={setName} placeholder="e.g. Weekly storm-surge lit scan" />
        </Field>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
          <GhostBtn size="sm" onClick={onClose}>Cancel</GhostBtn>
          <button onClick={() => { if (name.trim()) { onSave(name.trim()); onClose(); } }} disabled={!name.trim()}
            style={{ padding: '6px 14px', borderRadius: 9999, background: name.trim() ? BRAND : '#a8e8cf', color: '#0d0d0d', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 600, border: 'none', cursor: name.trim() ? 'pointer' : 'not-allowed' }}>
            Save preset
          </button>
        </div>
      </div>
    </div>
  );
}
