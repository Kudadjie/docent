import type { ReactNode } from 'react';

export interface DoctorCheck {
  label: string;
  status: 'OK' | 'WARN' | 'FAIL' | 'SKIP';
  version: string;
  detail: string;
}

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

export function DoctorStatusBadge({ status }: { status: DoctorCheck['status'] }) {
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

export function SectionCard({ icon, title, description, children, accentColor = '#18E299' }: {
  icon: ReactNode;
  title: string;
  description: ReactNode;
  children: ReactNode;
  accentColor?: string;
}) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ padding: '16px 20px 14px', borderBottom: '1px solid var(--border)', background: `${accentColor}18` }}>
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

export function KeyGroup({ label, children }: { label: string; children: ReactNode }) {
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
