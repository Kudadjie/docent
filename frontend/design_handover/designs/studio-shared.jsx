// ─── STUDIO SHARED ────────────────────────────────────────────────────────────
// Constants, theme, icons, data, primitives. Loaded first.

const SANS = "'Inter', system-ui, sans-serif";
const MONO = "'Geist Mono', ui-monospace, monospace";
const BRAND = '#18E299';
const BRAND_DEEP = '#0fa76e';
const BRAND_LIGHT = '#d4fae8';
const AMBER = '#C37D0D';
const AMBER_BORDER = '#F59E0B';
const RED = '#D45656';
const BLUE = '#3772cf';
// Complementary accents — used decoratively (hero washes, phase strips, section dots).
// Same chroma family as brand green; never used for primary CTAs.
const VIOLET = '#8B5CF6';
const PINK = '#EC78A8';

// ─── THEME ────────────────────────────────────────────────────────────────────
function makeTheme(dark) {
  return {
    bg:        dark ? '#0d0d0d' : '#ffffff',
    surface:   dark ? '#111111' : '#fafafa',
    card:      dark ? '#171717' : '#ffffff',
    fg1:       dark ? '#ededed' : '#0d0d0d',
    fg2:       dark ? '#c0c0c0' : '#333333',
    fg3:       dark ? '#a0a0a0' : '#666666',
    fg4:       dark ? '#606060' : '#888888',
    gray100:   dark ? '#1e1e1e' : '#f5f5f5',
    gray200:   dark ? '#2a2a2a' : '#e5e5e5',
    border:    dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
    borderMd:  dark ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.09)',
    logoBorder:dark ? 'rgba(255,255,255,0.22)' : '#0d0d0d',
    rowHover:  dark ? '#1a1a1a' : '#fafafa',
    amberBg:   dark ? 'rgba(245,158,11,0.13)' : '#FFF7ED',
    amberBgStrong: dark ? 'rgba(245,158,11,0.18)' : '#FFEFD5',
    amberText: dark ? '#F5C46B' : '#B45309',
    amberBorder: dark ? 'rgba(245,158,11,0.45)' : AMBER_BORDER,
    redBg:     dark ? 'rgba(212,86,86,0.16)' : '#FEF2F2',
    redText:   dark ? '#F87171' : '#B91C1C',
    blueBg:    dark ? 'rgba(59,130,246,0.14)' : '#EFF6FF',
    blueText:  dark ? '#60A5FA' : '#1D4ED8',
    codeBg:    dark ? '#0a0a0a' : '#fafafa',
    codeBorder:dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)',
    overlay:   dark ? 'rgba(0,0,0,0.55)' : 'rgba(0,0,0,0.25)',
    dark,
  };
}
const ThemeCtx = React.createContext(makeTheme(false));
const useTheme = () => React.useContext(ThemeCtx);

// ─── ICONS ────────────────────────────────────────────────────────────────────
const ico = (paths, size=16, sw=1.5) => () => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">{paths}</svg>
);
const Ico = {
  LayoutDashboard: ico(<>
    <rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/>
    <rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>
  </>),
  BookOpen: ico(<>
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
  </>),
  FlaskConical: ico(<>
    <path d="M10 2v7.31"/><path d="M14 9.3V1.99"/><path d="M8.5 2h7"/>
    <path d="M14 9.3a6.5 6.5 0 1 1-4 0"/><path d="M5.52 16h12.96"/>
  </>),
  Play: ico(<polygon points="6 3 20 12 6 21 6 3"/>, 13, 2),
  Square: ico(<rect x="5" y="5" width="14" height="14" rx="1"/>, 12, 2),
  CheckCircle: ico(<>
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
    <polyline points="22 4 12 14.01 9 11.01"/>
  </>),
  XCircle: ico(<>
    <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/>
    <line x1="9" y1="9" x2="15" y2="15"/>
  </>),
  AlertTriangle: ico(<>
    <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
    <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
  </>, 14, 2),
  Copy: ico(<>
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
  </>, 12, 1.6),
  Plus: ico(<><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></>, 14, 2),
  ChevronDown: ico(<polyline points="6 9 12 15 18 9"/>, 14, 2),
  ChevronRight: ico(<polyline points="9 18 15 12 9 6"/>, 14, 2),
  ChevronLeft: ico(<polyline points="15 18 9 12 15 6"/>, 14, 2),
  ArrowRight: ico(<><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></>, 13, 1.7),
  Search: ico(<><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>, 14),
  ExternalLink: ico(<>
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
    <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
  </>, 12),
  File: ico(<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></>, 13),
  X: ico(<><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>, 12, 2),
  Sun: ico(<>
    <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/>
    <line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/>
    <line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </>, 12, 2),
  Moon: ico(<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>, 12, 2),
  Clock: ico(<><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></>, 13),
  History: ico(<>
    <path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/>
    <line x1="12" y1="7" x2="12" y2="12"/><line x1="12" y1="12" x2="15" y2="14"/>
  </>, 14),
  Command: ico(<path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/>, 12),
  Pin: ico(<>
    <line x1="12" y1="17" x2="12" y2="22"/>
    <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V17z"/>
  </>, 13),
  Upload: ico(<>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
  </>, 13),
  Sparkles: ico(<>
    <path d="M9 3l1.5 4.5L15 9l-4.5 1.5L9 15l-1.5-4.5L3 9l4.5-1.5z"/>
    <path d="M19 13l.8 2.4L22 16l-2.2.6L19 19l-.8-2.4L16 16l2.2-.6z"/>
  </>, 12, 1.4),
  Layers: ico(<>
    <polygon points="12 2 2 7 12 12 22 7 12 2"/>
    <polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>
  </>, 13),
  ArrowDownToLine: ico(<>
    <path d="M12 17V3"/><path d="m6 11 6 6 6-6"/><path d="M19 21H5"/>
  </>, 13),
  Bookmark: ico(<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>, 13),
  Trash: ico(<>
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
  </>, 12),
  Pipe: ico(<>
    <path d="M3 12h6"/><path d="M15 12h6"/>
    <rect x="9" y="8" width="6" height="8" rx="1"/>
  </>, 13),
  Boxes: ico(<>
    <path d="M2.97 12.92A2 2 0 0 0 2 14.63v3.24a2 2 0 0 0 .97 1.71l3 1.8a2 2 0 0 0 2.06 0L11 19.61"/>
    <path d="m7 16.5-4.74-2.85"/><path d="m7 16.5 5-3"/><path d="M7 16.5v5.17"/>
    <path d="M12 13.63V8.37a2 2 0 0 0-.97-1.71l-3-1.8a2 2 0 0 0-2.06 0l-3 1.8A2 2 0 0 0 2 8.37v3.24"/>
    <path d="m17 16.5-5-3"/><path d="m17 16.5 4.74-2.85"/><path d="M17 16.5v5.17"/>
    <path d="M22 14.63v3.24a2 2 0 0 1-.97 1.71l-3 1.8a2 2 0 0 1-2.06 0L13 19.61"/>
  </>),
  Github: ico(<path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>, 13),
  Terminal: ico(<><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></>, 13),
  Package: ico(<>
    <path d="m7.5 4.27 9 5.15"/>
    <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/>
    <path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>
  </>),
  Book: ico(<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>),
  Cpu: ico(<>
    <rect x="4" y="4" width="16" height="16" rx="2" ry="2"/>
    <rect x="9" y="9" width="6" height="6"/>
    <line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/>
    <line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/>
    <line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/>
    <line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>
  </>),
};

// ─── ACTIONS ──────────────────────────────────────────────────────────────────
const ACTIONS = {
  research: {
    label: 'Research',
    items: [
      { id:'deep',     label:'Deep research',     form:'topic',    desc:'Multi-source synthesis on a topic' },
      { id:'lit',      label:'Literature review', form:'topic',    desc:'Structured review of the field' },
      { id:'peer',     label:'Peer review',       form:'artifact', desc:'Critique a single paper' },
      { id:'compare',  label:'Compare',           form:'compare',  desc:'Side-by-side analysis of two papers' },
      { id:'draft',    label:'Draft',             form:'topic',    desc:'Draft a writeup from sources' },
      { id:'replicate',label:'Replicate',         form:'artifact', desc:'Replication audit' },
      { id:'audit',    label:'Audit',             form:'artifact', desc:'Methods + evidence audit' },
    ],
  },
  utilities: {
    label: 'Utilities',
    items: [
      { id:'search',     label:'Search papers',    form:'search',   desc:'Search arXiv' },
      { id:'getpaper',   label:'Get paper',        form:'getpaper', desc:'Look up arXiv paper details' },
      { id:'scholarly',  label:'Scholarly search', form:'search',   desc:'Search Semantic Scholar' },
      { id:'notebook',   label:'To notebook',      form:'notebook', desc:'Build notebook from sources' },
    ],
  },
  config: {
    label: 'Config',
    items: [
      { id:'cfgshow', label:'Show config',    form:'cfgshow', desc:'View current config keys' },
      { id:'cfgset',  label:'Set config key', form:'cfgset',  desc:'Save a config key/value' },
    ],
  },
};
const ALL_ACTIONS = Object.values(ACTIONS).flatMap(g => g.items.map(it => ({ ...it, group: g.label })));
const findAction = (id) => ALL_ACTIONS.find(a => a.id === id) || ALL_ACTIONS[0];
const BACKENDS = ['Free','Feynman','Docent','Groq','Gemini','OpenRouter','Anthropic','OpenAI','Ollama','LM Studio'];

// ─── PHASES ───────────────────────────────────────────────────────────────────
const PHASE_LABELS = {
  plan:'Plan', search:'Search', fetch:'Fetch', parse:'Parse',
  synth:'Synth', save:'Save', done:'Done', cost:'Cost', warn:'Warn', error:'Error',
};
const PHASE_TONE = {
  info:'info', plan:'info', search:'info', fetch:'info', parse:'info',
  synth:'info', save:'info', done:'info',
  warn:'warn', cost:'warn',
  error:'error',
};
const ACTION_PHASES = {
  deep:      ['plan','search','fetch','parse','synth','save'],
  lit:       ['plan','search','fetch','parse','synth','save'],
  peer:      ['plan','parse','synth','save'],
  compare:   ['plan','parse','synth','save'],
  draft:     ['plan','search','synth','save'],
  replicate: ['plan','parse','synth','save'],
  audit:     ['plan','parse','synth','save'],
  notebook:  ['plan','fetch','parse','search','synth','save'],
  search:    ['search','parse','save'],
  scholarly: ['search','parse','save'],
  getpaper:  ['fetch','parse','synth'],
  cfgshow:   ['save'],
  cfgset:    ['save'],
};

// ─── LOG SCRIPTS ──────────────────────────────────────────────────────────────
const SCRIPTS = {
  deep: [
    { phase:'plan',   text:'Decomposing topic into 4 sub-questions' },
    { phase:'search', text:'arXiv: 47 candidates; filtering by relevance' },
    { phase:'search', text:'Semantic Scholar: 18 candidates' },
    { phase:'fetch',  text:'Downloading 12 PDFs in parallel', sources:[
      { title:'Storm surge attribution under non-stationary sea level rise', year:2024, src:'arXiv' },
      { title:'Bayesian inundation forecasting', year:2023, src:'JGR' },
      { title:'Compound flooding from tropical cyclones', year:2022, src:'Nat. Geo.' },
      { title:'High-resolution coupled coastal modeling', year:2024, src:'PNAS' },
      { title:'Tide-surge-wave interaction in estuaries', year:2021, src:'Ocean Eng.' },
      { title:'Storm surge ensemble forecasting', year:2023, src:'AGU' },
      { title:'Sea level rise & extreme events', year:2022, src:'Nature' },
      { title:'Coastal flooding probability metrics', year:2024, src:'JGR' },
    ]},
    { phase:'parse',  text:'Extracting sections, tables, figures' },
    { phase:'cost',   text:'Estimated synthesis cost: $0.42 (~4k tokens)' },
    { phase:'synth',  text:'Drafting outline → 7 sections, 18 citations' },
    { phase:'synth',  text:'Writing body paragraphs (section 3 of 7)' },
    { phase:'save',   text:'Wrote report.md and citations.bib' },
    { phase:'done',   text:'Run complete in 4m 12s' },
  ],
  lit: [
    { phase:'plan',   text:'Building review skeleton (intro · methods · findings · gaps)' },
    { phase:'search', text:'arXiv + Semantic Scholar: 84 candidates' },
    { phase:'fetch',  text:'Downloading 18 PDFs', sources:[
      { title:'Survey of LLM reasoning techniques', year:2024, src:'arXiv' },
      { title:'Chain-of-thought benchmarks', year:2023, src:'NeurIPS' },
      { title:'Self-consistency for LLM reasoning', year:2022, src:'ICLR' },
    ]},
    { phase:'parse',  text:'Clustering papers by methodology' },
    { phase:'synth',  text:'Drafting review sections' },
    { phase:'save',   text:'Saved literature-review.md' },
    { phase:'done',   text:'Run complete in 5m 02s' },
  ],
  peer: [
    { phase:'plan',   text:'Reading artifact: 2401.12345' },
    { phase:'parse',  text:'Extracting methods, results, claims' },
    { phase:'synth',  text:'Cross-checking claims against literature' },
    { phase:'synth',  text:'Drafting reviewer comments' },
    { phase:'save',   text:'Saved peer-review.md' },
    { phase:'done',   text:'Run complete in 3m 18s' },
  ],
  compare: [
    { phase:'plan',   text:'Loading artifacts A and B' },
    { phase:'parse',  text:'Extracting claims from both papers' },
    { phase:'synth',  text:'Aligning methods (jaccard 0.42)' },
    { phase:'synth',  text:'Identifying shared & divergent findings' },
    { phase:'save',   text:'Saved comparison.md' },
    { phase:'done',   text:'Run complete in 6m 47s' },
  ],
  draft: [
    { phase:'plan',   text:'Outlining draft sections' },
    { phase:'search', text:'Pulling 12 supporting sources' },
    { phase:'synth',  text:'Drafting body (1850 words)' },
    { phase:'save',   text:'Saved draft.md' },
    { phase:'done',   text:'Run complete in 4m 28s' },
  ],
  replicate: [
    { phase:'plan',   text:'Reading paper + supplementary materials' },
    { phase:'parse',  text:'Identifying replication targets (3 experiments)' },
    { phase:'synth',  text:'Drafting replication protocol' },
    { phase:'save',   text:'Saved replication-protocol.md' },
    { phase:'done',   text:'Run complete in 8m 12s' },
  ],
  audit: [
    { phase:'plan',   text:'Loading artifact' },
    { phase:'parse',  text:'Inspecting methods & data availability' },
    { phase:'synth',  text:'Cross-checking statistics' },
    { phase:'save',   text:'Saved audit-report.md' },
    { phase:'done',   text:'Run complete in 5m 51s' },
  ],
  notebook: [
    { phase:'plan',   text:'Loading sources.json (24 entries)' },
    { phase:'fetch',  text:'Resolving DOIs and arXiv IDs' },
    { phase:'parse',  text:'Quality gate: scanning for contradictions' },
    { phase:'search', text:'NLM web research: 5 supplementary sources' },
    { phase:'synth',  text:'Generating perspectives (3 personas)' },
    { phase:'warn',   text:'2 sources failed quality gate (broken DOI)' },
    { phase:'save',   text:'Notebook nb_4f2c updated' },
    { phase:'done',   text:'18 sources added in 1m 38s' },
  ],
  search: [
    { phase:'search', text:'Querying arXiv API' },
    { phase:'parse',  text:'Ranking by recency × citation count' },
    { phase:'save',   text:'5 results' },
  ],
  scholarly: [
    { phase:'search', text:'Querying Semantic Scholar' },
    { phase:'search', text:'Cross-referencing with arXiv' },
    { phase:'save',   text:'5 results' },
  ],
  getpaper: [
    { phase:'fetch',  text:'Resolving arXiv:2401.12345' },
    { phase:'parse',  text:'Extracting abstract and metadata' },
    { phase:'synth',  text:'Generating AI overview' },
  ],
  cfgshow: [{ phase:'save', text:'Loaded ~/.docent/config.toml' }],
  cfgset:  [{ phase:'save', text:'Writing ~/.docent/config.toml' }],
};
const scriptFor = (id) => SCRIPTS[id] || SCRIPTS.deep;

// ─── COMMAND PREVIEW ─────────────────────────────────────────────────────────
const SUBCMD = {
  deep:'deep-research', lit:'lit-review', peer:'peer-review',
  compare:'compare', draft:'draft', replicate:'replicate', audit:'audit',
  search:'search', scholarly:'scholarly-search', getpaper:'get-paper',
  notebook:'to-notebook', cfgshow:'config show', cfgset:'config set',
};
function quoteIfNeeded(v) {
  v = String(v ?? '').trim();
  if (!v) return '""';
  return /\s|"|'/.test(v) ? '"' + v.replace(/"/g, '\\"') + '"' : v;
}
function commandFor(actionId, s) {
  const sub = SUBCMD[actionId] || actionId;
  const parts = ['docent', sub];
  const backend = (s.backend || '').toLowerCase();
  switch (actionId) {
    case 'deep': case 'lit': case 'draft':
      parts.push('--topic', quoteIfNeeded(s.topic));
      if (backend) parts.push('--backend', backend);
      if (s.dest && s.dest !== 'Local') parts.push('--out', s.dest.toLowerCase());
      if (s.dest === 'Pipe →') parts.push('--pipe', 'notebook');
      (s.guides||[]).forEach(g => parts.push('--guide', quoteIfNeeded(g)));
      break;
    case 'peer': case 'replicate': case 'audit':
      parts.push(quoteIfNeeded(s.artifact));
      if (backend && backend !== 'free') parts.push('--backend', backend);
      (s.guides||[]).forEach(g => parts.push('--guide', quoteIfNeeded(g)));
      break;
    case 'compare':
      parts.push(quoteIfNeeded(s.artifactA), quoteIfNeeded(s.artifactB));
      if (backend && backend !== 'free') parts.push('--backend', backend);
      (s.guides||[]).forEach(g => parts.push('--guide', quoteIfNeeded(g)));
      break;
    case 'search': case 'scholarly':
      parts.push(quoteIfNeeded(s.query));
      parts.push('--max', String(s.maxResults || 10));
      break;
    case 'getpaper':
      parts.push(quoteIfNeeded(s.arxivId));
      break;
    case 'notebook':
      if (s.outPath) parts.push('--output', quoteIfNeeded(s.outPath));
      if (s.srcPath) parts.push('--sources', quoteIfNeeded(s.srcPath));
      parts.push('--max-sources', String(s.maxSources || 20));
      if (!s.nlm) parts.push('--no-nlm');
      if (!s.gate) parts.push('--no-quality-gate');
      if (!s.persp) parts.push('--no-perspectives');
      break;
    case 'cfgset':
      parts.push(quoteIfNeeded(s.cfgKey), quoteIfNeeded(s.cfgVal));
      break;
    case 'cfgshow':
      break;
  }
  return parts.join(' ');
}

// ─── COST ESTIMATE ────────────────────────────────────────────────────────────
const COST_BASE = {
  deep:      { cost:'$0.42', time:'~5 min' },
  lit:       { cost:'$0.38', time:'~5 min' },
  peer:      { cost:'$0.85', time:'~8 min' },
  compare:   { cost:'$1.10', time:'~10 min' },
  draft:     { cost:'$0.65', time:'~6 min' },
  replicate: { cost:'$1.20', time:'~12 min' },
  audit:     { cost:'$0.95', time:'~9 min' },
  notebook:  { cost:'$0.12', time:'~1 min' },
  search:    { cost:'$0.00', time:'~10s' },
  scholarly: { cost:'$0.00', time:'~10s' },
  getpaper:  { cost:'$0.08', time:'~20s' },
  cfgshow:   null,
  cfgset:    null,
};
function costEstimate(actionId, backend) {
  const base = COST_BASE[actionId];
  if (!base) return null;
  if (backend === 'Free') return { cost:'Free', time:'~2 min', tone:'info' };
  return { ...base, tone:'info' };
}

// ─── PRIMITIVES ───────────────────────────────────────────────────────────────
function PrimaryBtn({ icon, children, onClick, disabled, full, size='md' }) {
  const pad = size === 'sm' ? '6px 14px' : '9px 18px';
  const fs = size === 'sm' ? 12.5 : 13;
  return (
    <button onClick={onClick} disabled={disabled} className="tap"
      style={{ display:'inline-flex', alignItems:'center', justifyContent:'center', gap:7,
        padding:pad, borderRadius:9999, background: disabled ? '#a8e8cf' : BRAND,
        color:'#0d0d0d', fontFamily:SANS, fontSize:fs, fontWeight:600, border:'none',
        cursor: disabled?'not-allowed':'pointer', width: full?'100%':'auto',
        opacity: disabled?0.7:1 }}>
      {icon}{children}
    </button>
  );
}

function GhostBtn({ icon, children, onClick, size='md', danger, active }) {
  const T = useTheme();
  const [hov, setHov] = React.useState(false);
  const pad = size === 'sm' ? '4px 10px' : '5px 12px';
  return (
    <button onMouseEnter={()=>setHov(true)} onMouseLeave={()=>setHov(false)} onClick={onClick}
      style={{ display:'inline-flex', alignItems:'center', gap:6, padding:pad, borderRadius:9999,
        border:`1px solid ${active ? BRAND : T.borderMd}`,
        background: active ? BRAND+'1a' : (hov ? T.gray100 : 'transparent'),
        color: danger ? RED : (active ? BRAND_DEEP : T.fg2),
        fontFamily:SANS, fontSize:13, fontWeight:500,
        cursor:'pointer', transition:'background 0.12s', whiteSpace:'nowrap' }}>
      {icon && <span style={{ color: danger ? RED : (active ? BRAND_DEEP : T.fg4), display:'flex' }}>{icon}</span>}
      {children}
    </button>
  );
}

function PillToggle({ active, onClick, disabled, tooltip, children }) {
  const T = useTheme();
  const [hov, setHov] = React.useState(false);
  return (
    <button onClick={disabled?null:onClick} onMouseEnter={()=>setHov(true)} onMouseLeave={()=>setHov(false)}
      title={tooltip}
      style={{ padding:'5px 12px', borderRadius:9999,
        border: active ? `1px solid ${BRAND}` : `1px solid ${T.borderMd}`,
        background: active ? BRAND : (hov && !disabled ? T.gray100 : 'transparent'),
        color: active ? '#0d0d0d' : (disabled ? T.fg4 : T.fg2),
        fontFamily:SANS, fontSize:12, fontWeight:500,
        cursor: disabled?'not-allowed':'pointer', opacity:disabled?0.55:1,
        transition:'all 0.12s', whiteSpace:'nowrap' }}>
      {children}
    </button>
  );
}

function Segmented({ value, onChange, options }) {
  const T = useTheme();
  return (
    <div style={{ display:'inline-flex', padding:2, background:T.gray100, borderRadius:9999,
        border:`1px solid ${T.border}` }}>
      {options.map(opt => {
        const active = opt === value;
        return (
          <button key={opt} onClick={()=>onChange(opt)}
            style={{ padding:'4px 14px', borderRadius:9999, border:'none',
              background: active ? T.bg : 'transparent',
              color: active ? T.fg1 : T.fg3,
              fontFamily:SANS, fontSize:12, fontWeight: active?500:400, cursor:'pointer',
              transition:'all 0.12s',
              boxShadow: active ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
              display:'inline-flex', alignItems:'center', gap:5 }}>{opt}</button>
        );
      })}
    </div>
  );
}

function Input({ value, onChange, placeholder, type='text', mono, autoFocus }) {
  const T = useTheme();
  const [focus, setFocus] = React.useState(false);
  return (
    <input type={type} value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder}
      autoFocus={autoFocus}
      onFocus={()=>setFocus(true)} onBlur={()=>setFocus(false)}
      style={{ width:'100%', padding:'8px 12px',
        border:`1px solid ${focus?BRAND:T.borderMd}`, borderRadius:8,
        fontFamily: mono ? MONO : SANS, fontSize:13, color:T.fg1, background:T.bg,
        outline:'none', transition:'border-color 0.15s' }} />
  );
}

function Label({ children, hint }) {
  const T = useTheme();
  return (
    <label style={{ display:'block', marginBottom:6, fontFamily:SANS, fontSize:12,
        fontWeight:500, color:T.fg3 }}>
      {children}
      {hint && <span style={{ color:T.fg4, fontWeight:400, marginLeft:6 }}>{hint}</span>}
    </label>
  );
}
function Field({ label, hint, children }) {
  return <div><Label hint={hint}>{label}</Label>{children}</div>;
}

function Note({ tone='info', children, icon }) {
  const T = useTheme();
  const bg = tone === 'warn' ? T.amberBg : 'transparent';
  const text = tone === 'warn' ? T.amberText : T.fg3;
  return (
    <div style={{ fontFamily:SANS, fontSize:11.5, color:text, padding: tone==='warn'?'7px 10px':'4px 0',
        borderRadius:6, background:bg,
        borderLeft: tone==='warn' ? `2px solid ${T.amberBorder}` : 'none',
        marginTop:8, lineHeight:1.5, display:'flex', alignItems:'center', gap:6 }}>
      {icon && <span style={{ display:'flex' }}>{icon}</span>}
      <span>{children}</span>
    </div>
  );
}

function Toggle({ checked, onChange }) {
  const T = useTheme();
  return (
    <button onClick={()=>onChange(!checked)}
      style={{ width:30, height:18, borderRadius:9999, border:'none',
        background: checked ? BRAND : T.gray200,
        position:'relative', cursor:'pointer', padding:0,
        transition:'background 0.15s', flexShrink:0 }}>
      <span style={{ position:'absolute', top:2, left: checked?14:2,
        width:14, height:14, borderRadius:'50%', background:'#fff',
        boxShadow:'0 1px 2px rgba(0,0,0,0.2)', transition:'left 0.15s' }} />
    </button>
  );
}

function Stepper({ value, onChange, min=1, max=99 }) {
  const T = useTheme();
  return (
    <div style={{ display:'inline-flex', alignItems:'center',
        border:`1px solid ${T.borderMd}`, borderRadius:8, overflow:'hidden', background:T.bg }}>
      <button onClick={()=>onChange(Math.max(min, value-1))}
        style={{ width:28, height:30, border:'none', background:'transparent', cursor:'pointer',
          color:T.fg3, fontSize:16, fontFamily:SANS }}>−</button>
      <div style={{ width:36, textAlign:'center', fontFamily:MONO, fontSize:12,
          color:T.fg1, fontWeight:500, borderLeft:`1px solid ${T.border}`,
          borderRight:`1px solid ${T.border}`, padding:'7px 0' }}>{value}</div>
      <button onClick={()=>onChange(Math.min(max, value+1))}
        style={{ width:28, height:30, border:'none', background:'transparent', cursor:'pointer',
          color:T.fg3, fontSize:14, fontFamily:SANS }}>+</button>
    </div>
  );
}

function CodeBlock({ children, mono=true, small }) {
  const T = useTheme();
  const [copied, setCopied] = React.useState(false);
  const text = typeof children === 'string' ? children : '';
  return (
    <div style={{ position:'relative', background:T.codeBg,
        border:`1px solid ${T.codeBorder}`, borderRadius:8,
        padding: small ? '7px 32px 7px 10px' : '10px 36px 10px 12px',
        fontFamily: mono?MONO:SANS, fontSize: small?11:11.5, color:T.fg2,
        lineHeight:1.55, letterSpacing:'0.2px', wordBreak:'break-all',
        whiteSpace:'pre-wrap' }}>
      {children}
      <button onClick={()=>{ if(text){ navigator.clipboard?.writeText(text); setCopied(true); setTimeout(()=>setCopied(false),1200);} }}
        title="Copy"
        style={{ position:'absolute', top: small?4:6, right: small?4:6,
          width: small?22:24, height: small?22:24, borderRadius:6,
          border:'none', background:'transparent',
          color: copied ? BRAND_DEEP : T.fg4, cursor:'pointer',
          display:'flex', alignItems:'center', justifyContent:'center' }}>
        {copied ? <Ico.CheckCircle/> : <Ico.Copy/>}
      </button>
    </div>
  );
}

function Chip({ color, children, icon }) {
  const T = useTheme();
  return (
    <span style={{ display:'inline-flex', alignItems:'center', gap:5,
        padding:'4px 10px', borderRadius:9999,
        background: color ? color+'1f' : T.gray100,
        color: color || T.fg2,
        fontFamily:MONO, fontSize:11, fontWeight:600, letterSpacing:'0.4px',
        textTransform:'uppercase' }}>
      {icon && <span style={{ display:'flex' }}>{icon}</span>}
      {children}
    </span>
  );
}

function Kbd({ children }) {
  const T = useTheme();
  return (
    <span style={{ display:'inline-flex', alignItems:'center', justifyContent:'center',
        minWidth:18, height:18, padding:'0 5px',
        background: T.gray100, border:`1px solid ${T.borderMd}`, borderRadius:4,
        fontFamily:MONO, fontSize:10, color:T.fg3, fontWeight:500 }}>{children}</span>
  );
}

// ─── HERO WASH ────────────────────────────────────────────────────────────────
// Atmospheric multi-color gradient backdrop for page headers.
// Subtle in light mode, dimmer in dark mode. Pass `tones=[c1,c2,c3]` to vary.
function HeroWash({ tones, height=320, opacity, children }) {
  const T = useTheme();
  const [c1, c2, c3] = tones || [BRAND, BLUE, VIOLET];
  const a = opacity || (T.dark ? 0.18 : 0.22);
  const a2 = T.dark ? 0.10 : 0.14;
  const a3 = T.dark ? 0.07 : 0.10;
  const bg = `
    radial-gradient(ellipse 760px 360px at 12% -10%, ${c1}${Math.round(a*255).toString(16).padStart(2,'0')}, transparent 60%),
    radial-gradient(ellipse 600px 320px at 85% 0%,   ${c2}${Math.round(a2*255).toString(16).padStart(2,'0')}, transparent 60%),
    radial-gradient(ellipse 520px 280px at 50% 30%,  ${c3}${Math.round(a3*255).toString(16).padStart(2,'0')}, transparent 60%)
  `;
  return (
    <div style={{ position:'relative' }}>
      <div aria-hidden="true" style={{ position:'absolute', inset:'0 0 auto 0',
        height, pointerEvents:'none', background:bg, zIndex:0 }} />
      <div style={{ position:'relative', zIndex:1 }}>{children}</div>
    </div>
  );
}

// ─── DOCENT WORDMARK ──────────────────────────────────────────────────────────
function DocentWordmark() {
  const T = useTheme();
  const src = T.dark ? '../assets/logo-light.svg' : '../assets/logo.svg';
  return <img src={src} alt="Docent" style={{ height:24, display:'block' }} />;
}
function StatusIndicator({ dotState='idle' }) {
  const T = useTheme();
  const dotColor = { idle:BRAND, working:'#F5A623', error:'#E53535', done:BRAND }[dotState];
  const dotAnim = dotState === 'working' ? 'logo-dot-blink 1s step-end infinite'
                : dotState === 'error'   ? 'logo-dot-blink 0.7s step-end infinite' : 'none';
  return (
    <div style={{ height:24, display:'inline-flex', alignItems:'center', padding:'0 9px', gap:6,
        borderRadius:9999, border:`1.5px solid ${T.logoBorder}`, background:T.bg }}>
      <span style={{ width:6, height:6, borderRadius:'50%', background:dotColor,
        animation:dotAnim }} />
      <span style={{ fontFamily:SANS, fontSize:11.5, fontWeight:600, color:T.fg1,
        letterSpacing:'-0.2px', lineHeight:1 }}>docent</span>
    </div>
  );
}

// ─── SIDEBAR ──────────────────────────────────────────────────────────────────
function Sidebar({ active, currentRun }) {
  const T = useTheme();
  const items = [
    { id:'dashboard', label:'Dashboard', Icon: Ico.LayoutDashboard, count:null },
    { id:'reading',   label:'Reading',   Icon: Ico.BookOpen,        count:12 },
    { id:'studio',    label:'Studio',    Icon: Ico.FlaskConical,    count:null },
    { id:'ecosystem', label:'Ecosystem', Icon: Ico.Boxes,           count:null },
  ];
  const runningPhase = currentRun && currentRun.status === 'running' ? currentRun.currentPhase : null;
  return (
    <aside style={{ width:220, flexShrink:0, height:'100%',
        borderRight:`1px solid ${T.border}`, background:T.bg,
        display:'flex', flexDirection:'column', overflow:'hidden' }}>
      <div style={{ height:56, display:'flex', alignItems:'center', padding:'0 18px',
          borderBottom:`1px solid ${T.border}`, flexShrink:0 }}>
        <DocentWordmark />
      </div>
      <nav style={{ flex:1, padding:'10px 8px', display:'flex', flexDirection:'column', gap:2 }}>
        {items.map(({ id, label, Icon, count }) => {
          const isActive = id === active;
          const isStudio = id === 'studio';
          return (
            <button key={id}
              style={{ width:'100%', display:'flex', alignItems:'center', gap:9,
                padding:'7px 10px', borderRadius:8, border:'none', cursor:'pointer',
                fontFamily:SANS, fontSize:13, fontWeight: isActive?500:400,
                color: isActive ? BRAND_DEEP : T.fg3,
                background: isActive ? BRAND+'22' : 'transparent',
                transition:'background 0.1s, color 0.1s', textAlign:'left' }}>
              <span style={{ color: isActive ? BRAND_DEEP : T.fg4, display:'flex', flexShrink:0 }}>
                <Icon/>
              </span>
              {label}
              {isStudio && runningPhase ? (
                <span style={{ marginLeft:'auto', display:'inline-flex', alignItems:'center', gap:5,
                  fontFamily:MONO, fontSize:9, color:T.amberText, background:T.amberBg,
                  padding:'2px 7px', borderRadius:9999, letterSpacing:'0.3px', textTransform:'uppercase',
                  fontWeight:600 }}>
                  <span style={{ width:5, height:5, borderRadius:'50%', background:AMBER_BORDER,
                    animation:'logo-dot-blink 0.9s step-end infinite' }}/>
                  {runningPhase}
                </span>
              ) : isActive && count != null && (
                <span style={{ marginLeft:'auto', fontFamily:MONO, fontSize:9,
                  color:BRAND_DEEP, background:BRAND+'33', padding:'1px 6px',
                  borderRadius:9999, letterSpacing:'0.3px', textTransform:'uppercase',
                  fontWeight:600 }}>{count}</span>
              )}
            </button>
          );
        })}
      </nav>
      <div style={{ padding:'12px 18px', borderTop:`1px solid ${T.border}`,
          display:'flex', alignItems:'center', gap:8 }}>
        <div style={{ width:28, height:28, borderRadius:'50%', background:BRAND+'22',
            color:BRAND_DEEP, display:'flex', alignItems:'center', justifyContent:'center',
            fontFamily:SANS, fontSize:12, fontWeight:600, flexShrink:0 }}>A</div>
        <div>
          <div style={{ fontFamily:SANS, fontSize:12, fontWeight:500, color:T.fg1 }}>Alex R.</div>
          <div style={{ fontFamily:SANS, fontSize:11, color:T.fg4 }}>alex@lab.edu</div>
        </div>
      </div>
    </aside>
  );
}

// ─── STATUS BANNER ────────────────────────────────────────────────────────────
function StatusBanner({ dark, setDark, onOpenCmdK, onOpenHistory, historyOpen, runCount }) {
  const T = useTheme();
  const stats = [
    { label:'QUEUE', value:12 }, { label:'DATABASE', value:45 }, { label:'MENDELEY', value:40 },
  ];
  return (
    <div style={{ height:40, flexShrink:0, background:T.surface,
        borderBottom:`1px solid ${T.border}`, display:'flex', alignItems:'center',
        padding:'0 16px 0 24px', gap:16 }}>
      {stats.map(({ label, value }) => (
        <div key={label} style={{ display:'flex', alignItems:'center', gap:7 }}>
          <span style={{ fontFamily:MONO, fontSize:10, fontWeight:500, color:T.fg4,
            letterSpacing:'0.7px', textTransform:'uppercase' }}>{label}</span>
          <span style={{ fontFamily:MONO, fontSize:11, fontWeight:600, color:T.fg1,
            letterSpacing:'0.4px' }}>{value}</span>
        </div>
      ))}
      <div style={{ flex:1 }} />

      <button onClick={onOpenCmdK}
        style={{ display:'inline-flex', alignItems:'center', gap:8, padding:'3px 8px 3px 10px',
          borderRadius:9999, border:`1px solid ${T.borderMd}`, background:'transparent',
          cursor:'pointer', color:T.fg3, fontFamily:SANS, fontSize:11 }}>
        <Ico.Search/>
        <span>Quick action</span>
        <span style={{ display:'inline-flex', gap:2 }}>
          <Kbd>⌘</Kbd><Kbd>K</Kbd>
        </span>
      </button>

      {onOpenHistory && (
        <button onClick={onOpenHistory}
          title="Run history"
          style={{ display:'inline-flex', alignItems:'center', gap:5, padding:'3px 9px',
            borderRadius:9999, border:`1px solid ${historyOpen?BRAND:T.borderMd}`,
            background: historyOpen ? BRAND+'1a' : 'transparent', cursor:'pointer',
            color: historyOpen ? BRAND_DEEP : T.fg3,
            fontFamily:MONO, fontSize:10, letterSpacing:'0.5px', textTransform:'uppercase' }}>
          <Ico.History/>
          History
          {runCount > 0 && <span style={{ color: historyOpen ? BRAND_DEEP : T.fg4 }}>· {runCount}</span>}
        </button>
      )}

      <button onClick={()=>setDark(!dark)}
        style={{ display:'flex', alignItems:'center', gap:5, padding:'3px 10px',
          borderRadius:9999, border:`1px solid ${T.borderMd}`, background:'transparent',
          cursor:'pointer', fontFamily:MONO, fontSize:10, letterSpacing:'0.5px',
          textTransform:'uppercase', color:T.fg3 }}>
        {dark ? <Ico.Sun/> : <Ico.Moon/>}
        {dark ? 'Light' : 'Dark'}
      </button>
      <div style={{ display:'flex', alignItems:'center', gap:8 }}>
        <span style={{ fontFamily:MONO, fontSize:10, color:T.fg4,
          letterSpacing:'0.5px', textTransform:'uppercase' }}>Synced 2m ago</span>
        <StatusIndicator dotState="idle" />
      </div>
    </div>
  );
}

// ─── EXPORT ALL TO WINDOW ─────────────────────────────────────────────────────
Object.assign(window, {
  // constants
  SANS, MONO, BRAND, BRAND_DEEP, BRAND_LIGHT, AMBER, AMBER_BORDER, RED, BLUE, VIOLET, PINK,
  // theme
  makeTheme, ThemeCtx, useTheme,
  // icons
  Ico,
  // data
  ACTIONS, ALL_ACTIONS, findAction, BACKENDS,
  PHASE_LABELS, PHASE_TONE, ACTION_PHASES, SCRIPTS, scriptFor,
  SUBCMD, commandFor, COST_BASE, costEstimate,
  // primitives
  PrimaryBtn, GhostBtn, PillToggle, Segmented, Input, Label, Field, Note,
  Toggle, Stepper, CodeBlock, Chip, Kbd,
  // chrome
  DocentWordmark, StatusIndicator, Sidebar, StatusBanner, HeroWash,
});
