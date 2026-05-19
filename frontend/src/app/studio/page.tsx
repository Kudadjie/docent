'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from '@/components/Sidebar';
import StatusBanner, { type DotState } from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';
import { LeftColumn, CmdKPalette, PresetSaveModal } from './_form';
import { OutputPanel, HistoryDrawer } from './_output';
import {
  ACTION_PHASES, ACTIONS, findAction, actionSummary,
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
  const abortRef  = useRef<AbortController | null>(null);
  const stoppedRef = useRef(false);

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

  // ── Run helpers ─────────────────────────────────────────────────────────────
  function stopRun() {
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
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

  async function startRun() {
    stopRun();
    stoppedRef.current = false;
    const collectedLogs: LogEntry[] = [];
    const collectedSources: Source[] = [];
    setLogs([]);
    setSources([]);
    setStatus('running');
    setCurrentRunId(null);
    setCurrentPhase(ACTION_PHASES[actionId]?.[0] ?? null);
    setRecents(prev => [actionId, ...prev.filter(x => x !== actionId)].slice(0, 4) as ActionId[]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch('/api/studio/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_id: actionId,
          topic:      form.topic,
          backend:    form.backend.toLowerCase(),
          dest:       form.dest.toLowerCase().replace(' →', '').trim(),
          guides:     form.guides,
          artifact:   form.artifact,
          artifact_a: form.artifactA,
          artifact_b: form.artifactB,
          query:      form.query,
          max_results: form.maxResults,
          arxiv_id:   form.arxivId,
          out_path:   form.outPath,
          src_path:   form.srcPath,
          max_sources: form.maxSources,
          nlm:  form.nlm,
          gate: form.gate,
          persp: form.persp,
          cfg_key: form.cfgKey,
          cfg_val: form.cfgVal,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const errText = await res.text().catch(() => 'Unknown error');
        const entry: LogEntry = { phase: 'error', text: errText };
        collectedLogs.push(entry);
        setLogs([entry]);
        if (!stoppedRef.current) { setStatus('failure'); pushRun('failure', collectedLogs, [], 'error'); }
        return;
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      let finalStatus: 'success' | 'failure' = 'success';
      let lastPhase: string | null = null;

      try {
        outer: while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split('\n');
          buf = lines.pop() ?? '';
          for (const raw of lines) {
            if (!raw.startsWith('data: ')) continue;
            let evt: Record<string, unknown>;
            try { evt = JSON.parse(raw.slice(6)); } catch { continue; }

            if (evt.type === 'log') {
              const entry: LogEntry = { phase: String(evt.phase), text: String(evt.text) };
              collectedLogs.push(entry);
              setLogs(prev => [...prev, entry]);
              lastPhase = entry.phase;
              setCurrentPhase(entry.phase);
            } else if (evt.type === 'done') {
              finalStatus = (evt.status as 'success' | 'failure') ?? 'success';
              break outer;
            } else if (evt.type === 'error') {
              const entry: LogEntry = { phase: 'error', text: String(evt.message) };
              collectedLogs.push(entry);
              setLogs(prev => [...prev, entry]);
              finalStatus = 'failure';
              lastPhase = 'error';
              break outer;
            }
          }
        }
      } finally {
        reader.releaseLock();
      }

      if (!stoppedRef.current) {
        setStatus(finalStatus);
        pushRun(finalStatus, collectedLogs, collectedSources, lastPhase);
      }
    } catch (err: unknown) {
      if ((err as Error)?.name === 'AbortError') return;
      const entry: LogEntry = { phase: 'error', text: err instanceof Error ? err.message : String(err) };
      collectedLogs.push(entry);
      setLogs(prev => [...prev, entry]);
      if (!stoppedRef.current) { setStatus('failure'); pushRun('failure', collectedLogs, [], 'error'); }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }

  function handleRun()  { void startRun(); }
  function handleStop() {
    stoppedRef.current = true;
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

  const dotState: DotState = status === 'running' ? 'working' : status === 'failure' ? 'error' : status === 'success' ? 'done' : 'idle';

  const suggestedPresetName = action.label + ' · ' + (actionSummary(action, form) || '').slice(0, 30);

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="studio" queueCount={0} dark={dark} currentRun={currentRunForSidebar} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner
          dark={dark} onToggleDark={toggleDark} dotState={dotState}
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
