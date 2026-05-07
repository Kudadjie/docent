'use client';

import { useState, useEffect, useRef } from 'react';
import { BookOpen } from 'lucide-react';

export interface UserProfile {
  name: string;
  program: string;
  level: string;
}

const LEVELS = ['Undergraduate', 'Masters', 'PhD', 'Postdoc', 'Faculty', 'Other'];

interface Props {
  onComplete: (profile: UserProfile) => void;
}

export default function WelcomeModal({ onComplete }: Props) {
  const [name, setName]       = useState('');
  const [program, setProgram] = useState('');
  const [level, setLevel]     = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onComplete({ name: name.trim() || 'You', program: program.trim(), level });
  }

  function handleSkip() {
    onComplete({ name: '', program: '', level: '' });
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to Docent"
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
    >
      <div style={{
        background: 'var(--bg)',
        border: '1px solid var(--border-md)',
        borderRadius: 16,
        width: '100%', maxWidth: 420,
        boxShadow: '0 12px 48px rgba(0,0,0,0.24)',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '28px 28px 0',
          display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
        }}>
          <div style={{
            width: 44, height: 44, borderRadius: '50%',
            background: 'rgba(24,226,153,0.12)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 14,
          }}>
            <BookOpen size={20} strokeWidth={1.5} color="#0fa76e" />
          </div>
          <h2 style={{
            fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 700,
            color: 'var(--fg1)', margin: '0 0 6px', letterSpacing: '-0.3px',
          }}>
            Welcome to Docent
          </h2>
          <p style={{
            fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)',
            margin: 0, lineHeight: 1.5,
          }}>
            Tell us a bit about yourself to personalise your experience.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <FormField label="Your name">
            <input
              ref={inputRef}
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. John"
              style={inputStyle}
            />
          </FormField>

          <FormField label="Program or field of study">
            <input
              type="text"
              value={program}
              onChange={e => setProgram(e.target.value)}
              placeholder="e.g. Coastal Engineering"
              style={inputStyle}
            />
          </FormField>

          <FormField label="Level">
            <select
              value={level}
              onChange={e => setLevel(e.target.value)}
              style={inputStyle}
            >
              <option value="">Select…</option>
              {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </FormField>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
            <button
              type="submit"
              style={{
                fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600,
                color: '#fff', background: '#0fa76e',
                border: 'none', borderRadius: 9999,
                padding: '10px 20px', cursor: 'pointer', width: '100%',
              }}
            >
              Get started
            </button>
            <button
              type="button"
              onClick={handleSkip}
              style={{
                fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 400,
                color: 'var(--fg4)', background: 'transparent',
                border: 'none', cursor: 'pointer', padding: '4px 0',
              }}
            >
              Skip for now
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
        color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase',
      }}>
        {label}
      </span>
      {children}
    </label>
  );
}

const inputStyle: React.CSSProperties = {
  fontFamily: 'var(--sans)', fontSize: 13,
  color: 'var(--fg1)', background: 'var(--bg-subtle)',
  border: '1px solid var(--border-md)', borderRadius: 8,
  padding: '8px 12px', outline: 'none',
  width: '100%', boxSizing: 'border-box',
};
