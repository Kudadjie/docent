// Shared types, constants, and pure functions for the Studio page.
// No React — imported by both _form.tsx and _output.tsx.

export type Status = 'idle' | 'running' | 'success' | 'failure' | 'stopped';
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
      { id: 'replicate', label: 'Replicate',          form: 'artifact', desc: 'Replication audit' },
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
export const BACKENDS = ['Free', 'Feynman', 'Docent', 'Groq', 'Gemini', 'OpenRouter', 'Anthropic', 'OpenAI', 'Ollama', 'LM Studio'];

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
  'nlm-quality': 'Quality', 'nlm-poll': 'Poll',
};

export const PHASE_TONE: Record<string, 'info' | 'warn' | 'error'> = {
  plan: 'info', search: 'info', fetch: 'info', parse: 'info',
  synth: 'info', save: 'info', done: 'info',
  web_search: 'info', paper_search: 'info', compile: 'info',
  search_plan: 'info', write: 'info', review: 'info', refine: 'info',
  verify: 'info', verify_citations: 'info', research: 'info',
  compare: 'info', analyze: 'info', audit: 'info',
  cost: 'warn', warn: 'warn', error: 'error',
};

export const ACTION_PHASES: Record<string, string[]> = {
  deep:      ['plan', 'search', 'fetch', 'parse', 'synth', 'save'],
  lit:       ['plan', 'search', 'fetch', 'parse', 'synth', 'save'],
  peer:      ['plan', 'parse', 'synth', 'save'],
  compare:   ['plan', 'parse', 'synth', 'save'],
  draft:     ['plan', 'search', 'synth', 'save'],
  replicate: ['plan', 'parse', 'synth', 'save'],
  audit:     ['plan', 'parse', 'synth', 'save'],
  notebook:  ['plan', 'fetch', 'parse', 'search', 'synth', 'save'],
  search:    ['search', 'parse', 'save'],
  scholarly: ['search', 'parse', 'save'],
  getpaper:  ['fetch', 'parse', 'synth'],
  cfgshow:   ['save'],
  cfgset:    ['save'],
};

// ── Log scripts ────────────────────────────────────────────────────────────────

export const SCRIPTS: Record<string, LogEntry[]> = {
  deep: [
    { phase: 'plan',   text: 'Decomposing topic into 4 sub-questions' },
    { phase: 'search', text: 'arXiv: 47 candidates; filtering by relevance' },
    { phase: 'search', text: 'Semantic Scholar: 18 candidates' },
    { phase: 'fetch',  text: 'Downloading 12 PDFs in parallel', sources: [
      { title: 'Storm surge attribution under non-stationary sea level rise', year: 2024, src: 'arXiv' },
      { title: 'Bayesian inundation forecasting',                             year: 2023, src: 'JGR' },
      { title: 'Compound flooding from tropical cyclones',                    year: 2022, src: 'Nat. Geo.' },
      { title: 'High-resolution coupled coastal modeling',                    year: 2024, src: 'PNAS' },
      { title: 'Tide-surge-wave interaction in estuaries',                    year: 2021, src: 'Ocean Eng.' },
    ]},
    { phase: 'parse',  text: 'Extracting sections, tables, figures' },
    { phase: 'cost',   text: 'Estimated synthesis cost: $0.42 (~4k tokens)' },
    { phase: 'synth',  text: 'Drafting outline → 7 sections, 18 citations' },
    { phase: 'synth',  text: 'Writing body paragraphs (section 3 of 7)' },
    { phase: 'save',   text: 'Wrote report.md and citations.bib' },
    { phase: 'done',   text: 'Run complete in 4m 12s' },
  ],
  lit: [
    { phase: 'plan',   text: 'Building review skeleton (intro · methods · findings · gaps)' },
    { phase: 'search', text: 'arXiv + Semantic Scholar: 84 candidates' },
    { phase: 'fetch',  text: 'Downloading 18 PDFs', sources: [
      { title: 'Survey of LLM reasoning techniques', year: 2024, src: 'arXiv' },
      { title: 'Chain-of-thought benchmarks',         year: 2023, src: 'NeurIPS' },
      { title: 'Self-consistency for LLM reasoning',  year: 2022, src: 'ICLR' },
    ]},
    { phase: 'parse',  text: 'Clustering papers by methodology' },
    { phase: 'synth',  text: 'Drafting review sections' },
    { phase: 'save',   text: 'Saved literature-review.md' },
    { phase: 'done',   text: 'Run complete in 5m 02s' },
  ],
  peer: [
    { phase: 'plan',   text: 'Reading artifact: 2401.12345' },
    { phase: 'parse',  text: 'Extracting methods, results, claims' },
    { phase: 'synth',  text: 'Cross-checking claims against literature' },
    { phase: 'synth',  text: 'Drafting reviewer comments' },
    { phase: 'save',   text: 'Saved peer-review.md' },
    { phase: 'done',   text: 'Run complete in 3m 18s' },
  ],
  compare: [
    { phase: 'plan',   text: 'Loading artifacts A and B' },
    { phase: 'parse',  text: 'Extracting claims from both papers' },
    { phase: 'synth',  text: 'Aligning methods (jaccard 0.42)' },
    { phase: 'synth',  text: 'Identifying shared & divergent findings' },
    { phase: 'save',   text: 'Saved comparison.md' },
    { phase: 'done',   text: 'Run complete in 6m 47s' },
  ],
  draft: [
    { phase: 'plan',   text: 'Outlining draft sections' },
    { phase: 'search', text: 'Pulling 12 supporting sources' },
    { phase: 'synth',  text: 'Drafting body (1850 words)' },
    { phase: 'save',   text: 'Saved draft.md' },
    { phase: 'done',   text: 'Run complete in 4m 28s' },
  ],
  replicate: [
    { phase: 'plan',   text: 'Reading paper + supplementary materials' },
    { phase: 'parse',  text: 'Identifying replication targets (3 experiments)' },
    { phase: 'synth',  text: 'Drafting replication protocol' },
    { phase: 'save',   text: 'Saved replication-protocol.md' },
    { phase: 'done',   text: 'Run complete in 8m 12s' },
  ],
  audit: [
    { phase: 'plan',   text: 'Loading artifact' },
    { phase: 'parse',  text: 'Inspecting methods & data availability' },
    { phase: 'synth',  text: 'Cross-checking statistics' },
    { phase: 'save',   text: 'Saved audit-report.md' },
    { phase: 'done',   text: 'Run complete in 5m 51s' },
  ],
  notebook: [
    { phase: 'plan',   text: 'Loading sources.json (24 entries)' },
    { phase: 'fetch',  text: 'Resolving DOIs and arXiv IDs' },
    { phase: 'parse',  text: 'Quality gate: scanning for contradictions' },
    { phase: 'search', text: 'NLM web research: 5 supplementary sources' },
    { phase: 'synth',  text: 'Generating perspectives (3 personas)' },
    { phase: 'warn',   text: '2 sources failed quality gate (broken DOI)' },
    { phase: 'save',   text: 'Notebook nb_4f2c updated' },
    { phase: 'done',   text: '18 sources added in 1m 38s' },
  ],
  search: [
    { phase: 'search', text: 'Querying arXiv API' },
    { phase: 'parse',  text: 'Ranking by recency × citation count' },
    { phase: 'save',   text: '5 results' },
  ],
  scholarly: [
    { phase: 'search', text: 'Querying Semantic Scholar' },
    { phase: 'search', text: 'Cross-referencing with arXiv' },
    { phase: 'save',   text: '5 results' },
  ],
  getpaper: [
    { phase: 'fetch',  text: 'Resolving arXiv:2401.12345' },
    { phase: 'parse',  text: 'Extracting abstract and metadata' },
    { phase: 'synth',  text: 'Generating AI overview' },
  ],
  cfgshow: [{ phase: 'save', text: 'Loaded ~/.docent/config.toml' }],
  cfgset:  [{ phase: 'save', text: 'Writing ~/.docent/config.toml' }],
};
export const scriptFor = (id: ActionId): LogEntry[] => SCRIPTS[id] ?? SCRIPTS.deep;

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
      if (backend) parts.push('--backend', backend);
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

// ── Cost estimates ─────────────────────────────────────────────────────────────

const COST_BASE: Record<string, { cost: string; time: string } | null> = {
  deep:      { cost: '$0.42', time: '~5 min' },
  lit:       { cost: '$0.38', time: '~5 min' },
  peer:      { cost: '$0.85', time: '~8 min' },
  compare:   { cost: '$1.10', time: '~10 min' },
  draft:     { cost: '$0.65', time: '~6 min' },
  replicate: { cost: '$1.20', time: '~12 min' },
  audit:     { cost: '$0.95', time: '~9 min' },
  notebook:  { cost: '$0.12', time: '~1 min' },
  search:    { cost: '$0.00', time: '~10s' },
  scholarly: { cost: '$0.00', time: '~10s' },
  getpaper:  { cost: '$0.08', time: '~20s' },
  cfgshow:   null,
  cfgset:    null,
};

export function costEstimate(actionId: ActionId, backend: string): { cost: string; time: string; free: boolean } | null {
  const base = COST_BASE[actionId];
  if (!base) return null;
  if (backend === 'Free') return { cost: 'Free', time: '~2 min', free: true };
  return { ...base, free: false };
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
