'use client';

import React from 'react';
import { dashTokens } from './_tokens';

const MONO = 'var(--mono)';

export function CardShell({ dark, children, style, ...rest }: {
  dark: boolean;
  children: React.ReactNode;
  style?: React.CSSProperties;
  [key: string]: unknown;
}) {
  const D = dashTokens(dark);
  return (
    <div {...rest} style={{
      background: D.cardBg,
      border: `1px solid ${D.cardBorder}`,
      borderRadius: D.radius,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      minWidth: 0,   // critical: lets grid/flex children shrink below content size
      ...style,
    }}>
      {children}
    </div>
  );
}

export function Divider({ dark }: { dark: boolean }) {
  const D = dashTokens(dark);
  return <div style={{ height: 1, background: D.divider, flexShrink: 0 }} />;
}

export function SectionLabel({ dark, accent, right, children }: {
  dark: boolean;
  accent?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  const D = dashTokens(dark);
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 7,
        fontFamily: MONO, fontSize: 9, fontWeight: 500,
        color: D.sectionLabel, letterSpacing: '0.85px', textTransform: 'uppercase',
      }}>
        {accent && (
          <span style={{ width: 5, height: 5, borderRadius: '50%', background: accent, flexShrink: 0 }} />
        )}
        {children}
      </span>
      {right}
    </div>
  );
}

export function Section({ dark, label, accent, right, children }: {
  dark: boolean;
  label: string;
  accent?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }}>
      <SectionLabel dark={dark} accent={accent} right={right}>{label}</SectionLabel>
      <div style={{ minWidth: 0, overflow: 'hidden' }}>{children}</div>
    </div>
  );
}

export function CardHeader({ dark, left, right }: {
  dark: boolean;
  left: React.ReactNode;
  right?: React.ReactNode;
}) {
  const D = dashTokens(dark);
  return (
    <div style={{
      padding: '12px 18px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      borderBottom: `1px solid ${D.divider}`,
    }}>
      <span style={{
        fontFamily: MONO, fontSize: 10, fontWeight: 500,
        color: D.sectionLabel, letterSpacing: '1px', textTransform: 'uppercase',
      }}>
        {left}
      </span>
      {right}
    </div>
  );
}

export function CardFooter({ dark, left, right }: {
  dark: boolean;
  left: React.ReactNode;
  right: React.ReactNode;
}) {
  const D = dashTokens(dark);
  return (
    <div style={{
      padding: '10px 18px',
      borderTop: `1px solid ${D.divider}`,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      marginTop: 'auto',
    }}>
      <span style={{ fontFamily: MONO, fontSize: 10, color: D.dataMuted, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        {left}
      </span>
      {right}
    </div>
  );
}
