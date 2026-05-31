'use client';

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';
import { useTour } from '@/hooks/useTour';

// ── TOC definition ────────────────────────────────────────────────────────────
// Each entry is either a doc slug (fetched from /api/docs/{slug}) or 'overview'
// (kept as a short hardcoded intro — no separate file needed).

type TocEntry = {
  id: string;
  label: string;
  slug?: string; // omit for hardcoded sections
};

const TOC: TocEntry[] = [
  { id: 'overview',  label: 'Overview' },
  { id: 'reading',   label: 'Reading Queue', slug: 'reading' },
  { id: 'studio',    label: 'Studio',        slug: 'studio' },
  { id: 'cli',       label: 'CLI Reference', slug: 'cli' },
  { id: 'ecosystem', label: 'Ecosystem',     slug: 'ecosystem' },
  { id: 'plugins',   label: 'Plugin Guide',  slug: 'plugins' },
];

// ── Markdown renderer components ──────────────────────────────────────────────

function slugify(text: string) {
  return text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
}

const mdComponents = {
  h1: ({ children }: React.ComponentPropsWithoutRef<'h1'>) => {
    const id = slugify(String(children));
    return (
      <h1 id={id} style={{ fontFamily: 'var(--sans)', fontWeight: 600, fontSize: 17,
        color: 'var(--fg1)', margin: '0 0 14px 0', paddingBottom: 10,
        borderBottom: '1px solid var(--border)' }}>
        {children}
      </h1>
    );
  },
  h2: ({ children }: React.ComponentPropsWithoutRef<'h2'>) => {
    const id = slugify(String(children));
    return (
      <h2 id={id} style={{ fontFamily: 'var(--sans)', fontWeight: 600, fontSize: 14,
        color: 'var(--fg1)', margin: '24px 0 8px 0', paddingBottom: 6,
        borderBottom: '1px solid var(--border)' }}>
        {children}
      </h2>
    );
  },
  h3: ({ children }: React.ComponentPropsWithoutRef<'h3'>) => {
    const id = slugify(String(children));
    return (
      <h3 id={id} style={{ fontFamily: 'var(--sans)', fontWeight: 500, fontSize: 13,
        color: 'var(--fg1)', margin: '18px 0 6px 0' }}>
        {children}
      </h3>
    );
  },
  p: ({ children }: React.ComponentPropsWithoutRef<'p'>) => (
    <p style={{ fontFamily: 'var(--sans)', fontSize: 13, lineHeight: 1.7,
      color: 'var(--fg2)', margin: '0 0 10px 0' }}>
      {children}
    </p>
  ),
  code: ({ children, className }: React.ComponentPropsWithoutRef<'code'>) => {
    const isBlock = className?.startsWith('language-');
    if (isBlock) return <code>{children}</code>;
    return (
      <code style={{ fontFamily: 'var(--mono)', fontSize: 12,
        background: 'var(--gray100)', color: 'var(--fg1)',
        padding: '1px 5px', borderRadius: 4, border: '1px solid var(--border)' }}>
        {children}
      </code>
    );
  },
  pre: ({ children }: React.ComponentPropsWithoutRef<'pre'>) => (
    <pre style={{ fontFamily: 'var(--mono)', fontSize: 12, lineHeight: 1.6,
      background: 'var(--gray100)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '12px 16px', margin: '8px 0 14px 0',
      overflowX: 'auto', color: 'var(--fg2)' }}>
      {children}
    </pre>
  ),
  table: ({ children }: React.ComponentPropsWithoutRef<'table'>) => (
    <div style={{ overflowX: 'auto', marginBottom: 16 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse',
        fontFamily: 'var(--sans)', fontSize: 12 }}>
        {children}
      </table>
    </div>
  ),
  th: ({ children }: React.ComponentPropsWithoutRef<'th'>) => (
    <th style={{ padding: '7px 12px', textAlign: 'left', fontWeight: 600,
      color: 'var(--fg1)', background: 'var(--gray100)',
      borderBottom: '1px solid var(--border)', borderRight: '1px solid var(--border)' }}>
      {children}
    </th>
  ),
  td: ({ children }: React.ComponentPropsWithoutRef<'td'>) => (
    <td style={{ padding: '7px 12px', color: 'var(--fg2)',
      borderBottom: '1px solid var(--border)', borderRight: '1px solid var(--border)',
      verticalAlign: 'top', lineHeight: 1.5 }}>
      {children}
    </td>
  ),
  ul: ({ children }: React.ComponentPropsWithoutRef<'ul'>) => (
    <ul style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg2)',
      margin: '0 0 12px 0', paddingLeft: 20, lineHeight: 1.7 }}>
      {children}
    </ul>
  ),
  ol: ({ children }: React.ComponentPropsWithoutRef<'ol'>) => (
    <ol style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg2)',
      margin: '0 0 12px 0', paddingLeft: 20, lineHeight: 1.7 }}>
      {children}
    </ol>
  ),
  blockquote: ({ children }: React.ComponentPropsWithoutRef<'blockquote'>) => (
    <blockquote style={{ borderLeft: '3px solid var(--border)', margin: '0 0 12px 0',
      paddingLeft: 14, color: 'var(--fg3)', fontStyle: 'italic' }}>
      {children}
    </blockquote>
  ),
  a: ({ href, children }: React.ComponentPropsWithoutRef<'a'>) => (
    <a href={href} target="_blank" rel="noopener noreferrer"
      style={{ color: 'var(--accent)', textDecoration: 'underline' }}>
      {children}
    </a>
  ),
  hr: () => (
    <hr style={{ border: 'none', borderTop: '1px solid var(--border)',
      margin: '20px 0' }} />
  ),
};

// ── DocSection ────────────────────────────────────────────────────────────────

function DocSection({ slug }: { slug: string }) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/docs/${slug}`)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.text();
      })
      .then(setContent)
      .catch(e => setError(String(e)));
  }, [slug]);

  if (error) {
    return (
      <p style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg4)',
        padding: '20px 0' }}>
        Could not load documentation ({error}).
      </p>
    );
  }

  if (content === null) {
    return (
      <p style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg4)',
        padding: '20px 0' }}>
        Loading…
      </p>
    );
  }

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
      {content}
    </ReactMarkdown>
  );
}

// ── Card wrapper ──────────────────────────────────────────────────────────────

function Card({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <div id={id} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '24px 28px', marginBottom: 20 }}>
      {children}
    </div>
  );
}

// ── Overview (hardcoded — no separate markdown file) ──────────────────────────

function OverviewSection() {
  return (
    <>
      <p style={{ fontFamily: 'var(--sans)', fontSize: 13, lineHeight: 1.7,
        color: 'var(--fg2)', margin: '0 0 12px 0' }}>
        Docent is a grad-school AI assistant with three main tools: a{' '}
        <strong>Reading Queue</strong> that syncs with your reference manager
        (Mendeley or Zotero), a <strong>Studio</strong> research engine for
        AI-powered literature reviews, paper analysis, and notebook building, and
        an <strong>Ecosystem</strong> page that connects all the external tools
        Docent integrates with.
      </p>
      <p style={{ fontFamily: 'var(--sans)', fontSize: 13, lineHeight: 1.7,
        color: 'var(--fg2)', margin: '0 0 12px 0' }}>
        Every feature is callable three ways: from the terminal (
        <code style={{ fontFamily: 'var(--mono)', fontSize: 12,
          background: 'var(--gray100)', color: 'var(--fg1)',
          padding: '1px 5px', borderRadius: 4, border: '1px solid var(--border)' }}>
          docent …
        </code>
        ), from Claude via MCP (
        <code style={{ fontFamily: 'var(--mono)', fontSize: 12,
          background: 'var(--gray100)', color: 'var(--fg1)',
          padding: '1px 5px', borderRadius: 4, border: '1px solid var(--border)' }}>
          docent serve
        </code>
        ), or from this web UI (
        <code style={{ fontFamily: 'var(--mono)', fontSize: 12,
          background: 'var(--gray100)', color: 'var(--fg1)',
          padding: '1px 5px', borderRadius: 4, border: '1px solid var(--border)' }}>
          docent ui
        </code>
        ).
      </p>
    </>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DocsPage() {
  const { dark, toggleDark } = useDarkMode();

  useTour('docs', [
    {
      popover: {
        title: "Docent's documentation",
        description: 'Everything you need to configure, extend, and get the most out of Docent — setup guides, CLI reference, sync troubleshooting, and plugin docs.',
      },
    },
    {
      popover: {
        title: 'Jump to any section',
        description: 'Use the left sidebar to jump between topics. The Reading guide covers reference manager sync and queue management; the Studio guide covers all research backends.',
      },
    },
  ]);

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden',
      background: 'var(--bg)', backgroundImage: 'var(--hero-grad)',
      backgroundRepeat: 'no-repeat' }}>
      <Sidebar active="docs" queueCount={0} dark={dark} />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column',
        minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner dark={dark} onToggleDark={toggleDark} />

        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>

          {/* TOC */}
          <div style={{ width: 176, flexShrink: 0, borderRight: '1px solid var(--border)',
            padding: '24px 0', overflow: 'auto' }}>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 10, fontWeight: 600,
              textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--fg4)',
              padding: '0 18px 8px' }}>
              On this page
            </div>
            {TOC.map((s) => (
              <button
                key={s.id}
                onClick={() => scrollTo(s.id)}
                style={{ display: 'block', width: '100%', textAlign: 'left',
                  padding: '5px 18px', background: 'transparent', border: 'none',
                  cursor: 'pointer', fontFamily: 'var(--sans)', fontSize: 12,
                  color: 'var(--fg3)' }}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div style={{ flex: 1, padding: '28px 40px', overflow: 'auto',
            backgroundImage: 'var(--hero-grad)', backgroundRepeat: 'no-repeat',
            backgroundSize: '100% 100%', backgroundAttachment: 'local' }}>

            {TOC.map((entry) => (
              <Card key={entry.id} id={entry.id}>
                {entry.slug
                  ? <DocSection slug={entry.slug} />
                  : <OverviewSection />
                }
              </Card>
            ))}

          </div>
        </div>
      </main>
    </div>
  );
}
