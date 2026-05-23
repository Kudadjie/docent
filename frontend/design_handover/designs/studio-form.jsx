// ─── STUDIO FORM (LEFT COLUMN) ────────────────────────────────────────────────
// Action list + adaptive form + command preview + cost estimate + free-tier gate
// Plus Cmd-K palette and Preset-save modal

const {
  SANS, MONO, BRAND, BRAND_DEEP, AMBER, AMBER_BORDER, RED, BLUE, VIOLET, PINK,
  useTheme, Ico,
  ACTIONS, ALL_ACTIONS, findAction, BACKENDS, ACTION_PHASES,
  commandFor, costEstimate,
  PrimaryBtn, GhostBtn, PillToggle, Segmented, Input, Label, Field, Note,
  Toggle, Stepper, CodeBlock, Chip, Kbd,
} = window;

// Group-identity hues for the action sidebar — each section gets its own dot color.
const GROUP_COLOR = {
  Presets:   VIOLET,
  Research:  BLUE,
  Utilities: AMBER_BORDER,
  Config:    BRAND_DEEP,
};

// ─── ACTION LIST ──────────────────────────────────────────────────────────────
function ActionList({ activeId, onSelect, presets, onDeletePreset, onSelectPreset }) {
  const T = useTheme();
  function row(item, isActive, isPreset, onClick, onDelete) {
    return (
      <div key={(isPreset ? 'p:' : 'a:') + item.id} className="action-row"
        style={{ position:'relative', display:'flex', alignItems:'center',
          borderRadius:6,
          background: isActive ? BRAND+'1f' : 'transparent',
          transition:'background 0.1s' }}>
        <button onClick={onClick}
          style={{ flex:1, textAlign:'left', padding:'6px 10px',
            borderRadius:6, border:'none', background:'transparent', cursor:'pointer',
            fontFamily:SANS, fontSize:12.5,
            fontWeight: isActive ? 500 : 400,
            color: isActive ? BRAND_DEEP : T.fg2,
            display:'flex', alignItems:'center', gap:0 }}>
          <span style={{ width:4, height:4, borderRadius:'50%',
            background: isActive ? BRAND : 'transparent', marginRight:9, flexShrink:0 }} />
          {isPreset && <span style={{ color: isActive ? BRAND_DEEP : T.fg4, display:'flex',
            marginRight:6 }}><Ico.Bookmark/></span>}
          <span style={{ overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
            {item.label}
          </span>
        </button>
        {isPreset && (
          <button onClick={onDelete} className="row-action" title="Remove preset"
            style={{ width:22, height:22, borderRadius:5, border:'none', background:'transparent',
              color:T.fg4, cursor:'pointer', display:'flex', alignItems:'center',
              justifyContent:'center', marginRight:6, opacity:0, transition:'opacity 0.12s' }}>
            <Ico.Trash/>
          </button>
        )}
      </div>
    );
  }
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      {presets && presets.length > 0 && (
        <div>
          <div style={{ padding:'0 4px 6px', display:'flex', alignItems:'center', gap:7,
              fontFamily:MONO, fontSize:10, fontWeight:500,
              color:T.fg4, letterSpacing:'0.7px', textTransform:'uppercase' }}>
            <span style={{ width:6, height:6, borderRadius:'50%', background:GROUP_COLOR.Presets,
              boxShadow:`0 0 0 3px ${GROUP_COLOR.Presets}22`, flexShrink:0 }} />
            <Ico.Pin/> Presets
          </div>
          <div style={{ display:'flex', flexDirection:'column', gap:1 }}>
            {presets.map(p => row(
              { id:p.id, label:p.name },
              activeId === 'preset:'+p.id, true,
              ()=>onSelectPreset(p),
              (e)=>{ e.stopPropagation(); onDeletePreset(p.id); }
            ))}
          </div>
        </div>
      )}
      {Object.entries(ACTIONS).map(([key, group]) => {
        const groupHue = GROUP_COLOR[group.label] || BRAND;
        return (
          <div key={key}>
            <div style={{ padding:'0 4px 6px', display:'flex', alignItems:'center', gap:7,
                fontFamily:MONO, fontSize:10, fontWeight:500,
                color:T.fg4, letterSpacing:'0.7px', textTransform:'uppercase' }}>
              <span style={{ width:6, height:6, borderRadius:'50%', background:groupHue,
                boxShadow:`0 0 0 3px ${groupHue}22`, flexShrink:0 }} />
              {group.label}
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:1 }}>
              {group.items.map(it => row(it, it.id === activeId, false, ()=>onSelect(it.id)))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── BACKEND SELECTOR ─────────────────────────────────────────────────────────
function BackendSelector({ value, onChange, freeDisabled }) {
  return (
    <div style={{ display:'flex', flexWrap:'wrap', gap:5 }}>
      {BACKENDS.map(b => (
        <PillToggle key={b} active={value === b} onClick={()=>onChange(b)}
          disabled={freeDisabled && b === 'Free'}
          tooltip={freeDisabled && b === 'Free' ? 'Not available for this action' : null}>
          {b}
        </PillToggle>
      ))}
    </div>
  );
}

// ─── GUIDE FILES (with drag-drop) ─────────────────────────────────────────────
function GuideFiles({ files, setFiles, dragHover }) {
  const T = useTheme();
  const [open, setOpen] = React.useState(files.length > 0);
  const [draft, setDraft] = React.useState('');
  return (
    <div>
      <button onClick={()=>setOpen(o=>!o)} className="collapsible-toggle"
        style={{ display:'flex', alignItems:'center', gap:5, background:'transparent',
          border:'none', cursor:'pointer', padding:'2px 0', color:T.fg3,
          fontFamily:SANS, fontSize:12, fontWeight:500 }}>
        <span className="chev" style={{ display:'flex', transition:'transform 0.12s',
          transform: open?'rotate(0deg)':'rotate(-90deg)' }}>
          <Ico.ChevronDown />
        </span>
        Add guide files <span style={{ color:T.fg4, fontWeight:400 }}>
          (optional · or drop PDFs)</span>
        {files.length > 0 && (
          <span style={{ marginLeft:4, fontFamily:MONO, fontSize:10, color:BRAND_DEEP,
            background:BRAND+'1f', padding:'1px 6px', borderRadius:9999 }}>
            {files.length}
          </span>
        )}
      </button>
      {open && (
        <div style={{ marginTop:8, display:'flex', flexDirection:'column', gap:6 }}>
          <div style={{ display:'flex', gap:6 }}>
            <div style={{ flex:1 }}>
              <Input value={draft} onChange={setDraft} placeholder="path/to/guide.pdf" mono />
            </div>
            <button onClick={()=>{ if(draft.trim()){ setFiles([...files, draft.trim()]); setDraft(''); } }}
              style={{ padding:'8px 12px', borderRadius:8,
                border:`1px solid ${T.borderMd}`, background:T.gray100,
                color:T.fg2, fontFamily:SANS, fontSize:12, fontWeight:500, cursor:'pointer',
                display:'inline-flex', alignItems:'center', gap:4 }}>
              <Ico.Plus/> Add
            </button>
          </div>
          {files.length > 0 && (
            <div style={{ display:'flex', flexDirection:'column', gap:3 }}>
              {files.map((f, i) => (
                <div key={i} style={{ display:'flex', alignItems:'center', gap:6,
                    padding:'4px 8px', background:T.gray100, borderRadius:6,
                    fontFamily:MONO, fontSize:11, color:T.fg2 }}>
                  <span style={{ color:T.fg4, display:'flex' }}><Ico.File/></span>
                  <span style={{ flex:1, overflow:'hidden', textOverflow:'ellipsis',
                    whiteSpace:'nowrap' }}>{f}</span>
                  <button onClick={()=>setFiles(files.filter((_,j)=>j!==i))}
                    style={{ background:'transparent', border:'none', cursor:'pointer',
                      color:T.fg4, display:'flex', padding:2 }}>
                    <Ico.X/>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── COMMAND PREVIEW ─────────────────────────────────────────────────────────
function CommandPreview({ actionId, state }) {
  const T = useTheme();
  const cmd = commandFor(actionId, state);
  return (
    <div>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between',
          marginBottom:6 }}>
        <Label>Equivalent CLI</Label>
        <span style={{ fontFamily:MONO, fontSize:9.5, color:T.fg4, letterSpacing:'0.5px',
          textTransform:'uppercase' }}>copy & paste</span>
      </div>
      <CodeBlock small>{cmd}</CodeBlock>
    </div>
  );
}

// ─── COST / TIME ESTIMATE ─────────────────────────────────────────────────────
function CostEstimate({ actionId, backend }) {
  const T = useTheme();
  const est = costEstimate(actionId, backend);
  if (!est) return null;
  const isFree = est.cost === 'Free';
  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'8px 12px',
        background: T.gray100, borderRadius:8,
        border:`1px solid ${T.border}` }}>
      <span style={{ display:'flex', color: isFree ? BRAND_DEEP : T.fg3 }}>
        <Ico.Clock/>
      </span>
      <div style={{ display:'flex', flexDirection:'column', flex:1, gap:1 }}>
        <span style={{ fontFamily:SANS, fontSize:11.5, color:T.fg4, fontWeight:500,
            letterSpacing:'0.3px', textTransform:'uppercase' }}>Estimate</span>
        <span style={{ fontFamily:MONO, fontSize:12, color:T.fg1, fontWeight:600,
            letterSpacing:'0.3px' }}>
          {est.cost} · {est.time}
        </span>
      </div>
      <span style={{ fontFamily:SANS, fontSize:10.5, color:T.fg4 }}>
        {isFree ? 'no API key' : backend}
      </span>
    </div>
  );
}

// ─── FREE-TIER GATE ───────────────────────────────────────────────────────────
function FreeTierGate({ onCancel, onProceed }) {
  const T = useTheme();
  const proceedRef = React.useRef(null);
  React.useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', onKey);
    proceedRef.current?.focus();
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel]);
  return (
    <div role="alertdialog" aria-modal="true"
      style={{ background:T.amberBgStrong || T.amberBg,
        borderLeft:`3px solid ${T.amberBorder}`,
        borderRadius:'4px 8px 8px 4px', padding:'14px 16px',
        animation:'fadeInUp 0.18s ease' }}>
      <div style={{ display:'flex', alignItems:'center', gap:7, marginBottom:8,
          color: T.amberText, fontFamily:SANS, fontSize:12.5, fontWeight:600 }}>
        <Ico.AlertTriangle /> Free tier — confirm before running
      </div>
      <ul style={{ listStyle:'none', padding:0, margin:'0 0 12px',
          display:'flex', flexDirection:'column', gap:4 }}>
        {[
          'No AI synthesis — sources only',
          'Quality depends on search coverage',
          'Tavily optional (1k/month free); DuckDuckGo fallback',
          'This is a starting point, not a finished report',
        ].map(t => (
          <li key={t} style={{ display:'flex', gap:8, fontFamily:SANS,
              fontSize:12, color: T.amberText, lineHeight:1.55 }}>
            <span style={{ marginTop:7, width:3, height:3, borderRadius:'50%',
              background:T.amberText, flexShrink:0 }}/>
            <span>{t}</span>
          </li>
        ))}
      </ul>
      <div style={{ display:'flex', gap:6, justifyContent:'flex-end' }}>
        <GhostBtn size="sm" onClick={onCancel}>Cancel</GhostBtn>
        <button ref={proceedRef} onClick={onProceed} className="tap"
          style={{ padding:'5px 14px', borderRadius:9999, background:BRAND,
            color:'#0d0d0d', fontFamily:SANS, fontSize:12.5, fontWeight:600,
            border:'none', cursor:'pointer' }}>
          Yes, proceed
        </button>
      </div>
    </div>
  );
}

// ─── FORMS ────────────────────────────────────────────────────────────────────
function FormTopic({ state, set }) {
  return <>
    <Field label="Topic">
      <Input value={state.topic} onChange={v=>set('topic', v)}
        placeholder="e.g. storm surge inundation under climate change" />
    </Field>
    <Field label="Backend">
      <BackendSelector value={state.backend} onChange={v=>set('backend', v)} />
      {state.backend === 'Free'
        ? <Note icon={<Ico.Sparkles/>}>No API key needed.</Note>
        : <Note tone="warn">Runs 3–30 min. May time out over MCP.</Note>}
    </Field>
    <Field label="Output destination" hint="Pipe → chains result into the next action">
      <Segmented value={state.dest} onChange={v=>set('dest', v)}
        options={['Local','Notebook','Vault','Pipe →']} />
    </Field>
    <GuideFiles files={state.guides} setFiles={v=>set('guides', v)} />
  </>;
}
function FormArtifact({ state, set }) {
  return <>
    <Field label="Artifact" hint="arXiv ID, PDF path, or URL">
      <Input value={state.artifact} onChange={v=>set('artifact', v)}
        placeholder="2401.12345 / paper.pdf / https://…" mono />
    </Field>
    <Field label="Backend">
      <BackendSelector value={state.backend === 'Free' ? 'Anthropic' : state.backend}
        onChange={v=>set('backend', v)} freeDisabled />
      <Note tone="warn">Runs 3–30 min. May time out over MCP.</Note>
    </Field>
    <GuideFiles files={state.guides} setFiles={v=>set('guides', v)} />
  </>;
}
function FormCompare({ state, set }) {
  return <>
    <Field label="Artifact A" hint="arXiv / PDF / URL">
      <Input value={state.artifactA} onChange={v=>set('artifactA', v)} placeholder="2401.12345" mono />
    </Field>
    <Field label="Artifact B" hint="arXiv / PDF / URL">
      <Input value={state.artifactB} onChange={v=>set('artifactB', v)} placeholder="2310.06825" mono />
    </Field>
    <Field label="Backend">
      <BackendSelector value={state.backend === 'Free' ? 'Anthropic' : state.backend}
        onChange={v=>set('backend', v)} freeDisabled />
      <Note tone="warn">Runs 3–30 min. May time out over MCP.</Note>
    </Field>
    <GuideFiles files={state.guides} setFiles={v=>set('guides', v)} />
  </>;
}
function FormSearch({ state, set }) {
  return <>
    <Field label="Query">
      <Input value={state.query} onChange={v=>set('query', v)}
        placeholder="e.g. coastal flooding bayesian" />
    </Field>
    <Field label="Max results">
      <Stepper value={state.maxResults} onChange={v=>set('maxResults', v)} min={1} max={100} />
    </Field>
  </>;
}
function FormGetPaper({ state, set }) {
  return <>
    <Field label="arXiv ID or URL">
      <Input value={state.arxivId} onChange={v=>set('arxivId', v)}
        placeholder="e.g. 2401.12345 or arxiv.org/abs/…" mono />
    </Field>
  </>;
}
function FormNotebook({ state, set }) {
  const T = useTheme();
  return <>
    <Field label="Output file path" hint="(optional)">
      <Input value={state.outPath} onChange={v=>set('outPath', v)}
        placeholder="Auto-detect most recent" mono />
    </Field>
    <Field label="Sources file path" hint="(optional)">
      <Input value={state.srcPath} onChange={v=>set('srcPath', v)}
        placeholder="sources.json" mono />
    </Field>
    <Field label="Max sources">
      <Stepper value={state.maxSources} onChange={v=>set('maxSources', v)} min={1} max={200} />
    </Field>
    <div style={{ display:'flex', flexDirection:'column', gap:8,
        padding:'10px 12px', background:T.gray100, borderRadius:8 }}>
      {[
        ['nlm','NLM research'],
        ['gate','Quality gate'],
        ['persp','Perspectives'],
      ].map(([k, lbl]) => (
        <div key={k} style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <span style={{ fontFamily:SANS, fontSize:12.5, color:T.fg2 }}>{lbl}</span>
          <Toggle checked={state[k]} onChange={v=>set(k, v)} />
        </div>
      ))}
    </div>
  </>;
}
function FormCfgShow() {
  const T = useTheme();
  return <div style={{ fontFamily:SANS, fontSize:12.5, color:T.fg3, lineHeight:1.5 }}>
    Display current configuration values. API keys are masked.
  </div>;
}
function FormCfgSet({ state, set }) {
  return <>
    <Field label="Key">
      <Input value={state.cfgKey} onChange={v=>set('cfgKey', v)}
        placeholder="anthropic_api_key" mono />
    </Field>
    <Field label="Value">
      <Input value={state.cfgVal} onChange={v=>set('cfgVal', v)}
        placeholder="sk-ant-…" mono />
    </Field>
  </>;
}
const FORM_MAP = {
  topic: FormTopic, artifact: FormArtifact, compare: FormCompare,
  search: FormSearch, getpaper: FormGetPaper, notebook: FormNotebook,
  cfgshow: FormCfgShow, cfgset: FormCfgSet,
};

function runLabel(action) {
  return action.id === 'search' || action.id === 'scholarly' ? 'Search'
       : action.id === 'getpaper' ? 'Look up'
       : action.id === 'cfgshow' ? 'Show config'
       : action.id === 'cfgset'  ? 'Save'
       : action.id === 'notebook'? 'Build notebook'
       : `Run ${action.label.toLowerCase()}`;
}

// ─── LEFT COLUMN ──────────────────────────────────────────────────────────────
function LeftColumn({ actionId, setActionId, state, set, onRun, gating, setGating,
                      presets, onDeletePreset, onSelectPreset, onOpenCmdK,
                      isRunning, onStop }) {
  const T = useTheme();
  const action = findAction(actionId);
  const Form = FORM_MAP[action.form];

  function handleRunClick() {
    const usesFree = (action.form === 'topic') && state.backend === 'Free';
    if (usesFree) setGating(true);
    else onRun();
  }

  // Drag-drop for guide files
  const [dragHover, setDragHover] = React.useState(false);
  const supportsGuides = ['topic','artifact','compare'].includes(action.form);

  function onDragOver(e) {
    if (!supportsGuides) return;
    e.preventDefault();
    if (e.dataTransfer?.types?.includes('Files')) setDragHover(true);
  }
  function onDragLeave(e) {
    // only clear if leaving the column entirely
    if (e.relatedTarget && e.currentTarget.contains(e.relatedTarget)) return;
    setDragHover(false);
  }
  function onDrop(e) {
    if (!supportsGuides) return;
    e.preventDefault();
    setDragHover(false);
    const files = Array.from(e.dataTransfer?.files || []);
    if (files.length) {
      const names = files.map(f => f.name);
      set('guides', [...(state.guides||[]), ...names]);
    }
  }

  return (
    <aside onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
      style={{ width:380, flexShrink:0, height:'100%',
        borderRight:`1px solid ${T.border}`, background:T.bg,
        display:'flex', flexDirection:'column', overflow:'hidden', position:'relative' }}>
      {/* Hero wash — bleeds behind header + top of action list */}
      <div aria-hidden="true" style={{ position:'absolute', inset:'0 0 auto 0',
        height:240, pointerEvents:'none', zIndex:0,
        background: T.dark ?
          `radial-gradient(ellipse 480px 280px at 30% -10%, ${BRAND}1f, transparent 60%),
           radial-gradient(ellipse 360px 220px at 90% 10%, ${VIOLET}14, transparent 60%)` :
          `radial-gradient(ellipse 480px 280px at 30% -10%, ${BRAND}26, transparent 60%),
           radial-gradient(ellipse 360px 220px at 90% 10%, ${VIOLET}1c, transparent 60%)`,
      }} />

      <div style={{ position:'relative', zIndex:1, padding:'18px 22px 12px',
          borderBottom:`1px solid ${T.border}`,
          display:'flex', alignItems:'center', justifyContent:'space-between', gap:10 }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:9, marginBottom:3 }}>
            <span style={{ color:BRAND_DEEP, display:'flex' }}><Ico.FlaskConical/></span>
            <h1 style={{ fontFamily:SANS, fontSize:18, fontWeight:600, color:T.fg1,
              letterSpacing:'-0.3px' }}>Studio</h1>
          </div>
          <p style={{ fontFamily:SANS, fontSize:12, color:T.fg3 }}>
            Run AI research actions
          </p>
        </div>
        <button onClick={onOpenCmdK} title="Quick action (⌘K)"
          style={{ display:'inline-flex', alignItems:'center', justifyContent:'center',
            gap:5, padding:'5px 8px', borderRadius:7,
            border:`1px solid ${T.borderMd}`, background:'transparent', cursor:'pointer',
            color:T.fg3 }}>
          <Ico.Search/>
          <Kbd>⌘K</Kbd>
        </button>
      </div>

      <div style={{ position:'relative', zIndex:1, flex:1, overflowY:'auto', padding:'14px 22px 0' }}>
        <ActionList
          activeId={state.activePresetId ? 'preset:'+state.activePresetId : actionId}
          onSelect={setActionId}
          presets={presets}
          onDeletePreset={onDeletePreset}
          onSelectPreset={onSelectPreset} />

        <div style={{ height:1, background:T.border, margin:'18px 0 16px' }} />

        <div style={{ marginBottom:12, fontFamily:MONO, fontSize:10, fontWeight:500,
            color:T.fg4, letterSpacing:'0.7px', textTransform:'uppercase',
            display:'flex', alignItems:'center', gap:8 }}>
          <span>{action.label}</span>
          <span style={{ flex:1, height:1, background:T.border }} />
        </div>

        <div style={{ display:'flex', flexDirection:'column', gap:14, paddingBottom:14 }}>
          <Form state={state} set={set} />

          {!['cfgshow','cfgset'].includes(action.id) && (
            <CommandPreview actionId={action.id} state={state} />
          )}
        </div>
      </div>

      <div style={{ padding:'12px 22px 18px', borderTop:`1px solid ${T.border}`,
          background:T.bg, flexShrink:0, display:'flex', flexDirection:'column', gap:10 }}>
        {!gating && !isRunning && <CostEstimate actionId={action.id} backend={state.backend} />}
        {gating ? (
          <FreeTierGate onCancel={()=>setGating(false)} onProceed={()=>{ setGating(false); onRun(); }} />
        ) : isRunning ? (
          <button onClick={onStop} className="tap"
            style={{ width:'100%', display:'inline-flex', alignItems:'center', justifyContent:'center',
              gap:7, padding:'9px 18px', borderRadius:9999,
              background:'transparent', border:`1px solid ${T.borderMd}`,
              color:RED, fontFamily:SANS, fontSize:13, fontWeight:600, cursor:'pointer' }}>
            <Ico.Square/> Stop run
          </button>
        ) : (
          <PrimaryBtn full icon={<Ico.Play/>} onClick={handleRunClick}>
            {runLabel(action)}
            <span style={{ marginLeft:'auto', display:'inline-flex', gap:3, opacity:0.7 }}>
              <Kbd>⌘</Kbd><Kbd>↵</Kbd>
            </span>
          </PrimaryBtn>
        )}
      </div>

      {dragHover && supportsGuides && (
        <div style={{ position:'absolute', inset:0, background: BRAND+'22',
            border:`2px dashed ${BRAND_DEEP}`, borderRadius:0, zIndex:10,
            display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
            gap:8, pointerEvents:'none' }}>
          <div style={{ width:48, height:48, borderRadius:12, background:BRAND+'33',
            display:'flex', alignItems:'center', justifyContent:'center', color:BRAND_DEEP }}>
            <Ico.Upload/>
          </div>
          <div style={{ fontFamily:SANS, fontSize:14, fontWeight:600, color:BRAND_DEEP }}>
            Drop to add as guide file
          </div>
        </div>
      )}
    </aside>
  );
}

// ─── CMD-K PALETTE ────────────────────────────────────────────────────────────
function CmdKPalette({ onClose, onSelect, recents = [] }) {
  const T = useTheme();
  const [q, setQ] = React.useState('');
  const [idx, setIdx] = React.useState(0);
  const inputRef = React.useRef(null);

  React.useEffect(() => {
    inputRef.current?.focus();
    function onKey(e) {
      if (e.key === 'Escape') { onClose(); }
      else if (e.key === 'ArrowDown') { setIdx(i => Math.min(i+1, results.length-1)); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { setIdx(i => Math.max(i-1, 0)); e.preventDefault(); }
      else if (e.key === 'Enter') { if (results[idx]) { onSelect(results[idx]); onClose(); } e.preventDefault(); }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  // Build results
  const ql = q.toLowerCase();
  const allWithRecent = recents.length
    ? [...recents.map(id => ({ ...findAction(id), _recent: true })).filter(Boolean), ...ALL_ACTIONS.filter(a => !recents.includes(a.id))]
    : ALL_ACTIONS;
  const results = ql
    ? ALL_ACTIONS.filter(a =>
        a.label.toLowerCase().includes(ql) ||
        a.group.toLowerCase().includes(ql) ||
        (a.desc || '').toLowerCase().includes(ql))
    : allWithRecent;

  React.useEffect(() => { setIdx(0); }, [q]);

  return (
    <div onClick={onClose}
      style={{ position:'fixed', inset:0, background:T.overlay, zIndex:200,
        display:'flex', alignItems:'flex-start', justifyContent:'center', paddingTop:'12vh',
        animation:'fadeInUp 0.12s ease' }}>
      <div onClick={e=>e.stopPropagation()}
        style={{ width:560, maxHeight:'70vh', background:T.card,
          border:`1px solid ${T.border}`, borderRadius:14,
          boxShadow:'rgba(0,0,0,0.18) 0px 12px 36px',
          display:'flex', flexDirection:'column', overflow:'hidden' }}>
        <div style={{ display:'flex', alignItems:'center', gap:10, padding:'12px 16px',
            borderBottom:`1px solid ${T.border}` }}>
          <span style={{ color:T.fg4, display:'flex' }}><Ico.Search/></span>
          <input ref={inputRef} value={q} onChange={e=>setQ(e.target.value)}
            placeholder="Search actions, presets, or paste an arXiv ID…"
            style={{ flex:1, padding:'4px 0', border:'none', outline:'none',
              fontFamily:SANS, fontSize:14, color:T.fg1, background:'transparent' }} />
          <span style={{ display:'inline-flex', gap:3 }}><Kbd>esc</Kbd></span>
        </div>
        <div style={{ flex:1, overflowY:'auto', padding:'6px 6px 8px' }}>
          {!q && recents.length > 0 && (
            <div style={{ padding:'8px 12px 6px', fontFamily:MONO, fontSize:9.5, color:T.fg4,
              letterSpacing:'0.7px', textTransform:'uppercase' }}>Recent</div>
          )}
          {results.length === 0 ? (
            <div style={{ padding:'22px 16px', textAlign:'center', fontFamily:SANS,
              fontSize:13, color:T.fg4 }}>
              No actions match "{q}"
            </div>
          ) : (
            results.map((a, i) => {
              const isHov = i === idx;
              return (
                <button key={a.id} onClick={()=>{ onSelect(a); onClose(); }}
                  onMouseEnter={()=>setIdx(i)}
                  style={{ width:'100%', display:'flex', alignItems:'center', gap:10,
                    padding:'9px 12px', borderRadius:8, border:'none', cursor:'pointer',
                    background: isHov ? BRAND+'1a' : 'transparent', textAlign:'left' }}>
                  <span style={{ display:'flex', color: isHov ? BRAND_DEEP : T.fg4, flexShrink:0 }}>
                    {a._recent ? <Ico.Clock/> :
                     a.group === 'Research' ? <Ico.Sparkles/> :
                     a.group === 'Utilities' ? <Ico.Search/> :
                     <Ico.Layers/>}
                  </span>
                  <div style={{ display:'flex', flexDirection:'column', flex:1, minWidth:0 }}>
                    <span style={{ fontFamily:SANS, fontSize:13, fontWeight:500,
                      color: isHov ? BRAND_DEEP : T.fg1 }}>{a.label}</span>
                    <span style={{ fontFamily:SANS, fontSize:11.5, color:T.fg4,
                      overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                      {a.desc}
                    </span>
                  </div>
                  <span style={{ fontFamily:MONO, fontSize:9.5, color:T.fg4,
                    letterSpacing:'0.5px', textTransform:'uppercase', flexShrink:0 }}>
                    {a.group}
                  </span>
                  {isHov && <span style={{ display:'inline-flex', gap:3, flexShrink:0 }}>
                    <Kbd>↵</Kbd>
                  </span>}
                </button>
              );
            })
          )}
        </div>
        <div style={{ padding:'8px 14px', borderTop:`1px solid ${T.border}`,
            background:T.surface,
            display:'flex', alignItems:'center', justifyContent:'space-between',
            fontFamily:MONO, fontSize:9.5, color:T.fg4, letterSpacing:'0.4px',
            textTransform:'uppercase' }}>
          <span style={{ display:'inline-flex', alignItems:'center', gap:5 }}>
            <Kbd>↑</Kbd><Kbd>↓</Kbd> navigate · <Kbd>↵</Kbd> select
          </span>
          <span style={{ display:'inline-flex', alignItems:'center', gap:5 }}>
            {results.length} actions
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── PRESET-SAVE MODAL ────────────────────────────────────────────────────────
function PresetSaveModal({ onClose, onSave, suggested = '' }) {
  const T = useTheme();
  const [name, setName] = React.useState(suggested);
  React.useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'Enter' && name.trim()) { onSave(name.trim()); onClose(); }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
  return (
    <div onClick={onClose}
      style={{ position:'fixed', inset:0, background:T.overlay, zIndex:200,
        display:'flex', alignItems:'center', justifyContent:'center',
        animation:'fadeInUp 0.12s ease' }}>
      <div onClick={e=>e.stopPropagation()}
        style={{ width:420, background:T.card, border:`1px solid ${T.border}`,
          borderRadius:14, padding:'18px 20px',
          boxShadow:'rgba(0,0,0,0.18) 0px 12px 36px' }}>
        <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:14 }}>
          <span style={{ color:BRAND_DEEP, display:'flex' }}><Ico.Bookmark/></span>
          <span style={{ fontFamily:SANS, fontSize:14, fontWeight:600, color:T.fg1 }}>
            Save as preset
          </span>
        </div>
        <Field label="Preset name">
          <Input autoFocus value={name} onChange={setName}
            placeholder="e.g. Weekly storm-surge lit scan" />
        </Field>
        <div style={{ display:'flex', justifyContent:'flex-end', gap:8, marginTop:16 }}>
          <GhostBtn size="sm" onClick={onClose}>Cancel</GhostBtn>
          <button onClick={()=>{ if(name.trim()){ onSave(name.trim()); onClose(); } }}
            disabled={!name.trim()}
            style={{ padding:'6px 14px', borderRadius:9999,
              background: name.trim() ? BRAND : '#a8e8cf',
              color:'#0d0d0d', fontFamily:SANS, fontSize:12.5, fontWeight:600,
              border:'none', cursor: name.trim() ? 'pointer':'not-allowed' }}>
            Save preset
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── EXPORT ───────────────────────────────────────────────────────────────────
Object.assign(window, { LeftColumn, CmdKPalette, PresetSaveModal });
