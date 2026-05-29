// Shared types, constants, and pure functions for the Studio page.
// No React — imported by both _form.tsx and _output.tsx.

export type Status = 'idle' | 'queued' | 'running' | 'success' | 'failure' | 'stopped';
export type ActionId =
  | 'deep' | 'lit' | 'peer' | 'compare' | 'draft' | 'replicate' | 'audit'
  | 'search' | 'getpaper' | 'scholarly' | 'notebook'
  | 'cfgshow' | 'cfgset';

export interface ActionMeta {
  id: ActionId;
  label: string;
  form: string;
  group: string;
  desc: string;
}

export interface Source { title: string; year: number; src: string; }
export interface LogEntry  { phase: string; text: string; sources?: Source[]; }

export interface FormState {
  topic: string; backend: string; dest: string; guides: string[];
  artifact: string; artifactA: string; artifactB: string;
  query: string; maxResults: number; arxivId: string;
  outPath: string; srcPath: string; maxSources: number;
  nlm: boolean; gate: boolean; persp: boolean;
  cfgKey: string; cfgVal: string;
}

export interface Preset {
  id: string;
  name: string;
  actionId: ActionId;
  params: Partial<FormState>;
}

export interface RunRecord {
  id: string;
  actionId: ActionId;
  actionLabel: string;
  detail: string;
  status: 'success' | 'failure' | 'running' | 'stopped';
  timeAgo: string;
  startedAt: number;
  state: Partial<FormState>;
  logs: LogEntry[];
  sources: Source[];
  currentPhase: string | null;
  /** Serialised result payload (e.g. output_file, notebook_id). Preserved across history loads. */
  doneData?: Record<string, unknown> | null;
}

// ── Actions ────────────────────────────────────────────────────────────────────

const ACTION_GROUPS: { key: string; label: string; items: Omit<ActionMeta, 'group'>[] }[] = [
  {
    key: 'research', label: 'Actions',
    items: [
      { id: 'deep',      label: 'Deep research',     form: 'topic',    desc: 'Multi-source synthesis on a topic' },
      { id: 'lit',       label: 'Literature review',  form: 'topic',    desc: 'Structured review of the field' },
      { id: 'peer',      label: 'Peer review',        form: 'artifact', desc: 'Critique a single paper' },
      { id: 'compare',   label: 'Compare',            form: 'compare',  desc: 'Side-by-side analysis of two papers' },
      { id: 'draft',     label: 'Draft',              form: 'topic',    desc: 'Draft a writeup from sources' },
      // 'replicate' archived — Replication audit (still works from CLI: docent studio replicate --artifact ...)
      { id: 'audit',     label: 'Audit',              form: 'artifact', desc: 'Methods + evidence audit' },
    ],
  },
  {
    key: 'utilities', label: 'Utilities',
    items: [
      { id: 'search',    label: 'Search papers',      form: 'search',   desc: 'Search arXiv' },
      { id: 'getpaper',  label: 'Get paper',          form: 'getpaper', desc: 'Look up arXiv paper details' },
      { id: 'scholarly', label: 'Scholarly search',   form: 'search',   desc: 'Search Semantic Scholar' },
      { id: 'notebook',  label: 'To notebook',        form: 'notebook', desc: 'Build notebook from sources' },
    ],
  },
  {
    key: 'config', label: 'Config',
    items: [
      { id: 'cfgshow', label: 'Show config',    form: 'cfgshow', desc: 'View current config keys' },
      { id: 'cfgset',  label: 'Set config key', form: 'cfgset',  desc: 'Save a config key/value' },
    ],
  },
];

export const ACTIONS = ACTION_GROUPS;
export const ALL_ACTIONS: ActionMeta[] = ACTION_GROUPS.flatMap(g =>
  g.items.map(it => ({ ...it, group: g.label } as ActionMeta))
);
export const findAction = (id: ActionId): ActionMeta => ALL_ACTIONS.find(a => a.id === id) ?? ALL_ACTIONS[0];
export const BACKENDS = ['Free', 'Feynman', 'Docent', 'Groq'];
// Archived backends (still work via CLI --backend flag):
// 'Gemini', 'OpenRouter', 'Anthropic', 'OpenAI', 'Ollama', 'LM Studio', 'Mistral', 'Cerebras'

// The default AI backend used when 'Free' is excluded (text-generating actions).
export const DEFAULT_AI_BACKEND = 'Docent';

/** Only deep research and literature review support the source-only 'Free' backend.
 *  Text-generating actions (draft/peer/compare/replicate/audit) require an AI backend. */
export function supportsFreeBackend(actionId: ActionId): boolean {
  return actionId === 'deep' || actionId === 'lit';
}

// ── Phases ─────────────────────────────────────────────────────────────────────

export const PHASE_LABELS: Record<string, string> = {
  // generic
  plan: 'Plan', search: 'Search', fetch: 'Fetch', parse: 'Parse',
  synth: 'Synth', save: 'Save', done: 'Done', cost: 'Cost', warn: 'Warn', error: 'Error',
  // free-tier backend
  web_search: 'Web', paper_search: 'Papers', compile: 'Compile',
  // docent pipeline backend
  search_plan: 'Plan', write: 'Write', review: 'Review', refine: 'Refine',
  verify: 'Verify', verify_citations: 'Citations', research: 'Research',
  // action-specific
  compare: 'Compare', analyze: 'Analyze', audit: 'Audit',
  // to-notebook phases
  package: 'Package', 'nlm-check': 'Auth', 'nlm-login': 'Login',
  'nlm-notebook': 'Notebook', 'nlm-push': 'Push', 'nlm-stabilise': 'Stabilise',
  'nlm-quality': 'Quality', 'nlm-poll': 'Poll', 'nlm-wait': 'Waiting',
  // raw subprocess output (CLI passthrough stream)
  console: 'Log',
};

export const PHASE_TONE: Record<string, 'info' | 'warn' | 'error'> = {
  plan: 'info', search: 'info', fetch: 'info', parse: 'info',
  synth: 'info', save: 'info', done: 'info',
  web_search: 'info', paper_search: 'info', compile: 'info',
  search_plan: 'info', write: 'info', review: 'info', refine: 'info',
  verify: 'info', verify_citations: 'info', research: 'info',
  compare: 'info', analyze: 'info', audit: 'info',
  cost: 'warn', warn: 'warn', error: 'error', 'nlm-wait': 'warn',
  console: 'info',
};

// ── CLI command preview ────────────────────────────────────────────────────────

// Frontend action ID → studio CLI action name
const SUBCMD: Record<string, string> = {
  deep: 'deep-research', lit: 'lit', peer: 'review',
  compare: 'compare', draft: 'draft', replicate: 'replicate', audit: 'audit',
  search: 'search-papers', scholarly: 'scholarly-search', getpaper: 'get-paper',
  notebook: 'to-notebook', cfgshow: 'config-show', cfgset: 'config-set',
};

function quoteIfNeeded(v: string | undefined): string {
  const s = String(v ?? '').trim();
  if (!s) return '""';
  return /\s|"|'/.test(s) ? '"' + s.replace(/"/g, '\\"') + '"' : s;
}

export function commandFor(actionId: ActionId, s: FormState): string {
  const sub = SUBCMD[actionId] ?? actionId;
  const parts = ['docent', 'studio', sub];
  const backend = (s.backend ?? '').toLowerCase();
  switch (actionId) {
    case 'deep': case 'lit': case 'draft':
      parts.push('--topic', quoteIfNeeded(s.topic));
      // draft has no free tier — never surface an invalid `--backend free`.
      if (backend && (backend !== 'free' || supportsFreeBackend(actionId))) parts.push('--backend', backend);
      if (s.dest && s.dest !== 'Local') parts.push('--output', s.dest.toLowerCase().replace(' →', '').trim());
      (s.guides ?? []).forEach(g => parts.push('--guide-files', quoteIfNeeded(g)));
      break;
    case 'peer': case 'replicate': case 'audit':
      parts.push('--artifact', quoteIfNeeded(s.artifact));
      if (backend && backend !== 'free') parts.push('--backend', backend);
      (s.guides ?? []).forEach(g => parts.push('--guide-files', quoteIfNeeded(g)));
      break;
    case 'compare':
      parts.push('--artifact-a', quoteIfNeeded(s.artifactA), '--artifact-b', quoteIfNeeded(s.artifactB));
      if (backend && backend !== 'free') parts.push('--backend', backend);
      (s.guides ?? []).forEach(g => parts.push('--guide-files', quoteIfNeeded(g)));
      break;
    case 'search': case 'scholarly':
      parts.push('--query', quoteIfNeeded(s.query), '--max-results', String(s.maxResults ?? 10));
      break;
    case 'getpaper':
      parts.push('--arxiv-id', quoteIfNeeded(s.arxivId));
      break;
    case 'notebook':
      if (s.outPath) parts.push('--output-file', quoteIfNeeded(s.outPath));
      if (s.srcPath) parts.push('--sources-file', quoteIfNeeded(s.srcPath));
      parts.push('--max-sources', String(s.maxSources ?? 20));
      if (!s.nlm)  parts.push('--no-run-nlm-research');
      if (!s.gate) parts.push('--no-run-quality-gate');
      if (!s.persp) parts.push('--no-run-perspectives');
      break;
    case 'cfgset':
      parts.push('--key', quoteIfNeeded(s.cfgKey), '--value', quoteIfNeeded(s.cfgVal));
      break;
  }
  return parts.join(' ');
}

// ── API credit indicator ───────────────────────────────────────────────────────
// Actions that involve no AI synthesis and never touch an API credit budget.
const _NO_CREDIT_ACTIONS = new Set<ActionId>(['search', 'scholarly', 'getpaper', 'cfgshow', 'cfgset']);

/** Returns true when the chosen backend may consume API credits for this action. */
export function usesApiCredits(actionId: ActionId, backend: string): boolean {
  if (backend === 'Free') return false;
  return !_NO_CREDIT_ACTIONS.has(actionId);
}

// ── Labels / helpers ───────────────────────────────────────────────────────────

export function runLabel(action: ActionMeta): string {
  if (action.id === 'search' || action.id === 'scholarly') return 'Search';
  if (action.id === 'getpaper') return 'Look up';
  if (action.id === 'cfgshow')  return 'Show config';
  if (action.id === 'cfgset')   return 'Save';
  if (action.id === 'notebook') return 'Build notebook';
  return `Run ${action.label.toLowerCase()}`;
}

export function actionSummary(action: ActionMeta, s: FormState): string {
  switch (action.id) {
    case 'deep': case 'lit': case 'draft': return s.topic;
    case 'peer': case 'replicate': case 'audit': return s.artifact;
    case 'compare': return `${s.artifactA} vs ${s.artifactB}`;
    case 'search': case 'scholarly': return s.query;
    case 'getpaper': return s.arxivId;
    case 'cfgset': return s.cfgKey;
    case 'notebook': return 'notebook build';
    default: return '';
  }
}
