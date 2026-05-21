'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { DashboardStat } from './_registry';
import { dashTokens, VIOLET, MONO } from './_tokens';
import { CardShell, Divider, Section, CardHeader, CardFooter } from './_primitives';

interface OutputFile {
  path: string;
  name: string;
  folder: string;
  size: number;
  mtime: number;
}

function cleanTopic(name: string): string {
  // Strip date prefixes (YYYY-MM-DD_ or YYYYMMDD_), underscores, extensions
  return name
    .replace(/^\d{4}-?\d{2}-?\d{2}[_-]?/g, '')
    .replace(/\.(md|txt|json|html?)$/i, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .trim();
}

function relativeTime(mtime: number): string {
  const diff = Date.now() - mtime * 1000;
  const m = Math.floor(diff / 60000);
  if (m < 2)  return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7)  return `${d}d ago`;
  return `${Math.floor(d / 7)}w ago`;
}

function classifyFile(file: OutputFile): 'research' | 'notes' | 'briefs' {
  const n = file.name.toLowerCase();
  const f = (file.folder ?? '').toLowerCase();
  if (n.includes('brief') || f.includes('brief')) return 'briefs';
  if (n.includes('note') || f.includes('note'))   return 'notes';
  return 'research';
}

export default function StudioCard({ dark, onStats }: {
  dark: boolean;
  onStats: (stats: DashboardStat[]) => void;
}) {
  const D = dashTokens(dark);
  const [files, setFiles] = useState<OutputFile[] | null>(null);

  useEffect(() => {
    fetch('/api/studio/outputs')
      .then(r => r.json())
      .then((d: { files: OutputFile[] }) => {
        const fs = d.files ?? [];
        setFiles(fs);
        onStats([
          { label: 'Outputs', value: fs.length, color: VIOLET },
        ]);
      })
      .catch(() => setFiles([]));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const now = Date.now();
  const todayFiles  = (files ?? []).filter(f => now - f.mtime * 1000 < 86400000);
  const weekFiles   = (files ?? []).filter(f => now - f.mtime * 1000 < 7 * 86400000);
  const sorted      = [...(files ?? [])].sort((a, b) => b.mtime - a.mtime);
  const recent      = sorted.slice(0, 3);
  const lastFile    = sorted[0];

  const byType = (files ?? []).reduce(
    (acc, f) => { acc[classifyFile(f)]++; return acc; },
    { research: 0, notes: 0, briefs: 0 },
  );

  const lastRunText = lastFile ? relativeTime(lastFile.mtime) : null;

  return (
    <CardShell dark={dark}>
      <CardHeader
        dark={dark}
        left="Studio — Outputs"
        right={lastRunText ? (
          <span style={{ fontFamily: MONO, fontSize: 9, color: VIOLET, letterSpacing: '0.6px' }}>
            · {lastRunText}
          </span>
        ) : undefined}
      />

      {/* Stats */}
      <Section dark={dark} label="Stats" accent={VIOLET}>
        <div style={{ fontFamily: MONO, fontSize: 13, color: D.dataMuted, letterSpacing: '0.2px' }}>
          <span style={{ color: VIOLET, fontWeight: 500 }}>{files?.length ?? '—'}</span> outputs
          <span style={{ color: D.sectionLabel, margin: '0 8px' }}>·</span>
          <span style={{ color: D.dataBright, fontWeight: 500 }}>{todayFiles.length}</span> today
          <span style={{ color: D.sectionLabel, margin: '0 8px' }}>·</span>
          <span style={{ color: D.dataBright, fontWeight: 500 }}>{weekFiles.length}</span> this week
        </div>
      </Section>
      <Divider dark={dark} />

      {/* Recent sessions */}
      <Section dark={dark} label="Recent">
        {recent.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {recent.map(f => (
              <div key={f.path} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '5px 0',
              }}>
                <span style={{
                  fontSize: 13, color: dark ? '#ededed' : '#0d0d0d',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  flex: 1, minWidth: 0, paddingRight: 12,
                }} title={cleanTopic(f.name)}>
                  {cleanTopic(f.name)}
                </span>
                <span style={{
                  fontFamily: MONO, fontSize: 10, color: D.dataMuted,
                  textTransform: 'uppercase', letterSpacing: '0.5px', flexShrink: 0,
                }}>
                  {relativeTime(f.mtime)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <span style={{ fontSize: 13, color: D.sectionLabel, fontStyle: 'italic' }}>
            No research sessions yet — start a topic in Studio
          </span>
        )}
      </Section>
      <Divider dark={dark} />

      {/* By type */}
      <Section dark={dark} label="By type">
        <div style={{ fontFamily: MONO, fontSize: 11, color: D.dataMuted, letterSpacing: '0.2px' }}>
          <span style={{ color: D.dataBright, fontWeight: 500 }}>{byType.research}</span> research
          <span style={{ color: D.sectionLabel, margin: '0 8px' }}>·</span>
          <span style={{ color: D.dataBright, fontWeight: 500 }}>{byType.notes}</span> notes
          <span style={{ color: D.sectionLabel, margin: '0 8px' }}>·</span>
          <span style={{ color: D.dataBright, fontWeight: 500 }}>{byType.briefs}</span> briefs
        </div>
      </Section>

      <CardFooter
        dark={dark}
        left={lastRunText ? `Last run ${lastRunText}` : 'No runs yet'}
        right={
          <Link href="/studio" style={{
            fontSize: 12, fontWeight: 500,
            color: VIOLET, textDecoration: 'none',
          }} className="cta-link">
            Open →
          </Link>
        }
      />
    </CardShell>
  );
}
