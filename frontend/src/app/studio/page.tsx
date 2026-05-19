'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';
import { LeftColumn, CmdKPalette, PresetSaveModal } from './_form';
import { OutputPanel, HistoryDrawer } from './_output';
import {
  ACTIONS, findAction, scriptFor, actionSummary,
  type ActionId, type ActionMeta, type FormState,
  type LogEntry, type Source, type Preset, type RunRecord, type Status,
} from './_shared';

const DEFAULT_FORM: FormState = {
  topic: '', backend: 'Free', dest: 'Local', guides: [],
  artifact: '', artifactA: '', artifactB: '',
  query: '', maxResults: 10, arxivId: '',
  outPath: '', srcPath: '', maxSources: 20,
  nlm: true, gate: true, persp: true,
  cfgKey: '', cfgVal: '',
};

export default function StudioPage() {
  const { dark, toggleDark } = useDarkMode();

  // ── Form state ──────────────────────────────────────────────────────────────
  const [actionId, setActionId] = useState<ActionId>('deep');
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const set = useCallback((k: keyof FormState, v: unknown) => {
    setForm(s => ({ ...s, [k]: v }));
  }, []);

  // ── Run state ───────────────────────────────────────────────────────────────
  const [status, setStatus]           = useState<Status>('idle');
  const [logs, setLogs]               = useState<LogEntry[]>([]);
  const [sources, setSources]         = useState<Source[]>([]);
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [gating, setGating]           = useState(false);
  const runRef = useRef<{ timer: ReturnType<typeof setTimeout> | null; idx: number }>({ timer: null, idx: 0 });

  // ── Overlay / panel state ───────────────────────────────────────────────────
  const [cmdKOpen, setCmdKOpen]           = useState(false);
  const [historyOpen, setHistoryOpen]     = useState(false);
  const [savePresetOpen, setSavePresetOpen] = useState(false);

  // ── Presets ─────────────────────────────────────────────────────────────────
  const [presets, setPresets] = useState<Preset[]>([]);
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [recents, setRecents] = useState<ActionId[]>(['deep']);

  // ── Run history ─────────────────────────────────────────────────────────────
  const [runs, setRuns]               = useState<RunRecord[]>([]);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);

  const action = findAction(actionId);

  // ── Timer helpers ───────────────────────────────────────────────────────────
  function stopRun() {
    if (runRef.current.timer) { clearTimeout(runRef.current.timer); runRef.current.timer = null; }
  }

  function pushRun(finalStatus: 'success' | 'failure', finalLogs: LogEntry[], finalSources: Source[], finalPhase: string | null) {
    const detail = actionSummary(action, form);
    setRuns(prev => [{
      id: 'r' + Date.now(),
      actionId,
      actionLabel: action.label,
      detail,
      status: finalStatus,
      timeAgo: 'just now',
      startedAt: Date.now(),
      state: { ...form },
      logs: finalLogs,
      sources: finalSources,
      currentPhase: finalPhase,
    }, ...prev]);
  }

  function startRun() {
    stopRun();
    const script = scriptFor(actionId);
    const collectedLogs: LogEntry[] = [];
    const collectedSources: Source[] = [];
    setLogs([]);
    setSources([]);
    setStatus('running');
    setCurrentRunId(null);
    setCurrentPhase(script[0]?.phase ?? null);
    setRecents(prev => [actionId, ...prev.filter(x => x !== actionId)].slice(0, 4) as ActionId[]);
    runRef.current.idx = 0;

    const tick = () => {
      const i = runRef.current.idx;
      if (i >= script.length) {
        setStatus('success');
        pushRun('success', collectedLogs, collectedSources, collectedLogs[collectedLogs.length - 1]?.phase ?? null);
        runRef.current.timer = null;
        return;
      }
      const line = script[i];
      collectedLogs.push(line);
      setLogs(prev => [...prev, line]);
      if (line.sources) {
        collectedSources.push(...line.sources);
        setSources(prev => [...prev, ...(line.sources ?? [])]);
      }
      setCurrentPhase(line.phase);
      runRef.current.idx = i + 1;
      runRef.current.timer = setTimeout(tick, 650 + Math.random() * 220);
    };
    tick();
  }

  function handleRun()  { startRun(); }
  function handleStop() {
    stopRun();
    setStatus('success');
    pushRun('success', logs, sources, currentPhase);
  }
  function handleReset() {
    stopRun(); setStatus('idle'); setLogs([]); setSources([]); setCurrentPhase(null);
  }

  function handlePipeToNotebook() {
    setActionId('notebook');
    set('srcPath', '~/docent/runs/current/sources.json');
    setStatus('idle'); setLogs([]); setSources([]);
  }

  // ── Preset handlers ─────────────────────────────────────────────────────────
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

  // ── History load ─────────────────────────────────────────────────────────────
  function handleLoadRun(id: string) {
    const r = runs.find(x => x.id === id);
    if (!r) return;
    stopRun();
    setActionId(r.actionId);
    setForm(s => ({ ...s, ...r.state }));
    setLogs(r.logs);
    setSources(r.sources ?? []);
    setCurrentPhase(r.currentPhase);
    setStatus(r.status === 'running' ? 'success' : r.status);
    setCurrentRunId(r.id);
  }

  // ── Keyboard shortcuts ───────────────────────────────────────────────────────
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault(); setCmdKOpen(o => !o);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && status !== 'running' && !gating) {
        e.preventDefault(); handleRun();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [status, gating, actionId, form]);

  useEffect(() => () => stopRun(), []);

  const currentRunForSidebar = status === 'running'
    ? { status: 'running' as const, currentPhase: (currentPhase ?? 'run').slice(0, 7) }
    : null;

  const suggestedPresetName = action.label + ' · ' + (actionSummary(action, form) || '').slice(0, 30);

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="studio" queueCount={0} dark={dark} currentRun={currentRunForSidebar} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner
          dark={dark} onToggleDark={toggleDark} dotState="idle"
          onOpenCmdK={() => setCmdKOpen(true)}
          onOpenHistory={() => setHistoryOpen(o => !o)}
          historyOpen={historyOpen}
          runCount={runs.length}
        />
        <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
          <LeftColumn
            actionId={actionId} setActionId={id => { setActionId(id); setActivePresetId(null); }}
            state={form} set={set}
            onRun={handleRun}
            gating={gating} setGating={setGating}
            presets={presets}
            onDeletePreset={handleDeletePreset}
            onSelectPreset={handleSelectPreset}
            onOpenCmdK={() => setCmdKOpen(true)}
            isRunning={status === 'running'}
            onStop={handleStop}
            activePresetId={activePresetId}
          />
          <OutputPanel
            action={action} state={form}
            status={status} logs={logs} sources={sources}
            currentPhase={currentPhase}
            onReset={handleReset}
            onSaveAsPreset={() => setSavePresetOpen(true)}
            onPipeToNotebook={handlePipeToNotebook}
          />
          {historyOpen && (
            <div style={{ animation: 'slideInRight 0.18s ease forwards' }}>
              <HistoryDrawer
                runs={runs} currentRunId={currentRunId}
                onSelect={handleLoadRun}
                onClose={() => setHistoryOpen(false)}
                onClear={() => setRuns([])}
              />
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
