'use client';

import { useState } from 'react';
import { Sparkles, Cpu, BookOpen, ExternalLink, Check, Copy, ArrowRight, Globe } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';

// ── Colours ──────────────────────────────────────────────────────
const BRAND      = '#18E299';
const BRAND_DEEP = '#0fa76e';
const BLUE       = '#3B82F6';
const VIOLET     = '#8B5CF6';
const PINK       = '#EC4899';

// ── Data ─────────────────────────────────────────────────────────

interface Tool {
  id: string;
  name: string;
  author: string;
  license: string;
  Icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  accent: string;
  description: string;
  whenToUse: string;
  install: string;
  repo: string;
}

const TOOLS: Tool[] = [
  {
    id: 'academic-research-skills',
    name: 'Academic Research Skills',
    author: 'Cheng-I Wu',
    license: 'CC-BY-NC 4.0',
    Icon: Sparkles,
    accent: VIOLET,
    description:
      'A Claude Code plugin providing a full academic workflow: 13-agent deep research, 12-agent paper writing, 7-agent peer review, and a 10-stage end-to-end orchestrator with integrity gates. Emphasises "AI as copilot, not pilot."',
    whenToUse:
      'After a Docent research run — feed the output into /ars-write for a paper draft, then /ars-review for structured peer critique. Use /ars-revision when you have reviewer feedback to work through.',
    install: '/plugin marketplace add Imbad0202/academic-research-skills',
    repo: 'github.com/Imbad0202/academic-research-skills',
  },
  {
    id: 'feynman',
    name: 'Feynman',
    author: 'Companion (companion.ai)',
    license: 'MIT',
    Icon: Cpu,
    accent: BLUE,
    description:
      'An open-source AI research agent CLI. Runs multi-stage research pipelines using any major LLM provider via a unified interface. Docent uses Feynman as its highest-quality research backend (`--backend feynman`).',
    whenToUse:
      'When you need the highest-quality long-form research brief and have an LLM API key. Feynman handles the full synthesis pipeline autonomously — Docent orchestrates it and collects the output.',
    install: 'npm install -g @companion-ai/feynman',
    repo: 'feynman.is',
  },
  {
    id: 'notebooklm',
    name: 'NotebookLM',
    author: 'Google',
    license: 'Proprietary · free tier',
    Icon: BookOpen,
    accent: BRAND_DEEP,
    description:
      "A web-based research notebook that grounds AI answers in the sources you upload. Docent's `to-notebook` command pushes any run's sources + report into a notebook your collaborators can open in their browser.",
    whenToUse:
      'When you need to hand a research artifact to a non-technical collaborator — an advisor, a co-author, a reviewer — or want audio overviews and flashcards generated from your research output.',
    install: 'docent studio to-notebook --output-file research/output.md',
    repo: 'notebooklm.google.com',
  },
];

interface InsideRow { area: string; name: string; note: string; license: string; }
const INSIDE: InsideRow[] = [
  { area: 'Multi-stage pipeline',   name: 'Feynman (Companion)',           note: 'planner → fetch → write → verify → review → refine', license: 'MIT' },
  { area: 'Citation verification',  name: 'Academic Research Skills (Wu)', note: 'CrossRef + Semantic Scholar triangulation',           license: 'CC-BY-NC 4.0' },
  { area: 'Integrity gates',        name: 'Academic Research Skills (Wu)', note: 'Minimum-substance guards between pipeline stages',     license: 'CC-BY-NC 4.0' },
];

// ── Section label ─────────────────────────────────────────────────

function SectionLabel({ children, dot = BRAND, right }: { children: React.ReactNode; dot?: string; right?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 56, marginBottom: 18 }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%', background: dot, flexShrink: 0,
        boxShadow: `0 0 0 3px ${dot}1a`,
      }} />
      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: 'var(--fg2)', letterSpacing: '0.9px', textTransform: 'uppercase' as const }}>{children}</span>
      <span style={{ flex: 1, height: 1, background: 'var(--border)' }} />
      {right && <div style={{ flexShrink: 0 }}>{right}</div>}
    </div>
  );
}

// ── Install block ─────────────────────────────────────────────────

function InstallBlock({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard?.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 1300);
  }
  return (
    <div style={{
      position: 'relative',
      background: '#0d0d0d',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 10, padding: '12px 48px 12px 14px',
      fontFamily: 'var(--mono)', fontSize: 12.5, color: '#ededed',
      lineHeight: 1.5, letterSpacing: '0.2px', wordBreak: 'break-all' as const,
    }}>
      <span style={{ color: BRAND, marginRight: 9, userSelect: 'none' as const }}>$</span>
      <span>{command}</span>
      <button onClick={copy} title={copied ? 'Copied!' : 'Copy command'}
        style={{
          position: 'absolute', top: 6, right: 6,
          width: 30, height: 30, borderRadius: 7, border: 'none',
          background: copied ? BRAND + '22' : 'transparent',
          color: copied ? BRAND : 'rgba(255,255,255,0.55)',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'background 0.15s',
        }}>
        {copied ? <Check size={13} strokeWidth={2} /> : <Copy size={13} strokeWidth={1.6} />}
      </button>
    </div>
  );
}

// ── Tool card ─────────────────────────────────────────────────────

function ToolCard({ tool, index }: { tool: Tool; index: number }) {
  const { name, author, license, Icon, accent, description, whenToUse, install, repo } = tool;
  const num = String(index + 1).padStart(2, '0');
  return (
    <article style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 16,
      padding: '26px 28px 24px',
      marginTop: index === 0 ? 0 : 16,
      transition: 'border-color 0.15s',
    }}>
      {/* Header row */}
      <header style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 14 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10, flexShrink: 0,
          background: accent + '1a', color: accent,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={18} strokeWidth={1.5} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' as const, marginBottom: 6 }}>
            <h2 style={{ fontFamily: 'var(--sans)', fontSize: 19, fontWeight: 600, color: 'var(--fg1)', letterSpacing: '-0.35px', lineHeight: 1.2, margin: 0 }}>{name}</h2>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, fontWeight: 500, color: 'var(--fg4)', letterSpacing: '0.5px' }}>{num}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' as const }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 8px', borderRadius: 9999, background: 'var(--gray100)', fontFamily: 'var(--mono)', fontSize: 10.5, fontWeight: 600, color: 'var(--fg3)', letterSpacing: '0.3px', textTransform: 'uppercase' as const }}>{author}</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 8px', borderRadius: 9999, background: 'var(--gray100)', fontFamily: 'var(--mono)', fontSize: 10.5, fontWeight: 500, color: 'var(--fg4)', letterSpacing: '0.3px' }}>{license}</span>
          </div>
        </div>
        <a href={`https://${repo}`} target="_blank" rel="noreferrer"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)', textDecoration: 'none', letterSpacing: '0.3px', flexShrink: 0, padding: '4px 0', transition: 'color 0.12s' }}>
          {repo} <ExternalLink size={11} strokeWidth={1.5} />
        </a>
      </header>

      {/* Description */}
      <p style={{ fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.65, color: 'var(--fg2)', maxWidth: 640, margin: '0 0 18px' }}>{description}</p>

      {/* When to use */}
      <div style={{ paddingLeft: 14, borderLeft: `2px solid ${accent}66`, marginBottom: 20 }}>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, color: accent, letterSpacing: '0.8px', textTransform: 'uppercase' as const, marginBottom: 5 }}>When to use</div>
        <p style={{ fontFamily: 'var(--sans)', fontSize: 13.5, lineHeight: 1.6, color: 'var(--fg2)', maxWidth: 620, margin: 0 }}>{whenToUse}</p>
      </div>

      {/* Install */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500, color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase' as const }}>Install / access</span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.3px' }}>copy & paste</span>
        </div>
        <InstallBlock command={install} />
      </div>
    </article>
  );
}

// ── Inside Docent table ───────────────────────────────────────────

function InsideTable() {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 14, overflow: 'hidden' }}>
      <div style={{
        display: 'grid', gridTemplateColumns: '200px 1fr 160px',
        padding: '10px 18px',
        background: 'var(--bg-subtle)',
        borderBottom: '1px solid var(--border)',
        fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, color: 'var(--fg4)',
        letterSpacing: '0.8px', textTransform: 'uppercase' as const,
      }}>
        <div>Pattern</div>
        <div>Adopted from · usage</div>
        <div style={{ textAlign: 'right' as const }}>License</div>
      </div>
      {INSIDE.map((row, i) => (
        <div key={row.area} style={{
          display: 'grid', gridTemplateColumns: '200px 1fr 160px',
          padding: '12px 18px', alignItems: 'center',
          borderBottom: i < INSIDE.length - 1 ? '1px solid var(--border)' : 'none',
          transition: 'background 0.12s',
        }}>
          <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 500, color: 'var(--fg2)' }}>{row.area}</div>
          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 2, minWidth: 0 }}>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600, color: 'var(--fg1)', letterSpacing: '0.2px' }}>{row.name}</div>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)', lineHeight: 1.45 }}>{row.note}</div>
          </div>
          <div style={{ textAlign: 'right' as const, fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg3)', letterSpacing: '0.3px' }}>{row.license}</div>
        </div>
      ))}
    </div>
  );
}

// ── Footer CTA ────────────────────────────────────────────────────

function FooterCTA() {
  return (
    <div style={{
      marginTop: 24, padding: '28px 32px',
      background: BRAND + '0d',
      border: `1px solid ${BRAND_DEEP + '2e'}`,
      borderRadius: 16,
      display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' as const,
    }}>
      <div style={{ flex: '1 1 380px', minWidth: 0 }}>
        <h3 style={{ fontFamily: 'var(--sans)', fontSize: 17, fontWeight: 600, color: 'var(--fg1)', letterSpacing: '-0.25px', marginBottom: 5, margin: '0 0 5px' }}>
          Know a tool that pairs well with Docent?
        </h3>
        <p style={{ fontFamily: 'var(--sans)', fontSize: 13.5, color: 'var(--fg3)', lineHeight: 1.6, maxWidth: 560, margin: 0 }}>
          Open a GitHub issue with the tool name, a one-line description, and the install command. Include: name, author, repo/site, license, and when to reach for it alongside Docent.
        </p>
      </div>
      <a
        href="https://github.com/Kudadjie/docent/issues/new"
        target="_blank" rel="noreferrer"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '10px 18px', borderRadius: 9999,
          background: '#0d0d0d', color: '#ededed',
          fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, textDecoration: 'none',
          border: '1px solid rgba(255,255,255,0.12)',
          transition: 'background 0.12s',
        }}>
        <Globe size={14} strokeWidth={1.5} />
        Open an issue
        <ArrowRight size={13} strokeWidth={1.5} />
      </a>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────

export default function EcosystemPage() {
  const { dark, toggleDark } = useDarkMode();

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="ecosystem" queueCount={0} dark={dark} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner dark={dark} onToggleDark={toggleDark} />

        {/* Scrollable content — ecosystem uses BRAND + VIOLET + PINK gradient */}
        <div style={{
          flex: 1, overflow: 'auto', minHeight: 0,
          backgroundImage: dark ? `
            radial-gradient(ellipse 700px 320px at 10% 0%, ${BRAND}22, transparent 60%),
            radial-gradient(ellipse 560px 260px at 85% 15%, ${VIOLET}18, transparent 60%),
            radial-gradient(ellipse 480px 220px at 50% 75%, ${PINK}10, transparent 60%)
          ` : `
            radial-gradient(ellipse 700px 320px at 10% 0%, ${BRAND}44, transparent 60%),
            radial-gradient(ellipse 560px 260px at 85% 15%, ${VIOLET}36, transparent 60%),
            radial-gradient(ellipse 480px 220px at 50% 75%, ${PINK}20, transparent 60%)
          `,
          backgroundRepeat: 'no-repeat',
          backgroundSize: '100% 100%',
          backgroundAttachment: 'local',
        }}>
          <div style={{ maxWidth: 860, margin: '0 auto', padding: '64px 32px 96px' }}>

            {/* Hero */}
            <header style={{ marginBottom: 0 }}>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 7,
                padding: '4px 11px 4px 9px', borderRadius: 9999,
                background: 'var(--gray100)', border: '1px solid var(--border)',
                marginBottom: 18, marginTop: 0,
              }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: BRAND, animation: 'logo-dot-blink 1.6s step-end infinite' }} />
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, fontWeight: 500, color: 'var(--fg3)', letterSpacing: '0.6px', textTransform: 'uppercase' as const }}>
                  Curated · {TOOLS.length} tools
                </span>
              </div>
              <h1 style={{ fontFamily: 'var(--sans)', fontSize: 44, fontWeight: 600, color: 'var(--fg1)', letterSpacing: '-1.1px', lineHeight: 1.05, marginBottom: 14, margin: '0 0 14px' }}>
                Ecosystem
              </h1>
              <p style={{ fontFamily: 'var(--sans)', fontSize: 17, lineHeight: 1.55, color: 'var(--fg3)', maxWidth: 620, margin: 0 }}>
                Companion tools that pair with Docent. Hand off a run to a notebook, swap the reasoning backend, or bring Docent&apos;s workflows into your editor.
              </p>
            </header>

            {/* Companion tools */}
            <SectionLabel dot={VIOLET} right={
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--fg4)', letterSpacing: '0.4px' }}>
                {TOOLS.length} tools
              </span>
            }>
              Companion tools
            </SectionLabel>

            <div>
              {TOOLS.map((t, i) => <ToolCard key={t.id} tool={t} index={i} />)}
            </div>

            {/* Inside Docent */}
            <SectionLabel dot={BLUE} right={
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--fg4)', letterSpacing: '0.4px' }}>
                {INSIDE.length} patterns
              </span>
            }>
              Inside Docent
            </SectionLabel>
            <p style={{ fontFamily: 'var(--sans)', fontSize: 13.5, lineHeight: 1.6, color: 'var(--fg3)', maxWidth: 620, margin: '-6px 0 18px' }}>
              Open-source patterns adopted from the ecosystem. Full attribution in <span style={{ fontFamily: 'var(--mono)', fontSize: 12.5, color: 'var(--fg2)' }}>docs/ecosystem.md</span>.
            </p>
            <InsideTable />

            {/* Contribute */}
            <SectionLabel dot={PINK}>Contribute</SectionLabel>
            <FooterCTA />

            {/* Page footer */}
            <div style={{
              marginTop: 48, paddingTop: 24, borderTop: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' as const, gap: 12,
            }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)', letterSpacing: '0.4px' }}>
                docs/ecosystem.md
              </span>
              <a href="https://github.com/Kudadjie/docent" target="_blank" rel="noreferrer"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', textDecoration: 'none' }}>
                <Globe size={13} strokeWidth={1.5} /> docent on GitHub
              </a>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
