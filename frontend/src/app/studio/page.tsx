'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from '@/components/Sidebar';
import StatusBanner, { type DotState } from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';
import { useTour } from '@/hooks/useTour';
import { LeftColumn, CmdKPalette, PresetSaveModal } from './_form';
import { OutputPanel, HistoryDrawer, OutputsPanel } from './_output';
import {
  findAction, actionSummary,
  type ActionId, type FormState,
  type Preset, type Status,
} from './_shared';
import { useStudioRun } from '@/lib/studio-run-context';

// ── Default form ──────────────────────────────────────────────────────────────

const DEFAULT_FORM: FormState = {
  topic: '', backend: 'Free', dest: 'Local', guides: [],
  artifact: '', artifactA: '', artifactB: '',
  query: '', maxResults: 10, arxivId: '',
  outPath: '', srcPath: '', maxSources: 20,
  nlm: true, gate: true, persp: true,
  cfgKey: '', cfgVal: '',
};

// ── Page ──────────────────────────────────────────────────────────────────────

export default function StudioPage() {
  const { dark, toggleDark } = useDarkMode();

  // Run state lives in the layout-level context so navigation doesn't kill it
  const run = useStudioRun();

  useTour('studio', [
    {
      popover: {
        title: 'Studio — your AI-powered academic workspace',
        description: 'Studio runs academic actions — deep research, literature reviews, peer reviews, paper comparisons, drafting, and more. Pick an action, fill in a topic or artifact, and run.',
      },
    },
    {
      popover: {
        title: 'Choose your backend',
        description: 'Four backends are available: Free (source aggregation, no AI cost), Docent (native multi-stage pipeline, requires OpenCode), Feynman (autonomous long-form research), and Groq (fast LLM via Groq API).',
      },
    },
    {
      popover: {
        title: 'Sources and output',
        description: 'The final output is saved to your configured research folder (Settings → Research output directory; defaults to ~/docent/research) and streams live in the output panel.',
      },
    },
    {
      popover: {
        title: 'Session history',
        description: 'Every Studio run is saved in the history drawer. Open it to revisit any past brief, re-run it with different settings, or compare outputs.',
      },
    },
  ]);

  // ── Form state (sessionStorage-persisted so tab navigation doesn't reset it) ─
  const [actionId, setActionId] = useState<ActionId>(() => {
    try { return (sessionStorage.getItem('studio-actionId') as ActionId) || 'deep'; } catch { return 'deep'; }
  });
  const [form, setForm] = useState<FormState>(() => {
    try {
      const s = sessionStorage.getItem('studio-form');
      return s ? { ...DEFAULT_FORM, ...(JSON.parse(s) as Partial<FormState>) } : DEFAULT_FORM;
    } catch { return DEFAULT_FORM; }
  });
  const set = useCallback((k: keyof FormState, v: unknown) => {
    setForm(s => ({ ...s, [k]: v }));
  }, []);

  // Persist form + actionId to sessionStorage
  useEffect(() => { try { sessionStorage.setItem('studio-actionId', actionId); } catch {} }, [actionId]);
  useEffect(() => { try { sessionStorage.setItem('studio-form', JSON.stringify(form)); } catch {} }, [form]);

  // ── Column resize ─────────────────────────────────────────────────────────────
  const [leftWidth, setLeftWidth] = useState<number>(() => {
    try { return parseInt(localStorage.getItem('studio-left-width') ?? '380', 10) || 380; } catch { return 380; }
  });
  const dragging   = useRef(false);
  const dragStartX = useRef(0);
  const dragStartW = useRef(0);

  function onDividerMouseDown(e: React.MouseEvent) {
    dragging.current = true;
    dragStartX.current = e.clientX;
    dragStartW.current = leftWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!dragging.current) return;
      const delta = e.clientX - dragStartX.current;
      const next = Math.max(260, Math.min(600, dragStartW.current + delta));
      setLeftWidth(next);
    }
    function onUp() {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      try { localStorage.setItem('studio-left-width', String(leftWidth)); } catch {}
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [leftWidth]);

  // ── Overlay / panel state ──────────────────────────────────────────────────────
  const [cmdKOpen, setCmdKOpen]           = useState(false);
  const [historyOpen, setHistoryOpen]     = useState(false);
  const [outputsOpen, setOutputsOpen]     = useState(false);
  const [savePresetOpen, setSavePresetOpen] = useState(false);

  // ── Presets ───────────────────────────────────────────────────────────────────
  const [presets, setPresets] = useState<Preset[]>([]);
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [recents, setRecents] = useState<ActionId[]>(['deep']);

  const action = findAction(actionId);

  // ── Run handlers (thin wrappers over context) ─────────────────────────────────

  function handleRun() {
    setRecents(prev => [actionId, ...prev.filter(x => x !== actionId)].slice(0, 4) as ActionId[]);
    run.startRun({ actionId, form });
  }

  function handleStop() {
    run.stop();
  }

  function handleReset() {
    run.reset();
  }

  function handlePipeToNotebook(srcPath: string) {
    setActionId('notebook');
    setForm(s => ({ ...s, srcPath }));
    // Fire immediately with overrides — bypasses form state lag
    run.reset();
    run.startRun({ actionId: 'notebook', form: { ...form, srcPath } });
  }

  // ── Preset handlers ────────────────────────────────────────────────────────────
  function handleSelectPreset(p: Preset) {
    setActionId(p.actionId);
    setForm(s => ({ ...s, ...p.params }));
    setActivePresetId(p.id);
  }
  function handleDeletePreset(id: string) {
    setPresets(prev => prev.filter(p => p.id !== id));
    if (activePresetId === id) setActivePresetId(null);
  }
  function handleSavePreset(name: string) {
    const np: Preset = { id: 'p' + Date.now(), name, actionId, params: { ...form } };
    setPresets(prev => [np, ...prev]);
  }

  // ── History load ───────────────────────────────────────────────────────────────
  function handleLoadRun(id: string) {
    const r = run.runs.find(x => x.id === id);
    if (!r) return;
    // Abort any active run and display the history record
    run.abortAndLoad(r);
    // Restore the form so user can re-run with the same inputs
    setActionId(r.actionId);
    setForm(s => ({ ...s, ...r.state }));
  }

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────────
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault(); setCmdKOpen(o => !o);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && run.status !== 'running' && !run.gating) {
        e.preventDefault();
        const a = action;
        if (a.form === 'topic' && !form.topic.trim()) return;
        if (a.form === 'artifact' && !form.artifact.trim()) return;
        if (a.form === 'compare' && (!form.artifactA.trim() || !form.artifactB.trim())) return;
        if (a.form === 'search' && !form.query.trim()) return;
        if (a.form === 'getpaper' && !form.arxivId.trim()) return;
        handleRun();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run.status, run.gating, actionId, form]);

  // Note: no cleanup useEffect that calls stopRun — the provider is layout-level
  // and keeps the WS alive across navigation. Only explicit user stop kills it.

  // ── Derived values ─────────────────────────────────────────────────────────────

  // Sidebar reads currentRun from the context directly — no prop needed.
  const dotState: DotState =
    run.status === 'running' ? 'working' :
    run.status === 'failure' ? 'error' :
    (run.status === 'success' || run.status === 'stopped') ? 'done' : 'idle';

  const suggestedPresetName = action.label + ' · ' + (actionSummary(action, form) || '').slice(0, 30);

  // ── Render ─────────────────────────────────────────────────────────────────────

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="studio" queueCount={0} dark={dark} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner
          dark={dark} onToggleDark={toggleDark} dotState={dotState}
          onOpenCmdK={() => setCmdKOpen(true)}
          onOpenHistory={() => setHistoryOpen(o => !o)}
          historyOpen={historyOpen}
          runCount={run.runs.length}
          onOpenOutputs={() => setOutputsOpen(o => !o)}
          outputsOpen={outputsOpen}
        />
        <div style={{
          flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden',
          background: dark
            ? 'linear-gradient(135deg, rgba(24,226,153,0.07) 0%, rgba(139,92,246,0.04) 45%, transparent 75%)'
            : 'linear-gradient(135deg, rgba(24,226,153,0.22) 0%, rgba(139,92,246,0.13) 45%, transparent 75%)',
        }}>
          <LeftColumn
            actionId={actionId} setActionId={id => { setActionId(id); setActivePresetId(null); }}
            state={form} set={set}
            onRun={handleRun}
            gating={run.gating} setGating={run.setGating}
            presets={presets}
            onDeletePreset={handleDeletePreset}
            onSelectPreset={handleSelectPreset}
            onOpenCmdK={() => setCmdKOpen(true)}
            isRunning={run.status === 'running'}
            onStop={handleStop}
            activePresetId={activePresetId}
            width={leftWidth}
          />
          {/* Resize divider */}
          <div
            onMouseDown={onDividerMouseDown}
            title="Drag to resize"
            style={{ width: 4, flexShrink: 0, cursor: 'col-resize', background: 'transparent', transition: 'background 0.15s', position: 'relative', zIndex: 1 }}
            className="studio-resize-divider"
          />
          <OutputPanel
            action={action} state={form}
            status={run.status} logs={run.logs} sources={run.sources}
            currentPhase={run.currentPhase}
            doneData={run.doneData}
            onReset={handleReset}
            onSaveAsPreset={() => setSavePresetOpen(true)}
            onPipeToNotebook={handlePipeToNotebook}
          />
          {historyOpen && (
            <div style={{ animation: 'slideInRight 0.18s ease forwards' }}>
              <HistoryDrawer
                runs={run.runs} currentRunId={run.currentRunId}
                onSelect={handleLoadRun}
                onClose={() => setHistoryOpen(false)}
                onClear={() => run.setRuns([])}
                onDelete={(id) => run.setRuns(prev => prev.filter(r => r.id !== id))}
              />
            </div>
          )}
          {outputsOpen && (
            <div style={{ animation: 'slideInRight 0.18s ease forwards' }}>
              <OutputsPanel onClose={() => setOutputsOpen(false)} />
            </div>
          )}
        </div>
      </div>

      {cmdKOpen && (
        <CmdKPalette
          onClose={() => setCmdKOpen(false)}
          onSelect={a => { setActionId(a.id); setActivePresetId(null); }}
          recents={recents}
        />
      )}
      {savePresetOpen && (
        <PresetSaveModal
          onClose={() => setSavePresetOpen(false)}
          onSave={handleSavePreset}
          suggested={suggestedPresetName}
        />
      )}
    </div>
  );
}
