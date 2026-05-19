// ─── STUDIO OUTPUT (RIGHT COLUMN) ─────────────────────────────────────────────
// Output panel + phase strip + source chips + log + result variants + history drawer

const {
  SANS, MONO, BRAND, BRAND_DEEP, AMBER, AMBER_BORDER, RED, BLUE, VIOLET, PINK,
  useTheme, Ico,
  ACTION_PHASES, PHASE_LABELS, PHASE_TONE, findAction,
  PrimaryBtn, GhostBtn, Chip, CodeBlock, Label, Kbd,
} = window;

// Per-phase identity colors — each phase gets its own hue so the phase strip
// reads as a small rainbow rather than a wall of green.
const PHASE_COLOR = {
  plan:   VIOLET,
  search: BLUE,
  fetch:  AMBER_BORDER,
  parse:  PINK,
  synth:  BRAND,
  save:   BRAND_DEEP,
  done:   BRAND_DEEP,
  cost:   AMBER_BORDER,
  warn:   AMBER_BORDER,
  error:  '#E53535',
};

// ─── PHASE STRIP ──────────────────────────────────────────────────────────────
function PhaseStrip({ actionId, completedPhases, currentPhase, status }) {
  const T = useTheme();
  const phases = ACTION_PHASES[actionId] || [];
  if (phases.length <= 1) return null;
  return (
    <div style={{ display:'flex', alignItems:'center', gap:0, padding:'10px 0' }}>
      {phases.map((p, i) => {
        const done = completedPhases.has(p);
        const current = p === currentPhase && status === 'running';
        const phaseHue = PHASE_COLOR[p] || BRAND;

        const dotColor   = current ? phaseHue : done ? phaseHue : T.gray200;
        const labelColor = current ? phaseHue : done ? T.fg2    : T.fg4;
        // Connecting line blends from this dot's color toward the next.
        const nextHue = PHASE_COLOR[phases[i+1]] || phaseHue;
        const showLine = done || (current && i > 0);
        const lineBg = showLine
          ? `linear-gradient(90deg, ${phaseHue}aa, ${nextHue}66)`
          : T.border;
        return (
          <React.Fragment key={p}>
            <div style={{ display:'flex', alignItems:'center', gap:6, flexShrink:0 }}>
              <span style={{ width:done?7:current?9:7, height:done?7:current?9:7, borderRadius:'50%',
                background: dotColor, flexShrink:0,
                boxShadow: (done||current) ? `0 0 0 3px ${phaseHue}1a` : 'none',
                animation: current ? 'logo-dot-blink 1.1s step-end infinite' : 'none',
                transition:'all 0.15s' }} />
              <span style={{ fontFamily:MONO, fontSize:10, fontWeight: current?600:500,
                color: labelColor, letterSpacing:'0.5px', textTransform:'uppercase' }}>
                {PHASE_LABELS[p] || p}
              </span>
            </div>
            {i < phases.length - 1 && (
              <div style={{ flex:1, height:1, background: lineBg, margin:'0 10px',
                transition:'background 0.25s' }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ─── SOURCE CHIPS ─────────────────────────────────────────────────────────────
function SourceChips({ sources }) {
  const T = useTheme();
  if (!sources || sources.length === 0) return null;
  return (
    <div style={{ padding:'10px 0 0' }}>
      <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:8 }}>
        <span style={{ fontFamily:MONO, fontSize:10, fontWeight:500, color:T.fg4,
          letterSpacing:'0.7px', textTransform:'uppercase' }}>
          Sources collected
        </span>
        <span style={{ fontFamily:MONO, fontSize:10, fontWeight:600, color:BRAND_DEEP,
          background:BRAND+'1f', padding:'1px 7px', borderRadius:9999 }}>
          {sources.length}
        </span>
      </div>
      <div style={{ display:'flex', flexWrap:'wrap', gap:5 }}>
        {sources.map((s, i) => (
          <div key={i} className="src-chip"
            style={{ display:'inline-flex', alignItems:'center', gap:6, maxWidth:280,
              padding:'4px 10px', borderRadius:9999, background:T.gray100,
              border:`1px solid ${T.border}`,
              fontFamily:SANS, fontSize:11.5, color:T.fg2,
              animation:'fadeInUp 0.2s ease forwards' }}>
            <span style={{ flex:1, overflow:'hidden', textOverflow:'ellipsis',
              whiteSpace:'nowrap' }} title={s.title}>{s.title}</span>
            <span style={{ fontFamily:MONO, fontSize:10, color:T.fg4,
              letterSpacing:'0.3px' }}>{s.src} {s.year}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── LOG LINE ─────────────────────────────────────────────────────────────────
function LogLine({ phase, text, live }) {
  const T = useTheme();
  const tone = PHASE_TONE[phase] || 'info';
  const phaseColor = tone === 'warn' ? T.amberText : tone === 'error' ? T.redText : BRAND_DEEP;
  const phaseBg    = tone === 'warn' ? T.amberBg   : tone === 'error' ? T.redBg   : BRAND+'1c';
  const rowBg      = tone === 'warn' ? T.amberBg   : tone === 'error' ? T.redBg   : 'transparent';
  const rowBorder  = tone === 'warn' ? T.amberBorder : tone === 'error' ? '#E53535' : 'transparent';
  return (
    <div className={'log-line' + (live ? ' live' : '')}
      style={{ display:'flex', gap:10, padding:'5px 12px 5px 10px',
        background: rowBg, borderLeft: `2px solid ${rowBorder}`,
        borderRadius:'2px 4px 4px 2px', alignItems:'flex-start' }}>
      <span style={{ fontFamily:MONO, fontSize:9.5, fontWeight:600,
          letterSpacing:'0.6px', textTransform:'uppercase',
          color: phaseColor, background: phaseBg, padding:'2px 6px', borderRadius:4,
          flexShrink:0, marginTop:1, minWidth:46, textAlign:'center' }}>
        {phase}
      </span>
      <span style={{ fontFamily:SANS, fontSize:12.5, color:T.fg2,
          lineHeight:1.5, flex:1, wordBreak:'break-word' }}>
        {text}
        {live && (
          <span style={{ marginLeft:4 }}>
            <span className="thinking-dot"/><span className="thinking-dot"/><span className="thinking-dot"/>
          </span>
        )}
      </span>
    </div>
  );
}

// ─── LOG STREAM ───────────────────────────────────────────────────────────────
function LogStream({ logs, status }) {
  const T = useTheme();
  const isRunning = status === 'running';
  const isResult = status === 'success' || status === 'failure';
  const [collapsed, setCollapsed] = React.useState(isResult);

  // When a run finishes, default to collapsed; when fresh running, expanded
  React.useEffect(() => {
    if (status === 'running') setCollapsed(false);
    else if (isResult) setCollapsed(true);
  }, [status]);

  const logRef = React.useRef(null);
  React.useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs.length]);

  if (logs.length === 0) return null;

  if (isResult && collapsed) {
    return (
      <button onClick={()=>setCollapsed(false)}
        style={{ display:'flex', alignItems:'center', gap:7, padding:'7px 12px',
          borderRadius:8, border:`1px solid ${T.border}`, background:T.surface,
          color:T.fg3, fontFamily:SANS, fontSize:12, cursor:'pointer',
          alignSelf:'flex-start' }}>
        <Ico.ChevronRight/>
        <span style={{ fontFamily:MONO, fontSize:10, letterSpacing:'0.5px',
          textTransform:'uppercase', color:T.fg4 }}>
          {logs.length} events
        </span>
        <span style={{ fontFamily:SANS, fontSize:12, color:T.fg3 }}>
          Show activity log
        </span>
      </button>
    );
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
      <div style={{ display:'flex', alignItems:'center', gap:8 }}>
        <div style={{ fontFamily:MONO, fontSize:10, fontWeight:500, color:T.fg4,
            letterSpacing:'0.7px', textTransform:'uppercase' }}>
          Activity log
        </div>
        {isResult && (
          <button onClick={()=>setCollapsed(true)}
            style={{ marginLeft:'auto', background:'transparent', border:'none',
              cursor:'pointer', fontFamily:SANS, fontSize:11, color:T.fg4,
              display:'inline-flex', alignItems:'center', gap:4 }}>
            <Ico.ChevronDown/> Collapse
          </button>
        )}
      </div>
      <div ref={logRef}
        style={{ display:'flex', flexDirection:'column', gap:2,
          maxHeight: isResult ? 240 : 'none',
          overflowY: isResult ? 'auto' : 'visible' }}>
        {logs.map((l, i) => (
          <LogLine key={i} phase={l.phase} text={l.text}
            live={isRunning && i === logs.length - 1} />
        ))}
      </div>
    </div>
  );
}

// ─── EMPTY STATE ──────────────────────────────────────────────────────────────
function OutputEmpty() {
  const T = useTheme();
  return (
    <div style={{ flex:1, position:'relative', display:'flex', flexDirection:'column',
        alignItems:'center', justifyContent:'center', gap:14, padding:24, overflow:'hidden' }}>
      <div aria-hidden="true" style={{ position:'absolute', inset:0, pointerEvents:'none',
        background: T.dark ?
          `radial-gradient(ellipse 480px 320px at 50% 40%, ${BRAND}14, transparent 60%),
           radial-gradient(ellipse 380px 260px at 30% 70%, ${VIOLET}10, transparent 60%),
           radial-gradient(ellipse 380px 260px at 75% 30%, ${BLUE}10, transparent 60%)` :
          `radial-gradient(ellipse 480px 320px at 50% 40%, ${BRAND}1f, transparent 60%),
           radial-gradient(ellipse 380px 260px at 30% 70%, ${VIOLET}14, transparent 60%),
           radial-gradient(ellipse 380px 260px at 75% 30%, ${BLUE}14, transparent 60%)`,
      }} />
      <div style={{ position:'relative', width:56, height:56, borderRadius:14,
          background:`linear-gradient(135deg, ${BRAND}33, ${VIOLET}22)`,
          border:`1px solid ${BRAND}33`,
          display:'flex', alignItems:'center', justifyContent:'center', color:BRAND_DEEP }}>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 2v7.31"/><path d="M14 9.3V1.99"/><path d="M8.5 2h7"/>
          <path d="M14 9.3a6.5 6.5 0 1 1-4 0"/><path d="M5.52 16h12.96"/>
        </svg>
      </div>
      <div style={{ position:'relative', fontFamily:SANS, fontSize:15, fontWeight:600, color:T.fg1 }}>
        Run a research action
      </div>
      <div style={{ position:'relative', fontFamily:SANS, fontSize:13, color:T.fg3,
          textAlign:'center', maxWidth:340 }}>
        Select an action on the left and fill in the form, or press <Kbd>⌘</Kbd><Kbd>K</Kbd> to
        quick-jump.
      </div>
    </div>
  );
}

// ─── RESULT VARIANTS ──────────────────────────────────────────────────────────
function ResultResearchSuccess({ topic, action, onSaveAsPreset, onPipeToNotebook, dest }) {
  const T = useTheme();
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      <div style={{ display:'flex', alignItems:'center', gap:10, flexWrap:'wrap' }}>
        <span style={{ display:'inline-flex', alignItems:'center', gap:7 }}>
          <span style={{ color:BRAND_DEEP, display:'flex' }}><Ico.CheckCircle/></span>
          <span style={{ fontFamily:SANS, fontSize:14, fontWeight:600, color:T.fg1 }}>Done</span>
        </span>
        <span style={{ fontFamily:MONO, fontSize:10, color:T.fg4, letterSpacing:'0.5px',
            textTransform:'uppercase' }}>· 4m 12s · 18 sources</span>
        <div style={{ marginLeft:'auto', display:'inline-flex', gap:6 }}>
          <GhostBtn size="sm" icon={<Ico.Bookmark/>} onClick={onSaveAsPreset}>
            Save as preset
          </GhostBtn>
        </div>
      </div>
      <div>
        <Label>Output file</Label>
        <CodeBlock>~/docent/runs/2026-05-18_{action.id}_{(topic||'').slice(0,24).replace(/\s+/g,'-')}/report.md</CodeBlock>
      </div>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        <Chip color={BRAND_DEEP} icon={<Ico.Layers/>}>Notebook · nb_4f2c</Chip>
        <a href="#" style={{ display:'inline-flex', alignItems:'center', gap:5,
            fontFamily:SANS, fontSize:12, color:T.fg2, textDecoration:'none',
            padding:'4px 10px', borderRadius:9999, border:`1px solid ${T.borderMd}` }}>
          <Ico.ExternalLink/> Vault: research/storm-surge.md
        </a>
      </div>

      {dest === 'Pipe →' && (
        <div style={{ display:'flex', alignItems:'center', gap:12,
            padding:'12px 14px',
            background:BRAND+'12',
            border:`1px solid ${BRAND+'33'}`,
            borderLeft:`3px solid ${BRAND_DEEP}`,
            borderRadius:'4px 8px 8px 4px' }}>
          <span style={{ color:BRAND_DEEP, display:'flex' }}><Ico.Pipe/></span>
          <div style={{ flex:1, fontFamily:SANS, fontSize:12.5, color:T.fg2, lineHeight:1.5 }}>
            <strong style={{ color:T.fg1, fontWeight:600 }}>Piped to To notebook</strong>
            <span style={{ color:T.fg4, marginLeft:6 }}>
              · sources file pre-filled with this run's output
            </span>
          </div>
          <PrimaryBtn size="sm" icon={<Ico.ArrowRight/>} onClick={onPipeToNotebook}>
            Continue
          </PrimaryBtn>
        </div>
      )}
    </div>
  );
}

function ResultFailure() {
  const T = useTheme();
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
      <div style={{ display:'flex', alignItems:'center', gap:8 }}>
        <span style={{ color:T.redText, display:'flex' }}><Ico.XCircle/></span>
        <span style={{ fontFamily:SANS, fontSize:14, fontWeight:600, color:T.fg1 }}>Run failed</span>
      </div>
      <div style={{ fontFamily:SANS, fontSize:12.5, color:T.fg2, lineHeight:1.55 }}>
        Anthropic backend returned <span style={{ fontFamily:MONO, fontSize:11.5 }}>401 unauthorized</span>.
        The API key is missing or invalid.
      </div>
      <div>
        <Label>Fix</Label>
        <CodeBlock>{`docent config set anthropic_api_key sk-ant-...`}</CodeBlock>
      </div>
    </div>
  );
}

function ResultSearch({ query }) {
  const T = useTheme();
  const rows = [
    { title:'Storm surge attribution under non-stationary sea level rise', year:2024, authors:'Lin, N. · Emanuel, K.', source:'arXiv' },
    { title:'Bayesian inundation forecasting on US Atlantic coast', year:2023, authors:'Park, J. · Walsh, K. · Vitart, F.', source:'JGR' },
    { title:'Compound flooding from tropical cyclones: a review', year:2022, authors:'Wahl, T. · Jain, S. · Bender, J.', source:'Nat. Geo.' },
    { title:'High-resolution coupled modeling of coastal flood risk', year:2024, authors:'Marsooli, R. · Lin, N.', source:'PNAS' },
    { title:'Tide-surge-wave interaction in shallow estuaries', year:2021, authors:'Vatvani, D. · Zijlema, M.', source:'Ocean Eng.' },
  ];
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
      <div style={{ fontFamily:SANS, fontSize:12.5, color:T.fg3 }}>
        {rows.length} results · query <span style={{ fontFamily:MONO, color:T.fg2 }}>"{query || 'storm surge inundation'}"</span>
      </div>
      <div style={{ border:`1px solid ${T.border}`, borderRadius:8, overflow:'hidden' }}>
        <table style={{ width:'100%', borderCollapse:'collapse' }}>
          <thead>
            <tr style={{ background:T.surface, borderBottom:`1px solid ${T.border}` }}>
              {['Title','Year','Authors','Source',''].map((c,i) => (
                <th key={i} style={{ padding:'8px 12px', textAlign: i===4?'right':'left',
                    fontFamily:MONO, fontSize:10, fontWeight:500, color:T.fg4,
                    letterSpacing:'0.6px', textTransform:'uppercase' }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r,i) => (
              <tr key={i} style={{ borderBottom: i<rows.length-1 ? `1px solid ${T.border}` : 'none' }}>
                <td style={{ padding:'10px 12px', fontFamily:SANS, fontSize:13, color:T.fg1,
                    lineHeight:1.4 }}>
                  <a href="#" style={{ color:T.fg1, textDecoration:'none',
                      display:'inline-flex', alignItems:'center', gap:5 }}>
                    {r.title}
                    <span style={{ color:T.fg4, opacity:0.5, display:'flex' }}><Ico.ExternalLink/></span>
                  </a>
                </td>
                <td style={{ padding:'10px 12px', fontFamily:MONO, fontSize:11, color:T.fg3,
                    letterSpacing:'0.3px', whiteSpace:'nowrap' }}>{r.year}</td>
                <td style={{ padding:'10px 12px', fontFamily:SANS, fontSize:12, color:T.fg3,
                    whiteSpace:'nowrap' }}>{r.authors}</td>
                <td style={{ padding:'10px 12px', fontFamily:MONO, fontSize:10, color:T.fg4,
                    letterSpacing:'0.4px', textTransform:'uppercase', whiteSpace:'nowrap' }}>{r.source}</td>
                <td style={{ padding:'8px 12px', textAlign:'right' }}>
                  <GhostBtn size="sm">Look up</GhostBtn>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ResultGetPaper() {
  const T = useTheme();
  const [more, setMore] = React.useState(false);
  const [added, setAdded] = React.useState(false);
  const abstract = `We present a high-resolution coupled ocean-atmosphere model for storm surge attribution on the US Atlantic coast. The framework combines tropical cyclone synthetic tracks with a barotropic surge solver and applies Bayesian downscaling to convert ensemble forecasts into actionable inundation depth probabilities. Validation against historical events including Sandy (2012), Florence (2018), and Ian (2022) shows skill improvements of 12–18% over the prior generation of operational systems.`;
  const overview = `This paper extends Lin & Emanuel (2019) by adding non-stationary sea level rise priors to the Bayesian framework. The key novelty is the joint treatment of tide–surge–wave coupling in shallow estuaries — historically a major source of bias in operational forecasts. The authors release open-source code (GPL-3) and the trained surrogate model. For a graduate-level reader, the methodology section is dense but the results are compelling. Section 4.2 on hindcast skill is the most actionable for downstream users. The discussion acknowledges that intensity scaling under warmer climates remains uncertain and recommends future work coupling with a CMIP6 ensemble.`;
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      <div>
        <div style={{ fontFamily:SANS, fontSize:16, fontWeight:600, color:T.fg1,
            lineHeight:1.35, marginBottom:6, textWrap:'pretty' }}>
          High-resolution coupled modeling of coastal flood risk under non-stationary sea level rise
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center', flexWrap:'wrap',
            fontFamily:SANS, fontSize:12, color:T.fg3 }}>
          <span>Marsooli, R. · Lin, N. · Emanuel, K.</span>
          <span style={{ color:T.gray200 }}>·</span>
          <span style={{ fontFamily:MONO, fontSize:10, color:T.fg4, letterSpacing:'0.4px',
            textTransform:'uppercase' }}>PNAS 2024</span>
          <span style={{ color:T.gray200 }}>·</span>
          <span style={{ fontFamily:MONO, fontSize:10, color:T.fg4, letterSpacing:'0.4px' }}>
            arXiv:2401.12345
          </span>
        </div>
      </div>
      <div>
        <Label>Abstract</Label>
        <div style={{ maxHeight:140, overflowY:'auto', background:T.surface,
            border:`1px solid ${T.border}`, borderRadius:8, padding:'12px 14px',
            fontFamily:SANS, fontSize:13, color:T.fg2, lineHeight:1.55 }}>
          {abstract}
        </div>
      </div>
      <div>
        <Label>AI overview</Label>
        <div style={{ fontFamily:SANS, fontSize:13, color:T.fg2, lineHeight:1.6 }}>
          {more ? overview : overview.slice(0, 600) + '…'}
          <button onClick={()=>setMore(m=>!m)}
            style={{ marginLeft:6, background:'transparent', border:'none', cursor:'pointer',
              fontFamily:SANS, fontSize:12, fontWeight:500, color:BRAND_DEEP, padding:0 }}>
            {more ? 'Show less' : 'Show more'}
          </button>
        </div>
      </div>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        <button onClick={()=>setAdded(true)} disabled={added}
          className="tap"
          style={{ display:'inline-flex', alignItems:'center', gap:6,
            padding:'6px 14px', borderRadius:9999,
            background: added ? BRAND+'33' : BRAND, color:'#0d0d0d',
            fontFamily:SANS, fontSize:12.5, fontWeight:600,
            border:'none', cursor: added ? 'default' : 'pointer' }}>
          {added ? <Ico.CheckCircle/> : <Ico.Plus/>}
          {added ? 'Added to Reading' : 'Add to Reading'}
        </button>
        <a href="#" style={{ display:'inline-flex', alignItems:'center', gap:6,
            padding:'6px 14px', borderRadius:9999,
            background:'transparent', color:T.fg2,
            border:`1px solid ${T.borderMd}`,
            fontFamily:SANS, fontSize:12.5, fontWeight:500, textDecoration:'none' }}>
          <Ico.ExternalLink/> Open on arXiv
        </a>
      </div>
    </div>
  );
}

function PerspectiveSection({ title, color, body }) {
  const T = useTheme();
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ border:`1px solid ${T.border}`, borderRadius:8, overflow:'hidden' }}>
      <button onClick={()=>setOpen(o=>!o)}
        style={{ width:'100%', display:'flex', alignItems:'center', gap:8,
          padding:'10px 14px', background:'transparent', border:'none', cursor:'pointer',
          fontFamily:SANS, fontSize:13, fontWeight:500, color:T.fg1, textAlign:'left' }}>
        <span style={{ width:8, height:8, borderRadius:'50%', background:color, flexShrink:0 }} />
        {title}
        <span style={{ marginLeft:'auto', color:T.fg4, display:'flex' }}>
          {open ? <Ico.ChevronDown/> : <Ico.ChevronRight/>}
        </span>
      </button>
      {open && (
        <div style={{ padding:'0 14px 12px', fontFamily:SANS, fontSize:12.5, color:T.fg2,
            lineHeight:1.6, borderTop:`1px solid ${T.border}` }}>
          <div style={{ paddingTop:10 }}>{body}</div>
        </div>
      )}
    </div>
  );
}

function ResultNotebook() {
  const T = useTheme();
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      <div style={{ display:'flex', alignItems:'center', gap:8 }}>
        <span style={{ color:BRAND_DEEP, display:'flex' }}><Ico.CheckCircle/></span>
        <span style={{ fontFamily:SANS, fontSize:14, fontWeight:600, color:T.fg1 }}>
          Notebook updated
        </span>
      </div>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        <Chip color={BRAND_DEEP}>18 sources added</Chip>
        <Chip color={AMBER}>2 failed</Chip>
        <Chip color={BLUE}>5 from NLM web</Chip>
      </div>
      <div style={{ display:'flex', gap:8, alignItems:'center', flexWrap:'wrap' }}>
        <span style={{ display:'inline-flex', alignItems:'center', gap:5,
            padding:'3px 10px', borderRadius:9999, background:BRAND+'22', color:BRAND_DEEP,
            fontFamily:MONO, fontSize:11, fontWeight:600, letterSpacing:'0.5px',
            textTransform:'uppercase' }}>
          <Ico.CheckCircle/> Quality gate · clean
        </span>
        <span style={{ fontFamily:SANS, fontSize:12, color:T.fg3 }}>
          0 contradictions · 1 gap noted
        </span>
      </div>
      <div>
        <Label>Perspectives</Label>
        <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
          <PerspectiveSection title="Practitioner" color={BLUE}
            body="Section 4.2 hindcast skill is directly usable; you can replace the prior Lin & Emanuel (2019) module with this one and expect 12–18% improvement. Note that the surrogate model is GPU-only above 4km resolution." />
          <PerspectiveSection title="Skeptic" color={AMBER}
            body="The validation set leans on three named storms. Generalization to compound events (rain + surge) is unclear and the paper does not run a leave-one-out cross-check across decades." />
          <PerspectiveSection title="Beginner" color={BRAND_DEEP}
            body="Read Section 1 and the figures in Section 5 first. Skip the Bayesian downscaling derivation (Sections 3.2–3.4) unless you specifically need the math — the headline result holds without it." />
        </div>
      </div>
      <div style={{ background:T.amberBg, borderLeft:`3px solid ${T.amberBorder}`,
          borderRadius:'4px 8px 8px 4px', padding:'12px 14px',
          display:'flex', flexDirection:'column', gap:8 }}>
        <div style={{ display:'flex', alignItems:'center', gap:7,
            color:T.amberText, fontFamily:SANS, fontSize:12.5, fontWeight:600 }}>
          <Ico.AlertTriangle /> Save this notebook ID
        </div>
        <div style={{ fontFamily:SANS, fontSize:12, color:T.amberText, lineHeight:1.5 }}>
          A new notebook was created. Run this once to make it the default:
        </div>
        <CodeBlock>{`docent config set notebook_id nb_4f2c`}</CodeBlock>
      </div>
    </div>
  );
}

function ResultConfigShow() {
  const T = useTheme();
  const rows = [
    ['default_backend',     'anthropic'],
    ['notebook_id',         'nb_4f2c'],
    ['vault_path',          '~/docent/vault'],
    ['anthropic_api_key',   'sk-a...xZ9q'],
    ['openai_api_key',      'sk-p...4Aj1'],
    ['groq_api_key',        '(not set)'],
    ['gemini_api_key',      '(not set)'],
    ['tavily_api_key',      'tvly...kQ2m'],
    ['mendeley_token',      'eyJh...A8wL'],
    ['max_research_minutes','30'],
  ];
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
      <div style={{ fontFamily:SANS, fontSize:12.5, color:T.fg3 }}>
        Configuration (10 keys)
      </div>
      <div style={{ border:`1px solid ${T.border}`, borderRadius:8, overflow:'hidden' }}>
        {rows.map(([k, v], i) => {
          const unset = v === '(not set)';
          return (
            <div key={k} style={{ display:'grid', gridTemplateColumns:'minmax(180px, 0.4fr) 1fr',
                gap:14, padding:'9px 14px',
                borderBottom: i<rows.length-1 ? `1px solid ${T.border}` : 'none',
                background: i%2===0 ? 'transparent' : T.surface,
                alignItems:'center' }}>
              <span style={{ fontFamily:MONO, fontSize:11, color:T.fg2,
                letterSpacing:'0.3px' }}>{k}</span>
              <span style={{ fontFamily:MONO, fontSize:11,
                color: unset ? T.fg4 : T.fg1,
                fontStyle: unset ? 'italic' : 'normal' }}>{v}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ResultConfigSet({ cfgKey }) {
  const T = useTheme();
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
      <div style={{ display:'flex', alignItems:'center', gap:8 }}>
        <span style={{ color:BRAND_DEEP, display:'flex' }}><Ico.CheckCircle/></span>
        <span style={{ fontFamily:SANS, fontSize:14, fontWeight:600, color:T.fg1 }}>Key saved</span>
      </div>
      <div style={{ fontFamily:SANS, fontSize:12.5, color:T.fg2, lineHeight:1.6 }}>
        <span style={{ fontFamily:MONO, fontSize:11.5, color:T.fg1 }}>{cfgKey || 'anthropic_api_key'}</span>
        {' was written to:'}
      </div>
      <CodeBlock>~/.docent/config.toml</CodeBlock>
    </div>
  );
}

// ─── COMPARE DIFF VIEW (new) ─────────────────────────────────────────────────
function ResultCompare({ a, b }) {
  const T = useTheme();
  const aOnly = [
    'Uses Bayesian downscaling with priors trained on 1979–2020 reanalysis',
    'Validation against Sandy, Florence, Ian (3 storms)',
    'Open-source GPL-3 release of surrogate model',
  ];
  const shared = [
    'Tropical cyclone synthetic tracks coupled with barotropic surge solver',
    'Reports 12–18% skill improvement over operational baselines',
    'Identifies tide-surge-wave coupling as primary bias source',
  ];
  const bOnly = [
    'Ensemble of 10k members vs. 1k in A',
    'No code release; results table only',
    'Includes inland riverine flooding component',
  ];
  const contradictions = [
    {
      label: 'Surrogate model resolution',
      a: 'A: GPU-only above 4km; CPU fallback degrades quality',
      b: 'B: claims CPU-only inference is "fully equivalent" at any resolution',
    },
  ];
  function Col({ label, items, color }) {
    return (
      <div style={{ flex:1, minWidth:0, display:'flex', flexDirection:'column', gap:8 }}>
        <div style={{ display:'flex', alignItems:'center', gap:6,
            fontFamily:MONO, fontSize:10, fontWeight:600, color: color,
            letterSpacing:'0.6px', textTransform:'uppercase' }}>
          <span style={{ width:5, height:5, borderRadius:'50%', background:color }} />
          {label}
        </div>
        <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
          {items.map((it, i) => (
            <div key={i} style={{ padding:'10px 12px', borderRadius:8,
                background: T.surface, border:`1px solid ${T.border}`,
                fontFamily:SANS, fontSize:12, color:T.fg2, lineHeight:1.5 }}>
              {it}
            </div>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
      <div style={{ display:'flex', alignItems:'center', gap:8 }}>
        <span style={{ color:BRAND_DEEP, display:'flex' }}><Ico.CheckCircle/></span>
        <span style={{ fontFamily:SANS, fontSize:14, fontWeight:600, color:T.fg1 }}>
          Comparison complete
        </span>
        <span style={{ fontFamily:MONO, fontSize:10, color:T.fg4, letterSpacing:'0.5px',
            textTransform:'uppercase' }}>· {shared.length + aOnly.length + bOnly.length} findings</span>
      </div>

      {/* Paper headers */}
      <div style={{ display:'flex', gap:12 }}>
        <div style={{ flex:1, padding:'10px 12px', borderRadius:8, border:`1px solid ${T.border}`,
            background:T.surface }}>
          <div style={{ fontFamily:MONO, fontSize:9.5, color:BLUE,
              letterSpacing:'0.7px', textTransform:'uppercase', marginBottom:4 }}>Paper A</div>
          <div style={{ fontFamily:SANS, fontSize:12.5, fontWeight:500, color:T.fg1,
              lineHeight:1.4 }}>{a || '2401.12345'}</div>
        </div>
        <div style={{ flex:1, padding:'10px 12px', borderRadius:8, border:`1px solid ${T.border}`,
            background:T.surface }}>
          <div style={{ fontFamily:MONO, fontSize:9.5, color:BRAND_DEEP,
              letterSpacing:'0.7px', textTransform:'uppercase', marginBottom:4 }}>Paper B</div>
          <div style={{ fontFamily:SANS, fontSize:12.5, fontWeight:500, color:T.fg1,
              lineHeight:1.4 }}>{b || '2310.06825'}</div>
        </div>
      </div>

      {/* Three columns */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:12, alignItems:'flex-start' }}>
        <Col label="Only in A" items={aOnly} color={BLUE} />
        <Col label="Shared" items={shared} color={BRAND_DEEP} />
        <Col label="Only in B" items={bOnly} color={BRAND_DEEP} />
      </div>

      {/* Contradictions */}
      {contradictions.length > 0 && (
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:8,
              fontFamily:MONO, fontSize:10, fontWeight:600, color:T.amberText,
              letterSpacing:'0.6px', textTransform:'uppercase' }}>
            <Ico.AlertTriangle/> Contradictions
          </div>
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {contradictions.map((c, i) => (
              <div key={i} style={{ background:T.amberBg,
                  borderLeft:`3px solid ${T.amberBorder}`,
                  borderRadius:'4px 8px 8px 4px', padding:'10px 14px',
                  display:'flex', flexDirection:'column', gap:6 }}>
                <div style={{ fontFamily:SANS, fontSize:12.5, fontWeight:600,
                    color:T.amberText }}>{c.label}</div>
                <div style={{ fontFamily:SANS, fontSize:12, color:T.fg2, lineHeight:1.55 }}>
                  {c.a}
                </div>
                <div style={{ fontFamily:SANS, fontSize:12, color:T.fg2, lineHeight:1.55 }}>
                  {c.b}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <Label>Output file</Label>
        <CodeBlock>~/docent/runs/2026-05-18_compare_2401-vs-2310/comparison.md</CodeBlock>
      </div>
    </div>
  );
}

// ─── OUTPUT PANEL ─────────────────────────────────────────────────────────────
function OutputPanel({ action, state, status, logs, sources, currentPhase,
                       onReset, onSaveAsPreset, onPipeToNotebook }) {
  const T = useTheme();
  const isResult = status === 'success' || status === 'failure';
  const isRunning = status === 'running';
  const isEmpty = status === 'idle';

  const completedPhases = React.useMemo(() => {
    const set = new Set();
    for (const l of logs) {
      if (ACTION_PHASES[action.id]?.includes(l.phase)) set.add(l.phase);
    }
    // a phase is "completed" only if there's a later phase OR status === success
    const phases = ACTION_PHASES[action.id] || [];
    const lastLogged = phases.findIndex(p => p === currentPhase);
    if (status === 'success') return new Set(phases);
    if (lastLogged > 0) {
      const done = new Set(phases.slice(0, lastLogged));
      return done;
    }
    return new Set();
  }, [logs.length, status, currentPhase, action.id]);

  function renderResult() {
    if (status === 'failure') return <ResultFailure />;
    switch (action.id) {
      case 'search':
      case 'scholarly':  return <ResultSearch query={state.query} />;
      case 'getpaper':   return <ResultGetPaper />;
      case 'notebook':   return <ResultNotebook />;
      case 'cfgshow':    return <ResultConfigShow />;
      case 'cfgset':     return <ResultConfigSet cfgKey={state.cfgKey} />;
      case 'compare':    return <ResultCompare a={state.artifactA} b={state.artifactB} />;
      default:           return <ResultResearchSuccess topic={state.topic} action={action}
                                  dest={state.dest}
                                  onSaveAsPreset={onSaveAsPreset}
                                  onPipeToNotebook={onPipeToNotebook}/>;
    }
  }

  const breadcrumbDetail = (() => {
    switch (action.id) {
      case 'deep': case 'lit': case 'draft':       return state.topic || '';
      case 'peer': case 'replicate': case 'audit': return state.artifact || '';
      case 'compare':
        return state.artifactA && state.artifactB ? `${state.artifactA} vs ${state.artifactB}` : '';
      case 'search': case 'scholarly':             return state.query || '';
      case 'getpaper':                             return state.arxivId || '';
      case 'cfgset':                               return state.cfgKey || '';
      case 'notebook':                             return state.srcPath || 'notebook build';
      default:                                     return '';
    }
  })();

  return (
    <section style={{ flex:1, display:'flex', flexDirection:'column', minWidth:0,
        background:T.bg, overflow:'hidden', position:'relative' }}>
      {/* Hero wash — bleeds behind the output header */}
      <div aria-hidden="true" style={{ position:'absolute', inset:'0 0 auto 0',
        height:280, pointerEvents:'none', zIndex:0,
        background: T.dark ?
          `radial-gradient(ellipse 520px 280px at 12% 0%, ${BRAND}14, transparent 60%),
           radial-gradient(ellipse 640px 320px at 60% 10%, ${BLUE}14, transparent 60%),
           radial-gradient(ellipse 480px 260px at 92% 0%, ${PINK}12, transparent 60%)` :
          `radial-gradient(ellipse 520px 280px at 12% 0%, ${BRAND}1c, transparent 60%),
           radial-gradient(ellipse 640px 320px at 60% 10%, ${BLUE}1c, transparent 60%),
           radial-gradient(ellipse 480px 260px at 92% 0%, ${PINK}1a, transparent 60%)`,
      }} />

      {!isEmpty && (
        <div style={{ flexShrink:0, padding:'14px 24px',
            position:'relative', zIndex:1,
            borderBottom:`1px solid ${T.border}`,
            display:'flex', alignItems:'center', justifyContent:'space-between', gap:12 }}>
          <div style={{ display:'flex', alignItems:'center', gap:10, minWidth:0 }}>
            {isRunning && (
              <span style={{ width:8, height:8, borderRadius:'50%', background:BRAND,
                animation:'logo-dot-blink 1.2s step-end infinite', flexShrink:0 }} />
            )}
            <div style={{ display:'flex', alignItems:'center', gap:8, minWidth:0 }}>
              <span style={{ fontFamily:SANS, fontSize:13, fontWeight:500, color:T.fg1,
                  whiteSpace:'nowrap' }}>
                {action.label}
              </span>
              {breadcrumbDetail && <>
                <span style={{ fontFamily:SANS, fontSize:13, color:T.gray200 }}>·</span>
                <span style={{ fontFamily:MONO, fontSize:11.5, color:T.fg3,
                    letterSpacing:'0.2px', overflow:'hidden', textOverflow:'ellipsis',
                    whiteSpace:'nowrap', minWidth:0 }}>
                  {breadcrumbDetail}
                </span>
              </>}
            </div>
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:6 }}>
            {isResult && (
              <GhostBtn onClick={onReset}>Clear</GhostBtn>
            )}
          </div>
        </div>
      )}

      <div style={{ position:'relative', zIndex:1, flex:1, overflowY:'auto',
          display:'flex', flexDirection:'column' }}>
        {isEmpty && <OutputEmpty />}

        {(isRunning || isResult) && (
          <div style={{ padding:'12px 24px 0' }}>
            <PhaseStrip actionId={action.id}
              completedPhases={completedPhases}
              currentPhase={currentPhase}
              status={status} />
          </div>
        )}

        {isRunning && sources.length > 0 && (
          <div style={{ padding:'0 24px' }}>
            <SourceChips sources={sources} />
          </div>
        )}

        {(isRunning || isResult) && logs.length > 0 && (
          <div style={{ padding:'14px 22px 14px', borderBottom: isResult ? `1px solid ${T.border}` : 'none' }}>
            <LogStream logs={logs} status={status} />
          </div>
        )}

        {isResult && (
          <div style={{ padding:'18px 24px 24px' }}>
            {renderResult()}
          </div>
        )}
      </div>
    </section>
  );
}

// ─── HISTORY DRAWER ───────────────────────────────────────────────────────────
function HistoryDrawer({ runs, currentRunId, onSelect, onClose, onClear }) {
  const T = useTheme();
  return (
    <aside style={{ width:300, flexShrink:0, height:'100%',
        borderLeft:`1px solid ${T.border}`, background:T.bg,
        display:'flex', flexDirection:'column', overflow:'hidden' }}>
      <div style={{ padding:'14px 18px', borderBottom:`1px solid ${T.border}`,
          display:'flex', alignItems:'center', gap:8 }}>
        <span style={{ color:T.fg3, display:'flex' }}><Ico.History/></span>
        <span style={{ fontFamily:SANS, fontSize:13, fontWeight:600, color:T.fg1 }}>
          Run history
        </span>
        <span style={{ fontFamily:MONO, fontSize:10, color:T.fg4, letterSpacing:'0.5px' }}>
          {runs.length}
        </span>
        <div style={{ marginLeft:'auto', display:'flex', gap:4 }}>
          {runs.length > 0 && (
            <button onClick={onClear} title="Clear all" style={{ width:24, height:24,
              border:'none', background:'transparent', color:T.fg4, cursor:'pointer',
              display:'flex', alignItems:'center', justifyContent:'center', borderRadius:5 }}>
              <Ico.Trash/>
            </button>
          )}
          <button onClick={onClose} title="Close history" style={{ width:24, height:24,
            border:'none', background:'transparent', color:T.fg4, cursor:'pointer',
            display:'flex', alignItems:'center', justifyContent:'center', borderRadius:5 }}>
            <Ico.X/>
          </button>
        </div>
      </div>
      <div style={{ flex:1, overflowY:'auto', padding:'8px 10px' }}>
        {runs.length === 0 ? (
          <div style={{ display:'flex', flexDirection:'column', alignItems:'center',
              justifyContent:'center', height:'100%', gap:8, color:T.fg4,
              padding:'24px 14px', textAlign:'center' }}>
            <span style={{ opacity:0.4 }}><Ico.History/></span>
            <span style={{ fontFamily:SANS, fontSize:12 }}>No runs yet</span>
            <span style={{ fontFamily:SANS, fontSize:11, color:T.fg4, lineHeight:1.5 }}>
              Completed runs will appear here. Click one to view its results.
            </span>
          </div>
        ) : runs.map(r => {
          const active = r.id === currentRunId;
          const dotColor = r.status === 'running' ? AMBER_BORDER
                         : r.status === 'failure' ? '#E53535'
                         : BRAND;
          const dotAnim = r.status === 'running' ? 'logo-dot-blink 1.1s step-end infinite' : 'none';
          return (
            <button key={r.id} onClick={()=>onSelect(r.id)}
              style={{ width:'100%', textAlign:'left',
                padding:'10px 12px', marginBottom:4,
                borderRadius:8, border:`1px solid ${active ? BRAND+'66' : 'transparent'}`,
                background: active ? BRAND+'10' : 'transparent', cursor:'pointer',
                display:'flex', flexDirection:'column', gap:5, position:'relative' }}>
              <div style={{ display:'flex', alignItems:'center', gap:7 }}>
                <span style={{ width:6, height:6, borderRadius:'50%',
                  background:dotColor, animation:dotAnim, flexShrink:0 }} />
                <span style={{ fontFamily:SANS, fontSize:12.5, fontWeight: active?600:500,
                  color:T.fg1, overflow:'hidden', textOverflow:'ellipsis',
                  whiteSpace:'nowrap', minWidth:0, flex:1 }}>
                  {r.actionLabel}
                </span>
                <span style={{ fontFamily:MONO, fontSize:9.5, color:T.fg4,
                  letterSpacing:'0.4px', flexShrink:0 }}>
                  {r.timeAgo}
                </span>
              </div>
              {r.detail && (
                <div style={{ fontFamily:MONO, fontSize:10.5, color:T.fg3,
                  letterSpacing:'0.2px', overflow:'hidden', textOverflow:'ellipsis',
                  whiteSpace:'nowrap', paddingLeft:13 }}>
                  {r.detail}
                </div>
              )}
              {r.status === 'running' && (
                <div style={{ paddingLeft:13, fontFamily:MONO, fontSize:9.5,
                  color:T.amberText, letterSpacing:'0.4px', textTransform:'uppercase' }}>
                  · {r.currentPhase || 'running'}…
                </div>
              )}
            </button>
          );
        })}
      </div>
    </aside>
  );
}

// ─── EXPORT ───────────────────────────────────────────────────────────────────
Object.assign(window, { OutputPanel, HistoryDrawer });
