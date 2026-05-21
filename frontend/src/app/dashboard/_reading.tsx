'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { QueueData, QueueEntry } from '@/lib/types';
import type { DashboardStat } from './_registry';
import { dashTokens, BRAND, BRAND_D, AMBER, RED, MONO } from './_tokens';
import { CardShell, Divider, Section, CardHeader, CardFooter } from './_primitives';

function relativeTime(iso: string | null): string {
  if (!iso) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 2)  return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function isDeadlineUrgent(deadline: string | null): 'past' | 'soon' | null {
  if (!deadline) return null;
  const diff = new Date(deadline).getTime() - Date.now();
  if (diff < 0) return 'past';
  if (diff < 3 * 24 * 60 * 60 * 1000) return 'soon';
  return null;
}

export default function ReadingCard({ dark, onStats }: {
  dark: boolean;
  onStats: (stats: DashboardStat[]) => void;
}) {
  const D = dashTokens(dark);
  const [data, setData] = useState<QueueData | null>(null);

  useEffect(() => {
    fetch('/api/queue')
      .then(r => r.json())
      .then((d: QueueData) => {
        setData(d);
        onStats([
          { label: 'Queued',  value: d.banner.queued  },
          { label: 'Reading', value: d.banner.reading, color: BRAND },
          { label: 'Done',    value: d.banner.done,    dim: true },
        ]);
      })
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const active = data?.entries.filter(e => e.status !== 'done' && e.status !== 'removed') ?? [];
  const nextUp: QueueEntry | undefined  = active.filter(e => e.status === 'queued').sort((a, b) => a.order - b.order)[0];
  const inProg: QueueEntry | undefined  = active.find(e => e.status === 'reading');

  const pastDue  = active.filter(e => isDeadlineUrgent(e.deadline) === 'past').length;
  const dueSoon  = active.filter(e => isDeadlineUrgent(e.deadline) === 'soon').length;
  const showDeadlines = pastDue > 0 || dueSoon > 0;

  const queued  = data?.banner.queued  ?? 0;
  const reading = data?.banner.reading ?? 0;
  const done    = data?.banner.done    ?? 0;

  return (
    <CardShell dark={dark}>
      <CardHeader
        dark={dark}
        left="Reading — Queue"
        right={
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            fontFamily: MONO, fontSize: 9, color: BRAND_D,
            letterSpacing: '0.8px', textTransform: 'uppercase',
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%', background: BRAND,
              animation: 'pulse-dot 2.2s ease-in-out infinite',
            }} />
            Active
          </span>
        }
      />

      {/* Stats */}
      <Section dark={dark} label="Stats" accent={BRAND}>
        <div style={{ fontFamily: MONO, fontSize: 13, color: D.dataMuted, letterSpacing: '0.2px' }}>
          <span style={{ color: D.dataBright, fontWeight: 500 }}>{queued}</span> queued
          <span style={{ color: D.sectionLabel, margin: '0 8px' }}>·</span>
          <span style={{ color: BRAND, fontWeight: 500 }}>{reading}</span> reading
          <span style={{ color: D.sectionLabel, margin: '0 8px' }}>·</span>
          <span style={{ color: D.dataBright, fontWeight: 500 }}>{done}</span> done
        </div>
      </Section>
      <Divider dark={dark} />

      {/* Next up */}
      <Section dark={dark} label="Next up">
        {nextUp ? (
          <>
            <div style={{
              fontSize: 13, fontWeight: 500,
              color: 'var(--fg1)', lineHeight: 1.4,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }} title={nextUp.title}>
              {nextUp.title || nextUp.id}
            </div>
            <div style={{ marginTop: 5, fontFamily: MONO, fontSize: 11, color: D.dataMuted, letterSpacing: '0.4px' }}>
              <span style={{ color: 'var(--fg3)' }}>#{nextUp.order}</span>
              {nextUp.category && <>
                <span style={{ margin: '0 7px' }}>·</span>
                <span style={{ color: 'var(--fg3)' }}>{nextUp.category}</span>
              </>}
              {nextUp.tags[0] && <>
                <span style={{ margin: '0 7px' }}>·</span>
                <span style={{ textTransform: 'uppercase' }}>{nextUp.tags[0]}</span>
              </>}
            </div>
          </>
        ) : (
          <span style={{ fontSize: 13, color: D.sectionLabel, fontStyle: 'italic' }}>
            Queue is empty — sync your library to get started
          </span>
        )}
      </Section>
      <Divider dark={dark} />

      {/* Deadlines — conditional */}
      {showDeadlines && (
        <>
          <Section dark={dark} label="Deadlines">
            <div style={{ fontFamily: MONO, fontSize: 11, letterSpacing: '0.3px', lineHeight: 1.7 }}>
              {pastDue > 0 && (
                <span style={{ color: RED }}>
                  {pastDue} past due
                </span>
              )}
              {pastDue > 0 && dueSoon > 0 && (
                <span style={{ color: D.sectionLabel, margin: '0 8px' }}>·</span>
              )}
              {dueSoon > 0 && (
                <span style={{ color: AMBER }}>
                  {dueSoon} due soon
                </span>
              )}
            </div>
          </Section>
          <Divider dark={dark} />
        </>
      )}

      {/* In progress */}
      <Section
        dark={dark}
        label="In progress"
        right={inProg ? (
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            fontFamily: MONO, fontSize: 9, color: BRAND_D,
            border: '1px solid rgba(24,226,153,0.4)',
            borderRadius: 9999, padding: '2px 7px',
            letterSpacing: '0.6px', textTransform: 'uppercase',
          }}>
            <span style={{ width: 4, height: 4, borderRadius: '50%', background: BRAND }} />
            Reading
          </span>
        ) : undefined}
      >
        {inProg ? (
          <div style={{
            fontSize: 13, color: 'var(--fg1)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }} title={inProg.title}>
            {inProg.title || inProg.id}
          </div>
        ) : (
          <span style={{ fontSize: 13, color: D.sectionLabel, fontStyle: 'italic' }}>
            Nothing in progress — start a queued entry
          </span>
        )}
      </Section>

      <CardFooter
        dark={dark}
        left={`Synced ${relativeTime(data?.last_updated ?? null)}`}
        right={
          <Link href="/reading" style={{
            fontSize: 12, fontWeight: 500,
            color: BRAND, textDecoration: 'none',
          }} className="cta-link">
            Open →
          </Link>
        }
      />
    </CardShell>
  );
}
