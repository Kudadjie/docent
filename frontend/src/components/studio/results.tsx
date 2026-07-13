'use client';

// Per-action result panels — extracted from app/studio/_output.tsx in the
// v2.3 monolith split.

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  CheckCircle, XCircle, AlertTriangle, ExternalLink, ChevronDown, ChevronRight, Plus,
} from 'lucide-react';
import { type ActionMeta } from '@/app/studio/_shared';
import { GhostBtn, CodeBlock, Chip, FieldLabel, Kbd } from '@/components/studio/controls';
import { BRAND, BRAND_DEEP, AMBER_BORDER, AMBER, BLUE } from '@/components/studio/palette';

export function OutputEmpty() {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '48px 32px',
      backgroundImage: 'radial-gradient(circle, var(--gray200) 1px, transparent 1px)',
      backgroundSize: '24px 24px',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, maxWidth: 380, textAlign: 'center' }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '4px 12px', borderRadius: 9999,
          background: BRAND + '1c', border: `1px solid ${BRAND + '44'}`,
          fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600,
          color: BRAND_DEEP, letterSpacing: '1.5px', textTransform: 'uppercase',
        }}>
          <span style={{ width: 5, height: 5, borderRadius: '50%', background: BRAND, display: 'inline-block' }} />
          Ready
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 24, fontWeight: 700, color: 'var(--fg1)', letterSpacing: '-0.5px', lineHeight: 1.2 }}>
          Run a studio action
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)', lineHeight: 1.75, maxWidth: 320 }}>
          Select an action on the left, fill in the form, then run — or press <Kbd>Ctrl</Kbd><Kbd>K</Kbd> to quick-jump.
        </div>
      </div>
    </div>
  );
}

// ── Result variants ────────────────────────────────────────────────────────────

export function DocPreview({ path }: { path: string }) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    if (content !== null) { setOpen(o => !o); return; }
    setOpen(true);
    setLoading(true);
    try {
      const r = await fetch('/api/fs/read?path=' + encodeURIComponent(path));
      const j = await r.json() as { content?: string; error?: string };
      if (j.error) setErr(j.error);
      else setContent(j.content ?? '');
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <button onClick={load} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: 'transparent', border: 'none', cursor: 'pointer', padding: '3px 0', fontFamily: 'var(--sans)', fontSize: 12, color: BRAND_DEEP, fontWeight: 500 }}>
        <ChevronDown size={13} strokeWidth={2} style={{ transform: open ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.12s' }} />
        {open ? 'Hide preview' : 'Preview document'}
      </button>
      {open && (
        <div style={{ marginTop: 8, border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', maxHeight: 400 }}>
          {loading && <div style={{ padding: '16px', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)' }}>Loading…</div>}
          {err && <div style={{ padding: '12px', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--red-text)' }}>{err}</div>}
          {content !== null && !loading && (
            <div style={{ padding: '14px 16px', background: 'var(--bg-subtle)', overflowY: 'auto', maxHeight: 400 }}
              className="md-preview">
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ResultResearchSuccess({ topic, action, dest, doneData, onSaveAsPreset, onPipeToNotebook }: {
  topic: string; action: ActionMeta; dest: string;
  doneData?: Record<string, unknown> | null;
  onSaveAsPreset: () => void; onPipeToNotebook: (srcPath: string) => void;
}) {
  const outputFile = (doneData?.output_file as string | null | undefined) ?? null;
  const notebookId = (doneData?.notebook_id as string | null | undefined) ?? null;
  const message    = (doneData?.message as string | undefined) ?? '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
          <span style={{ color: BRAND_DEEP, display: 'flex' }}><CheckCircle size={16} strokeWidth={1.5} /></span>
          <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Done</span>
        </span>
        {message && <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.5px' }}>{message}</span>}
        <div style={{ marginLeft: 'auto' }}>
          <GhostBtn size="sm" onClick={onSaveAsPreset}>Save as preset</GhostBtn>
        </div>
      </div>

      {outputFile ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <FieldLabel>Output file</FieldLabel>
          <CodeBlock>{outputFile}</CodeBlock>
          <DocPreview path={outputFile} />
        </div>
      ) : (
        <div>
          <FieldLabel>Output file</FieldLabel>
          <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)' }}>
            Saved to your configured output folder.
          </span>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {notebookId ? (
          <a href={'https://notebooklm.google.com/notebook/' + notebookId} target="_blank" rel="noreferrer"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--sans)', fontSize: 12, color: BRAND_DEEP, textDecoration: 'none', padding: '4px 10px', borderRadius: 9999, background: BRAND + '18', border: '1px solid ' + BRAND + '44' }}>
            <ExternalLink size={12} strokeWidth={1.5} /> Open in NotebookLM
          </a>
        ) : dest === 'Local' && outputFile && (
          <button
            onClick={() => onPipeToNotebook(outputFile.replace(/\.md$/, '-sources.json'))}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)', padding: '4px 10px', borderRadius: 9999, background: 'transparent', border: '1px solid var(--border-md)', cursor: 'pointer' }}>
            <ExternalLink size={12} strokeWidth={1.5} /> Send to NotebookLM
          </button>
        )}
        {outputFile && (
          <button onClick={() => fetch('/api/fs/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: outputFile }) })}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)', padding: '4px 10px', borderRadius: 9999, background: 'transparent', border: '1px solid var(--border-md)', cursor: 'pointer' }}>
            <ExternalLink size={12} strokeWidth={1.5} /> Open output folder
          </button>
        )}
      </div>

    </div>
  );
}

export function ResultStopped() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: AMBER_BORDER, display: 'flex' }}><AlertTriangle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Run stopped</span>
      </div>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.55 }}>
        The run was cancelled before it finished. The activity log above shows progress up to the stop point.
      </div>
    </div>
  );
}

export function ResultFailure({ errorText }: { errorText?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: 'var(--red-text)', display: 'flex' }}><XCircle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Run failed</span>
      </div>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.55 }}>
        {errorText ?? 'The run failed. Check the activity log above for details.'}
      </div>
    </div>
  );
}

type PaperRow = { title: string; authors: string; year: string; source: string; url: string | null };

function _normalizePapers(data: Record<string, unknown> | null): PaperRow[] {
  const papers = Array.isArray(data?.papers) ? (data!.papers as Record<string, unknown>[]) : [];
  return papers.map(p => {
    const authorsRaw = p.authors;
    const authors = Array.isArray(authorsRaw)
      ? (authorsRaw as string[]).slice(0, 4).join(' · ') + ((authorsRaw as string[]).length > 4 ? ' et al.' : '')
      : String(authorsRaw ?? '');
    const published = typeof p.published === 'string' ? p.published.slice(0, 4) : '';
    const year = String(p.year ?? published ?? '') || '—';
    const doi = p.doi ? `https://doi.org/${p.doi}` : null;
    const url = (p.arxiv_url as string) || (p.url as string) || doi || null;
    const source = (p.arxiv_id as string) ? 'arXiv' : (p.doi ? 'DOI' : (p.venue as string) || '');
    return { title: String(p.title ?? 'Untitled'), authors, year, source, url };
  });
}

export function ResultSearch({ query, data }: { query: string; data: Record<string, unknown> | null }) {
  const rows = _normalizePapers(data);
  const resolvedQuery = (typeof data?.query === 'string' && data.query) || query;
  if (rows.length === 0) {
    return (
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>
        No results{resolvedQuery ? <> for <span style={{ fontFamily: 'var(--mono)', color: 'var(--fg2)' }}>&ldquo;{resolvedQuery}&rdquo;</span></> : ''}.
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>
        {rows.length} results · query <span style={{ fontFamily: 'var(--mono)', color: 'var(--fg2)' }}>&ldquo;{resolvedQuery}&rdquo;</span>
      </div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border)' }}>
              {['Title', 'Year', 'Authors', 'Source', ''].map((c, i) => (
                <th key={i} style={{ padding: '8px 12px', textAlign: i === 4 ? 'right' : 'left', fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500, color: 'var(--fg4)', letterSpacing: '0.6px', textTransform: 'uppercase' }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} style={{ borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg1)', lineHeight: 1.4 }}>
                  {r.url ? (
                    <a href={r.url} target="_blank" rel="noreferrer" style={{ color: 'var(--fg1)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                      {r.title}<span style={{ color: 'var(--fg4)', opacity: 0.5, display: 'flex' }}><ExternalLink size={12} strokeWidth={1.5} /></span>
                    </a>
                  ) : r.title}
                </td>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg3)', whiteSpace: 'nowrap' }}>{r.year}</td>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', whiteSpace: 'nowrap' }}>{r.authors}</td>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.4px', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{r.source}</td>
                <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                  {r.url && <a href={r.url} target="_blank" rel="noreferrer"><GhostBtn size="sm">Look up</GhostBtn></a>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ResultGetPaper({ data }: { data: Record<string, unknown> | null }) {
  const [more, setMore] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const arxivId  = typeof data?.arxiv_id === 'string' ? data.arxiv_id : '';
  const title    = typeof data?.title === 'string' && data.title ? data.title : (arxivId ? `arXiv:${arxivId}` : 'Paper');
  const abstract = typeof data?.abstract === 'string' ? data.abstract : '';
  const overview = typeof data?.overview === 'string' ? data.overview : '';
  const arxivUrl = arxivId ? `https://arxiv.org/abs/${arxivId}` : null;

  if (!data) {
    return <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>No paper details returned.</div>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 16, fontWeight: 600, color: 'var(--fg1)', lineHeight: 1.35, marginBottom: 6 }}>
          {title}
        </div>
        {arxivId && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)' }}>
            <span>arXiv:{arxivId}</span>
          </div>
        )}
      </div>
      {abstract && (
        <div>
          <FieldLabel>Abstract</FieldLabel>
          <div style={{ maxHeight: 140, overflowY: 'auto', background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg2)', lineHeight: 1.55 }}>{abstract}</div>
        </div>
      )}
      {overview && (
        <div>
          <FieldLabel>AI overview</FieldLabel>
          <div style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg2)', lineHeight: 1.6 }}>
            {more || overview.length <= 600 ? overview : overview.slice(0, 600) + '…'}
            {overview.length > 600 && (
              <button onClick={() => setMore(m => !m)} style={{ marginLeft: 6, background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500, color: BRAND_DEEP, padding: 0 }}>
                {more ? 'Show less' : 'Show more'}
              </button>
            )}
          </div>
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button onClick={() => setShowAdd(s => !s)} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 9999, background: 'transparent', color: 'var(--fg2)', border: '1px solid var(--border-md)', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 500, cursor: 'pointer' }}>
          <Plus size={14} strokeWidth={2} /> Add to Reading
        </button>
        {arxivUrl && (
          <a href={arxivUrl} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 9999, background: 'transparent', color: 'var(--fg2)', border: '1px solid var(--border-md)', fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 500, textDecoration: 'none' }}>
            <ExternalLink size={12} strokeWidth={1.5} /> Open on arXiv
          </a>
        )}
      </div>
      {showAdd && (
        <div style={{ background: 'var(--gray100)', borderRadius: 8, padding: '12px 14px', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)', lineHeight: 1.6 }}>
          The reading queue syncs from Mendeley. To add this paper: download its PDF, drop it into your
          Mendeley watch folder (Settings → reading database folder), then run <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg1)' }}>docent reading sync-from-mendeley</span> (or the Sync button on the Reading page).
        </div>
      )}
    </div>
  );
}

function PerspectiveSection({ title, color, body }: { title: string; color: string; body: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
      <button onClick={() => setOpen(o => !o)} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', textAlign: 'left' }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
        {title}
        <span style={{ marginLeft: 'auto', color: 'var(--fg4)', display: 'flex' }}>
          {open ? <ChevronDown size={14} strokeWidth={2} /> : <ChevronRight size={14} strokeWidth={2} />}
        </span>
      </button>
      {open && (
        <div style={{ padding: '0 14px 12px', fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.6, borderTop: '1px solid var(--border)' }}>
          <div style={{ paddingTop: 10 }}>{body}</div>
        </div>
      )}
    </div>
  );
}

type CiteGraphPaper = {
  title: string; authors: string; year: number | null;
  doi: string | null; arxiv_id: string | null;
  oa_url: string | null; s2_url: string; abstract: string;
};

function CiteGraphPaperCard({ paper, index }: { paper: CiteGraphPaper; index: number }) {
  const [open, setOpen] = useState(false);
  const href = paper.oa_url || (paper.doi ? `https://doi.org/${paper.doi}` : paper.s2_url) || '';
  const doiLabel = paper.arxiv_id ? `arXiv:${paper.arxiv_id}` : paper.doi ?? '';
  return (
    <div style={{ borderBottom: '1px solid var(--border)', padding: '12px 0' }}>
      {/* Title row */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', paddingTop: 3, minWidth: 20, textAlign: 'right', flexShrink: 0 }}>{index + 1}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 3 }}>
            {paper.oa_url && (
              <span style={{ flexShrink: 0, marginTop: 2, fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700, letterSpacing: '0.5px', textTransform: 'uppercase', color: '#3f8f54', background: 'rgba(93,184,114,0.14)', padding: '1px 6px', borderRadius: 4 }}>OA</span>
            )}
            <div style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', lineHeight: 1.4 }}>
              {href ? (
                <a href={href} target="_blank" rel="noreferrer" style={{ color: 'var(--fg1)', textDecoration: 'none' }}>
                  {paper.title || 'Untitled'}
                  <ExternalLink size={11} strokeWidth={1.5} style={{ marginLeft: 5, opacity: 0.4, verticalAlign: 'middle' }} />
                </a>
              ) : (paper.title || 'Untitled')}
            </div>
          </div>
          {/* Meta row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {paper.authors && <span style={{ fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg3)' }}>{paper.authors}</span>}
            {paper.year && <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--fg4)' }}>{paper.year}</span>}
            {doiLabel && <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)' }}>{doiLabel}</span>}
            {paper.abstract && (
              <button onClick={() => setOpen(o => !o)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'var(--sans)', fontSize: 11.5, color: BRAND_DEEP, padding: 0, display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                {open ? <ChevronDown size={12} strokeWidth={2} /> : <ChevronRight size={12} strokeWidth={2} />}
                Abstract
              </button>
            )}
          </div>
          {/* Abstract */}
          {open && paper.abstract && (
            <div style={{ marginTop: 8, fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.6, background: 'var(--bg-subtle)', borderRadius: 6, padding: '8px 10px', borderLeft: '2px solid var(--border-md)' }}>
              {paper.abstract}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function ResultCiteGraph({ data }: { data: Record<string, unknown> | null }) {
  const anchorTitle = typeof data?.anchor_title === 'string' ? data.anchor_title : '';
  const direction   = typeof data?.direction === 'string' ? data.direction : '';
  const totalFound  = typeof data?.total_found === 'number' ? data.total_found : 0;
  const oaCount     = typeof data?.oa_count === 'number' ? data.oa_count : 0;
  const message     = typeof data?.message === 'string' ? data.message : '';
  const papers      = Array.isArray(data?.papers) ? (data!.papers as CiteGraphPaper[]) : [];

  if (papers.length === 0) {
    return <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>{message || 'No papers found.'}</div>;
  }

  const dirLabel = direction === 'cited-by' ? 'citing this paper'
    : direction === 'citing' ? 'cited by this paper'
    : 'in the citation graph';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {/* Header */}
      <div style={{ marginBottom: 14 }}>
        {anchorTitle && (
          <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', marginBottom: 4 }}>
            Anchor · <span style={{ color: 'var(--fg2)', fontStyle: 'italic' }}>{anchorTitle}</span>
          </div>
        )}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>
            {totalFound} papers {dirLabel}
          </span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#3f8f54', background: 'rgba(93,184,114,0.12)', padding: '2px 8px', borderRadius: 9999 }}>
            {oaCount} open access
          </span>
          <span style={{ fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg4)' }}>· showing {papers.length}</span>
        </div>
      </div>
      {/* Paper list */}
      <div>
        {papers.map((p, i) => <CiteGraphPaperCard key={i} paper={p} index={i} />)}
      </div>
    </div>
  );
}

export function ResultNotebook({ data, doneData }: { data: Record<string, unknown> | null; doneData?: Record<string, unknown> | null }) {
  const num = (k: string): number => (typeof data?.[k] === 'number' ? (data[k] as number) : 0);
  const notebookId = (typeof data?.notebook_id === 'string' && data.notebook_id)
    || (typeof doneData?.notebook_id === 'string' ? (doneData.notebook_id as string) : '') || '';
  const added = num('sources_added');
  const failed = num('sources_failed');
  const fromNlm = num('sources_from_nlm');
  const message = typeof data?.message === 'string' ? data.message : (typeof doneData?.message === 'string' ? doneData!.message as string : '');

  const qg = (data?.quality_gate ?? null) as Record<string, unknown> | null;
  const contradictions = qg && typeof qg.contradictions === 'number' ? qg.contradictions : null;
  const validation = qg && typeof qg.validation === 'string' ? qg.validation : null;
  const gateClean = contradictions === 0;

  const perspectives = (data?.perspectives ?? null) as Record<string, string> | null;
  const perspEntries = perspectives ? Object.entries(perspectives).filter(([, v]) => typeof v === 'string' && v.trim()) : [];
  const perspColors = [BLUE, AMBER, BRAND_DEEP];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ color: BRAND_DEEP, display: 'flex' }}><CheckCircle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Notebook updated</span>
        {message && <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.5px' }}>{message}</span>}
      </div>
      {(added > 0 || failed > 0 || fromNlm > 0) && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {added > 0 && <Chip color={BRAND_DEEP}>{added} sources added</Chip>}
          {failed > 0 && <Chip color={AMBER}>{failed} failed</Chip>}
          {fromNlm > 0 && <Chip color={BLUE}>{fromNlm} from NLM web</Chip>}
        </div>
      )}
      {qg && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 9999, background: gateClean ? BRAND + '22' : 'var(--amber-bg)', color: gateClean ? BRAND_DEEP : 'var(--amber-text)', fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
            {gateClean ? <CheckCircle size={11} strokeWidth={1.5} /> : <AlertTriangle size={11} strokeWidth={1.5} />} Quality gate · {gateClean ? 'clean' : 'flags'}
          </span>
          {(contradictions !== null || validation) && (
            <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)' }}>
              {contradictions !== null ? `${contradictions} contradiction${contradictions === 1 ? '' : 's'}` : ''}{validation ? `${contradictions !== null ? ' · ' : ''}${validation}` : ''}
            </span>
          )}
        </div>
      )}
      {perspEntries.length > 0 && (
        <div>
          <FieldLabel>Perspectives</FieldLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {perspEntries.map(([key, body], i) => (
              <PerspectiveSection key={key} title={key.charAt(0).toUpperCase() + key.slice(1)} color={perspColors[i % perspColors.length]} body={body} />
            ))}
          </div>
        </div>
      )}
      {notebookId && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <a href={'https://notebooklm.google.com/notebook/' + notebookId} target="_blank" rel="noreferrer"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--sans)', fontSize: 12, color: BRAND_DEEP, textDecoration: 'none', padding: '4px 10px', borderRadius: 9999, background: BRAND + '18', border: '1px solid ' + BRAND + '44' }}>
            <ExternalLink size={12} strokeWidth={1.5} /> Open in NotebookLM
          </a>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)' }}>{notebookId}</span>
        </div>
      )}
    </div>
  );
}

function _formatConfigValue(v: unknown): { text: string; unset: boolean } {
  if (v === null || v === undefined || v === '' || v === '(not set)') return { text: '(not set)', unset: true };
  if (Array.isArray(v)) return { text: v.join(' '), unset: false };
  return { text: String(v), unset: false };
}

export function ResultConfigShow({ data }: { data: Record<string, unknown> | null }) {
  const rows = data ? Object.entries(data) : [];
  if (rows.length === 0) {
    return <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>No configuration returned.</div>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>Configuration ({rows.length} keys)</div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
        {rows.map(([k, v], i) => {
          const { text, unset } = _formatConfigValue(v);
          return (
            <div key={k} style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 0.4fr) 1fr', gap: 14, padding: '9px 14px', borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none', background: i % 2 === 0 ? 'transparent' : 'var(--bg-subtle)', alignItems: 'center' }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)', letterSpacing: '0.3px' }}>{k}</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: unset ? 'var(--fg4)' : 'var(--fg1)', fontStyle: unset ? 'italic' : 'normal', wordBreak: 'break-all' }}>{text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ResultConfigSet({ cfgKey, data }: { cfgKey: string; data: Record<string, unknown> | null }) {
  const key = (typeof data?.key === 'string' && data.key) || cfgKey;
  const message = typeof data?.message === 'string' ? data.message : '';
  const configPath = typeof data?.config_path === 'string' ? data.config_path : '~/.docent/config.toml';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: BRAND_DEEP, display: 'flex' }}><CheckCircle size={16} strokeWidth={1.5} /></span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--fg1)' }}>Key saved</span>
      </div>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg2)', lineHeight: 1.6 }}>
        {message || <><span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--fg1)' }}>{key}</span>{' was written to:'}</>}
      </div>
      <CodeBlock>{configPath}</CodeBlock>
    </div>
  );
}

// ── Output panel ───────────────────────────────────────────────────────────────

// Phases that don't appear in the breadcrumb progress strip but DO show in the activity log.
