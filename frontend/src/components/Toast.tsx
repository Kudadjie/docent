'use client';

import { useEffect } from 'react';
import { CheckCircle, AlertCircle, X } from 'lucide-react';

export interface ToastData {
  type: 'success' | 'error';
  message: string;
}

interface Props {
  toast: ToastData;
  onDismiss: () => void;
  duration?: number;
}

export default function Toast({ toast, onDismiss, duration = 5000 }: Props) {
  useEffect(() => {
    const t = setTimeout(onDismiss, duration);
    return () => clearTimeout(t);
  }, [toast, onDismiss, duration]);

  const isError = toast.type === 'error';

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 100,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        padding: '12px 14px',
        borderRadius: 10,
        border: `1px solid ${isError ? 'rgba(212,86,86,0.25)' : 'rgba(24,226,153,0.25)'}`,
        background: isError ? 'rgba(212,86,86,0.08)' : 'rgba(24,226,153,0.08)',
        backdropFilter: 'blur(8px)',
        boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
        maxWidth: 360,
        animation: 'fadeInUp 0.18s ease forwards',
      }}
    >
      <span style={{ color: isError ? '#D45656' : '#0fa76e', display: 'flex', flexShrink: 0, marginTop: 1 }}>
        {isError
          ? <AlertCircle size={15} strokeWidth={1.8} />
          : <CheckCircle size={15} strokeWidth={1.8} />}
      </span>
      <span
        style={{
          fontFamily: 'var(--sans)',
          fontSize: 13,
          fontWeight: 400,
          color: 'var(--fg1)',
          lineHeight: 1.5,
          flex: 1,
        }}
      >
        {toast.message}
      </span>
      <button
        onClick={onDismiss}
        aria-label="Dismiss"
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--fg4)',
          display: 'flex',
          padding: 0,
          flexShrink: 0,
          marginTop: 1,
        }}
      >
        <X size={13} strokeWidth={2} />
      </button>
    </div>
  );
}
