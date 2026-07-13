'use client';

// Generic Studio form primitives — extracted from app/studio/_form.tsx in the
// v2.3 monolith split. Purely presentational; no studio state.

import { useState } from 'react';
import { CheckCircle, Copy } from 'lucide-react';

export const RED        = '#c64545';
export const INDIGO     = '#6366f1';
export const INDIGO_DIM = '#a8b0f7';
export const AMBER_HDR  = '#F59E0B';
export const BLUE_HDR   = '#5db8a6';

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
        border: `1px solid ${active ? 'var(--brand)' : 'var(--border-md)'}`,
        background: active ? 'var(--brand-light)' : (hov ? 'var(--gray100)' : 'transparent'),
        color: danger ? RED : (active ? 'var(--brand-deep)' : 'var(--fg2)'),
        fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
        cursor: 'pointer', transition: 'background 0.12s', whiteSpace: 'nowrap',
      }}
    >
      {icon && <span style={{ color: danger ? RED : (active ? 'var(--brand-deep)' : 'var(--fg4)'), display: 'flex' }}>{icon}</span>}
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
        border: active ? `1px solid ${'var(--brand)'}` : '1px solid var(--border-md)',
        background: active ? 'var(--brand)' : (hov && !disabled ? 'var(--gray100)' : 'transparent'),
        color: active ? 'var(--on-primary)' : (disabled ? 'var(--fg4)' : 'var(--fg2)'),
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
        border: `1px solid ${focus ? 'var(--brand)' : 'var(--border-md)'}`,
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
      background: checked ? 'var(--brand)' : 'var(--gray200)',
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
        style={{ position: 'absolute', top: small ? 4 : 6, right: small ? 4 : 6, width: small ? 22 : 24, height: small ? 22 : 24, borderRadius: 6, border: 'none', background: 'transparent', color: copied ? 'var(--brand-deep)' : 'var(--fg4)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
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
