'use client';

/**
 * StudioRunProvider — layout-level context for Studio WS runs.
 *
 * Lifting run state + WS connection to the layout means navigation between
 * pages (Settings → Studio → Dashboard) does NOT kill an active run.
 * The Studio page reads state via `useStudioRun()` and stays a thin renderer.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from 'react';

import { useAppRun } from '@/lib/app-run-context';

import {
  findAction,
  actionSummary,
  type ActionId,
  type FormState,
  type LogEntry,
  type RunRecord,
  type Source,
  type Status,
} from '@/app/studio/_shared';

// ── Public input type ─────────────────────────────────────────────────────────

export interface StartRunInput {
  actionId: ActionId;
  form: FormState;
}

// ── Context value ─────────────────────────────────────────────────────────────

export interface StudioRunContextValue {
  /** Current run output state */
  status: Status;
  logs: LogEntry[];
  sources: Source[];
  currentPhase: string | null;
  doneData: Record<string, unknown> | null;
  gating: boolean;

  /** Run history (persisted to localStorage) */
  runs: RunRecord[];
  /** ID of the run currently displayed in the output panel (null = live run) */
  currentRunId: string | null;

  /** Start a new WS run. Fire-and-forget — state updates via React state. */
  startRun: (input: StartRunInput) => void;
  /** User-triggered stop: close WS, set status=stopped, push history record. */
  stop: () => void;
  /** Reset output panel to idle without affecting history. */
  reset: () => void;
  /**
   * Abort any active run (silently) and load a history record into the
   * output panel for viewing. Used by the history drawer's "load" action.
   */
  abortAndLoad: (record: RunRecord) => void;

  setGating: (g: boolean) => void;
  setRuns: Dispatch<SetStateAction<RunRecord[]>>;
}

// ── Internal mutable run state (captured in a ref to avoid stale closures) ───

interface RunRef {
  logs: LogEntry[];
  sources: Source[];
  phase: string | null;
  meta: StartRunInput | null;
  /** Captured result payload; set when the 'done' event arrives before pushRun. */
  doneData?: Record<string, unknown> | null;
}

// ── Context + hook ────────────────────────────────────────────────────────────

const StudioRunContext = createContext<StudioRunContextValue | null>(null);

export function useStudioRun(): StudioRunContextValue {
  const ctx = useContext(StudioRunContext);
  if (!ctx) throw new Error('useStudioRun must be called inside <StudioRunProvider>');
  return ctx;
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function StudioRunProvider({ children }: { children: ReactNode }) {
  const [status, setStatus]           = useState<Status>('idle');
  const [logs, setLogs]               = useState<LogEntry[]>([]);
  const [sources, setSources]         = useState<Source[]>([]);
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [doneData, setDoneData]         = useState<Record<string, unknown> | null>(null);
  const [gating, setGating]           = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);

  // Run history — bootstrapped from localStorage (client-side only)
  const [runs, setRuns] = useState<RunRecord[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const s = localStorage.getItem('docent-studio-runs');
      return s ? (JSON.parse(s) as RunRecord[]) : [];
    } catch { return []; }
  });

  // Persist history whenever it changes
  useEffect(() => {
    try { localStorage.setItem('docent-studio-runs', JSON.stringify(runs)); } catch { /* quota */ }
  }, [runs]);

  // Mutable ref tracks the active run's collected state so stop() / error
  // callbacks can access current logs without stale closure captures.
  const runRef = useRef<RunRef>({ logs: [], sources: [], phase: null, meta: null });

  // WS abort handle and stopped flag (also mutable refs, not state)
  const abortRef  = useRef<{ abort: () => void } | null>(null);
  const stoppedRef = useRef(false);

  // ── Helpers ─────────────────────────────────────────────────────────────────

  const closeWs = useCallback(() => {
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
  }, []);

  const pushRun = useCallback((
    finalStatus: 'success' | 'failure' | 'stopped',
    snapshot: RunRef,
  ) => {
    if (!snapshot.meta) return;
    const { actionId, form } = snapshot.meta;
    const actionMeta = findAction(actionId);
    const detail = actionSummary(actionMeta, form);
    setRuns(prev => [{
      id: 'r' + Date.now(),
      actionId,
      actionLabel: actionMeta.label,
      detail,
      status: finalStatus,
      timeAgo: 'just now',
      startedAt: Date.now(),
      state: { ...form },
      logs: snapshot.logs,
      sources: snapshot.sources,
      currentPhase: snapshot.phase,
      doneData: snapshot.doneData ?? null,
    }, ...prev]);
  }, []);

  // ── startRun ─────────────────────────────────────────────────────────────────

  const startRun = useCallback((input: StartRunInput) => {
    closeWs();
    stoppedRef.current = false;

    // Reset mutable tracking state
    runRef.current = { logs: [], sources: [], phase: null, meta: input };

    // Reset observable state
    setLogs([]);
    setSources([]);
    setDoneData(null);
    setStatus('running');
    setCurrentRunId(null);
    setCurrentPhase(null);

    const { actionId, form } = input;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/studio/run`);
    abortRef.current = { abort: () => ws.close() };

    ws.onopen = () => {
      ws.send(JSON.stringify({
        action_id:   actionId,
        topic:       form.topic,
        backend:     form.backend.toLowerCase(),
        dest:        form.dest.toLowerCase(),
        guides:      form.guides,
        artifact:    form.artifact,
        artifact_a:  form.artifactA,
        artifact_b:  form.artifactB,
        query:       form.query,
        max_results: form.maxResults,
        arxiv_id:    form.arxivId,
        out_path:    form.outPath,
        src_path:    form.srcPath,
        max_sources: form.maxSources,
        nlm:         form.nlm,
        gate:        form.gate,
        persp:       form.persp,
        cfg_key:     form.cfgKey,
        cfg_val:     form.cfgVal,
      }));
    };

    ws.onmessage = (e: MessageEvent) => {
      if (stoppedRef.current) return;
      let evt: Record<string, unknown>;
      try { evt = JSON.parse(e.data as string); } catch { return; }

      if (evt.type === 'log') {
        const entry: LogEntry = { phase: String(evt.phase), text: String(evt.text) };
        runRef.current.logs.push(entry);
        runRef.current.phase = String(evt.phase);
        setLogs(prev => [...prev, entry]);
        setCurrentPhase(String(evt.phase));
      } else if (evt.type === 'done') {
        const finalStatus = (evt.status as 'success' | 'failure') ?? 'success';
        if (evt.raw) {
          try {
            const parsed = JSON.parse(evt.raw as string) as Record<string, unknown>;
            setDoneData(parsed);
            // Capture in ref BEFORE pushRun so the record carries the output_file path.
            runRef.current.doneData = parsed;
          } catch {}
        }
        setStatus(finalStatus);
        pushRun(finalStatus, { ...runRef.current, logs: [...runRef.current.logs] });
        ws.close();
      } else if (evt.type === 'error') {
        const entry: LogEntry = { phase: 'error', text: String(evt.message) };
        runRef.current.logs.push(entry);
        runRef.current.phase = 'error';
        setLogs(prev => [...prev, entry]);
        setStatus('failure');
        pushRun('failure', { ...runRef.current, logs: [...runRef.current.logs] });
        ws.close();
      }
    };

    ws.onerror = () => {
      if (!stoppedRef.current) {
        const entry: LogEntry = { phase: 'error', text: 'Connection error — is the server running?' };
        runRef.current = { logs: [entry], sources: [], phase: 'error', meta: input };
        setLogs([entry]);
        setStatus('failure');
        pushRun('failure', { ...runRef.current });
      }
    };

    ws.onclose = () => {
      abortRef.current = null;
    };
  }, [closeWs, pushRun]);

  // ── stop ─────────────────────────────────────────────────────────────────────

  const stop = useCallback(() => {
    stoppedRef.current = true;
    closeWs();
    // Snapshot current mutable state before it's cleared
    const snapshot: RunRef = {
      logs: [...runRef.current.logs],
      sources: [...runRef.current.sources],
      phase: runRef.current.phase,
      meta: runRef.current.meta,
    };
    setStatus('stopped');
    pushRun('stopped', snapshot);
  }, [closeWs, pushRun]);

  // ── reset ─────────────────────────────────────────────────────────────────────

  const reset = useCallback(() => {
    closeWs();
    setStatus('idle');
    setLogs([]);
    setSources([]);
    setCurrentPhase(null);
    setDoneData(null);
    runRef.current = { logs: [], sources: [], phase: null, meta: null };
  }, [closeWs]);

  // ── abortAndLoad ──────────────────────────────────────────────────────────────

  const abortAndLoad = useCallback((record: RunRecord) => {
    // Silently close WS (no push to history — we're just switching view)
    stoppedRef.current = true;
    closeWs();
    // Display the history record's state in the output panel
    setStatus(record.status === 'running' ? 'success' : (record.status as Status));
    setLogs(record.logs);
    setSources(record.sources ?? []);
    setCurrentPhase(record.currentPhase);
    // Restore result payload so output_file shows correctly for historical runs.
    setDoneData(record.doneData ?? null);
    setCurrentRunId(record.id);
    runRef.current = {
      logs: record.logs,
      sources: record.sources ?? [],
      phase: record.currentPhase,
      meta: null,
    };
  }, [closeWs]);

  // ── Sync to AppRunContext ─────────────────────────────────────────────────────
  // This is how the generic status indicators (Sidebar pill, StatusBanner dot)
  // learn about Studio activity without coupling to Studio internals.

  const { setActivity } = useAppRun();

  useEffect(() => {
    if (status === 'running') {
      setActivity('studio', {
        label: 'Studio',
        phase: currentPhase ?? undefined,
        status: 'running',
      });
    } else if (status === 'idle') {
      setActivity('studio', null);
    } else {
      // success / failure / stopped — show briefly then auto-clear
      setActivity('studio', { label: 'Studio', status });
      const t = setTimeout(() => setActivity('studio', null), 3000);
      return () => clearTimeout(t);
    }
  }, [status, currentPhase, setActivity]);

  // ── Context value ─────────────────────────────────────────────────────────────

  return (
    <StudioRunContext.Provider value={{
      status, logs, sources, currentPhase, doneData, gating, runs, currentRunId,
      startRun, stop, reset, abortAndLoad,
      setGating, setRuns,
    }}>
      {children}
    </StudioRunContext.Provider>
  );
}
