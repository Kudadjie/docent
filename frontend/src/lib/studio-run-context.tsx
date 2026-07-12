'use client';

/**
 * StudioRunProvider — layout-level context for Studio background-job runs.
 *
 * Holds MULTIPLE concurrent runs, keyed by runId. Each run is submitted to the
 * backend as a background job (POST /api/studio/submit) and polled via
 * GET /api/jobs/{id} every POLL_MS — the single transport since the v2.3
 * rewire (the WS-subprocess and SSE streams are gone; jobs survive page
 * reloads server-side and poll batches arrive ~2s apart instead of instantly).
 * The output panel shows one "viewed" run at a time (chosen via the run
 * switcher); the legacy flat fields (status/logs/sources/currentPhase/doneData)
 * are derived from that viewed run so existing consumers keep working.
 *
 * Lifting this to the layout means navigation between pages does NOT kill runs.
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
// Side-effect import: patches window.fetch to attach X-Docent-Token on
// mutating /api requests (submit + cancel here). Must load with the layout
// bundle, before any fetch.
import '@/lib/api-token';

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

// ── A concurrent run as seen by the UI (render-safe snapshot) ───────────────────

export interface ActiveRunView {
  runId: string;
  actionId: ActionId;
  actionLabel: string;
  detail: string;
  status: Status;
  phase: string | null;
  logs: LogEntry[];
  sources: Source[];
  doneData: Record<string, unknown> | null;
  startedAt: number;
  /** Why a run is parked in `queued` (e.g. "NotebookLM busy"). */
  queuedReason?: string;
  /** The form the run was launched with — lets the output panel render the
   *  viewed run's result correctly even when the live form has moved on. */
  form: FormState;
}

// ── Context value ─────────────────────────────────────────────────────────────

export interface StudioRunContextValue {
  /** Viewed-run output state (derived from the currently-viewed run/record). */
  status: Status;
  logs: LogEntry[];
  sources: Source[];
  currentPhase: string | null;
  doneData: Record<string, unknown> | null;
  gating: boolean;

  /** Every concurrent run currently held (running + finished-not-cleared). */
  activeRuns: ActiveRunView[];
  /** True while any run is still streaming. */
  anyRunning: boolean;

  /** Run history (persisted to localStorage) */
  runs: RunRecord[];
  /** ID of the run/record currently displayed in the output panel (null = idle). */
  currentRunId: string | null;

  /** Start a new WS run alongside any existing runs. Returns the new runId. */
  startRun: (input: StartRunInput) => string;
  /** Switch the output panel to view a given active run. */
  viewRun: (runId: string) => void;
  /** Stop a run (default: the currently-viewed run): close WS, mark stopped, push history. */
  stop: (runId?: string) => void;
  /** Clear the output view; drops the viewed run from the active list if finished. */
  reset: () => void;
  /** Load a history record into the output panel WITHOUT touching active runs. */
  abortAndLoad: (record: RunRecord) => void;

  setGating: (g: boolean) => void;
  setRuns: Dispatch<SetStateAction<RunRecord[]>>;
}

// ── Internal mutable run record (lives in a ref to dodge stale closures) ─────────

interface InternalRun {
  runId: string;
  meta: StartRunInput;
  status: Status;
  logs: LogEntry[];
  sources: Source[];
  phase: string | null;
  doneData: Record<string, unknown> | null;
  startedAt: number;
  /** Backend job id once submitted (null while client-queued / before submit). */
  jobId: string | null;
  pollTimer: ReturnType<typeof setInterval> | null;
  /** Consecutive failed polls — the run fails after POLL_MAX_ERRORS. */
  pollErrors: number;
  stopped: boolean;
  queuedReason?: string;
}

const POLL_MS = 2000;
const POLL_MAX_ERRORS = 5; // ~10s of unreachable server → mark the run failed

// ── Context + hook ────────────────────────────────────────────────────────────

const StudioRunContext = createContext<StudioRunContextValue | null>(null);

export function useStudioRun(): StudioRunContextValue {
  const ctx = useContext(StudioRunContext);
  if (!ctx) throw new Error('useStudioRun must be called inside <StudioRunProvider>');
  return ctx;
}

// ── Provider ──────────────────────────────────────────────────────────────────

let _runSeq = 0;
function _newRunId(): string {
  _runSeq += 1;
  return `r${Date.now()}_${_runSeq}`;
}

export function StudioRunProvider({ children }: { children: ReactNode }) {
  const [gating, setGating]             = useState(false);
  const [activeRuns, setActiveRuns]     = useState<ActiveRunView[]>([]);
  const [viewedRunId, setViewedRunId]   = useState<string | null>(null);
  const [viewedHistory, setViewedHistory] = useState<RunRecord | null>(null);

  // Run history — bootstrapped from localStorage (client-side only)
  const [runs, setRuns] = useState<RunRecord[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const s = localStorage.getItem('docent-studio-runs');
      return s ? (JSON.parse(s) as RunRecord[]) : [];
    } catch { return []; }
  });

  useEffect(() => {
    try { localStorage.setItem('docent-studio-runs', JSON.stringify(runs)); } catch { /* quota */ }
  }, [runs]);

  // Source of truth for live runs. The Map holds mutable per-run buffers + WS.
  const runsRef = useRef<Map<string, InternalRun>>(new Map());

  // ── Snapshot helper: rebuild the render array from the ref ─────────────────────

  const syncActiveRuns = useCallback(() => {
    const views: ActiveRunView[] = [];
    for (const r of runsRef.current.values()) {
      const actionMeta = findAction(r.meta.actionId);
      views.push({
        runId: r.runId,
        actionId: r.meta.actionId,
        actionLabel: actionMeta.label,
        detail: actionSummary(actionMeta, r.meta.form),
        status: r.status,
        phase: r.phase,
        logs: [...r.logs],
        sources: [...r.sources],
        doneData: r.doneData,
        startedAt: r.startedAt,
        queuedReason: r.queuedReason,
        form: r.meta.form,
      });
    }
    views.sort((a, b) => a.startedAt - b.startedAt);
    setActiveRuns(views);
  }, []);

  const pushRun = useCallback((run: InternalRun, finalStatus: 'success' | 'failure' | 'stopped') => {
    const { actionId, form } = run.meta;
    const actionMeta = findAction(actionId);
    setRuns(prev => [{
      id: run.runId,
      actionId,
      actionLabel: actionMeta.label,
      detail: actionSummary(actionMeta, form),
      status: finalStatus,
      timeAgo: 'just now',
      startedAt: run.startedAt,
      state: { ...form },
      logs: [...run.logs],
      sources: [...run.sources],
      currentPhase: run.phase,
      doneData: run.doneData ?? null,
    }, ...prev]);
  }, []);

  // ── Admission control (parallel cap + NotebookLM exclusivity) ─────────────────
  // The parallel cap comes from research.max_parallel_studio_runs (default 3).
  // NotebookLM is single-session, so only ONE to-notebook run may be live at a
  // time — a second parks in `queued` and self-starts when the first finishes.

  const capRef = useRef<number>(3);
  useEffect(() => {
    if (typeof fetch !== 'function') return;  // e.g. SSR / test env without fetch
    let cancelled = false;
    fetch('/api/config')
      .then(r => r.json())
      .then(c => {
        const n = Number(c?.research?.max_parallel_studio_runs);
        if (!cancelled && Number.isFinite(n) && n >= 1) capRef.current = n;
      })
      .catch(() => { /* keep default */ });
    return () => { cancelled = true; };
  }, []);

  // Decide whether a run may start NOW. The only client-side gate is the parallel
  // cap. NotebookLM exclusivity is NOT enforced here on purpose: a notebook-bound
  // run spends most of its life doing research that has nothing to do with NLM, so
  // queuing the whole run would needlessly serialize the expensive part. The server
  // mutex serializes only the actual NLM touchpoints (auth + push), letting runs
  // research concurrently and surfacing a brief "Waiting: NotebookLM busy" only at
  // those moments.
  const admit = useCallback((run: InternalRun): { start: boolean; reason?: string } => {
    void run;
    const running = [...runsRef.current.values()].filter(r => r.status === 'running');
    if (running.length >= capRef.current) {
      return { start: false, reason: `Queued — ${running.length} runs already active (max ${capRef.current}).` };
    }
    return { start: true };
  }, []);

  const admitQueuedRef = useRef<() => void>(() => {});

  // Submit a run as a backend job and poll it to completion. Used by startRun
  // and by tryAdmitQueued when a queued run is promoted.

  const stopPolling = useCallback((run: InternalRun) => {
    if (run.pollTimer !== null) { clearInterval(run.pollTimer); run.pollTimer = null; }
  }, []);

  const finishRun = useCallback((run: InternalRun, finalStatus: 'success' | 'failure' | 'stopped') => {
    stopPolling(run);
    run.status = finalStatus;
    pushRun(run, finalStatus);
    syncActiveRuns();
    admitQueuedRef.current();
  }, [pushRun, stopPolling, syncActiveRuns]);

  const applyJobSnapshot = useCallback((run: InternalRun, job: Record<string, unknown>) => {
    // Rebuild the log from the job's event list (bounded server-side at 500).
    const events = Array.isArray(job.events) ? (job.events as Record<string, unknown>[]) : [];
    run.logs = events.map(e => ({ phase: String(e.phase ?? ''), text: String(e.message ?? '') }));
    if (events.length > 0) run.phase = String(events[events.length - 1].phase ?? '');

    const state = String(job.state ?? '');
    if (state === 'queued') {
      // Admitted client-side but waiting for a server slot (serve.jobs_max_concurrent).
      run.phase = 'queued';
      syncActiveRuns();
    } else if (state === 'running') {
      syncActiveRuns();
    } else if (state === 'done') {
      let result: Record<string, unknown> | null = null;
      try { result = JSON.parse(String(job.result_json ?? 'null')); } catch {}
      const ok = !result || result.ok !== false;
      if (result) {
        // Same envelope the WS path used to build, so _output.tsx panels keep
        // working: top-level convenience fields + the full result under `data`.
        run.doneData = {
          ok,
          output_file: result.output_file,
          notebook_id: result.notebook_id,
          message: result.message,
          data: result,
        };
        if (!ok && result.message) {
          run.logs.push({ phase: 'error', text: String(result.message) });
          run.phase = 'error';
        }
      }
      finishRun(run, ok ? 'success' : 'failure');
    } else if (state === 'failed' || state === 'interrupted') {
      const err = String(job.error ?? 'Job failed — check the activity log.');
      run.logs.push({ phase: 'error', text: err });
      run.phase = 'error';
      finishRun(run, 'failure');
    } else if (state === 'cancelled') {
      // Cancelled server-side (from this tab's stop() or elsewhere, e.g. the
      // jobs CLI). stop() already pushed history for local stops.
      stopPolling(run);
      if (!run.stopped) finishRun(run, 'stopped');
    }
  }, [finishRun, stopPolling, syncActiveRuns]);

  const startJob = useCallback((run: InternalRun) => {
    run.status = 'running';
    run.queuedReason = undefined;
    syncActiveRuns();

    const { actionId, form } = run.meta;
    const fail = (text: string) => {
      const r = runsRef.current.get(run.runId);
      if (!r || r.stopped) return;
      r.logs.push({ phase: 'error', text });
      r.phase = 'error';
      finishRun(r, 'failure');
    };

    fetch('/api/studio/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
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
        cfg_key:         form.cfgKey,
        cfg_val:         form.cfgVal,
        cite_identifier:   form.citeIdentifier,
        cite_direction:    form.citeDirection,
        cite_max:          form.citeMax,
        expand_citations:  form.expandCitations,
      }),
    })
      .then(async res => {
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(String(body?.error ?? `Submit failed (HTTP ${res.status})`));
        }
        return res.json();
      })
      .then((data: { job_id?: string }) => {
        const r = runsRef.current.get(run.runId);
        if (!r) return;
        if (!data.job_id) throw new Error('Submit returned no job id');
        r.jobId = data.job_id;
        if (r.stopped) {
          // Stopped between submit and response — cancel the orphaned job.
          void fetch(`/api/jobs/${data.job_id}/cancel`, { method: 'POST' }).catch(() => {});
          return;
        }
        r.pollTimer = setInterval(() => {
          const cur = runsRef.current.get(run.runId);
          if (!cur || cur.stopped) { if (cur) stopPolling(cur); return; }
          fetch(`/api/jobs/${cur.jobId}`)
            .then(res => {
              if (!res.ok) throw new Error(`HTTP ${res.status}`);
              return res.json();
            })
            .then((job: Record<string, unknown>) => {
              cur.pollErrors = 0;
              applyJobSnapshot(cur, job);
            })
            .catch(() => {
              cur.pollErrors += 1;
              if (cur.pollErrors >= POLL_MAX_ERRORS) {
                fail('Connection error — is the server running?');
              }
            });
        }, POLL_MS);
      })
      .catch((exc: unknown) => fail(String(exc instanceof Error ? exc.message : exc)));
  }, [applyJobSnapshot, finishRun, stopPolling, syncActiveRuns]);

  // Promote queued runs (oldest first) whose blocking condition has cleared.
  const tryAdmitQueued = useCallback(() => {
    const queued = [...runsRef.current.values()]
      .filter(r => r.status === 'queued')
      .sort((a, b) => a.startedAt - b.startedAt);
    for (const r of queued) {
      // admit() re-reads the live running set, which startJob() mutates as we
      // go, so the cap stays correct across the loop.
      if (admit(r).start) startJob(r);
    }
  }, [admit, startJob]);
  useEffect(() => { admitQueuedRef.current = tryAdmitQueued; }, [tryAdmitQueued]);

  // ── startRun ─────────────────────────────────────────────────────────────────

  const startRun = useCallback((input: StartRunInput): string => {
    const runId = _newRunId();
    const run: InternalRun = {
      runId,
      meta: input,
      status: 'queued',
      logs: [],
      sources: [],
      phase: null,
      doneData: null,
      startedAt: Date.now(),
      jobId: null,
      pollTimer: null,
      pollErrors: 0,
      stopped: false,
    };
    runsRef.current.set(runId, run);
    // View the freshly-started run.
    setViewedHistory(null);
    setViewedRunId(runId);

    const verdict = admit(run);
    if (verdict.start) {
      startJob(run); // sets status='running' + syncs
    } else {
      run.queuedReason = verdict.reason;
      syncActiveRuns();
    }
    return runId;
  }, [admit, startJob, syncActiveRuns]);

  // ── viewRun ──────────────────────────────────────────────────────────────────

  const viewRun = useCallback((runId: string) => {
    setViewedHistory(null);
    setViewedRunId(runId);
  }, []);

  // ── stop ─────────────────────────────────────────────────────────────────────

  const stop = useCallback((runId?: string) => {
    const id = runId ?? viewedRunId;
    if (!id) return;
    const r = runsRef.current.get(id);
    if (!r) return;
    r.stopped = true;
    stopPolling(r);
    // Server-side cancellation is cooperative (between progress events) and
    // fire-and-forget — the UI marks the run stopped immediately either way.
    if (r.jobId) void fetch(`/api/jobs/${r.jobId}/cancel`, { method: 'POST' }).catch(() => {});
    r.status = 'stopped';
    pushRun(r, 'stopped');
    syncActiveRuns();
    // Stopping a running run frees a slot — let a queued run take it.
    tryAdmitQueued();
  }, [viewedRunId, pushRun, stopPolling, syncActiveRuns, tryAdmitQueued]);

  // ── reset ─────────────────────────────────────────────────────────────────────
  // Clears the output view. If the viewed run has finished, drop it from the
  // active list (it lives on in history). Running runs are never killed by reset.

  const reset = useCallback(() => {
    if (viewedRunId) {
      const r = runsRef.current.get(viewedRunId);
      if (r && r.status !== 'running') {
        runsRef.current.delete(viewedRunId);
        syncActiveRuns();
      }
    }
    setViewedHistory(null);
    setViewedRunId(null);
  }, [viewedRunId, syncActiveRuns]);

  // ── abortAndLoad ──────────────────────────────────────────────────────────────
  // View a history record. Active runs keep streaming untouched (the whole point
  // of concurrent runs — opening history no longer kills a live run).

  const abortAndLoad = useCallback((record: RunRecord) => {
    setViewedHistory(record);
    setViewedRunId(null);
  }, []);

  // ── Derive the viewed-run flat fields ──────────────────────────────────────────

  const viewedActive = viewedRunId ? activeRuns.find(r => r.runId === viewedRunId) : undefined;

  let vStatus: Status = 'idle';
  let vLogs: LogEntry[] = [];
  let vSources: Source[] = [];
  let vPhase: string | null = null;
  let vDone: Record<string, unknown> | null = null;
  let vCurrentId: string | null = null;

  if (viewedHistory) {
    vStatus = viewedHistory.status === 'running' ? 'success' : (viewedHistory.status as Status);
    vLogs = viewedHistory.logs;
    vSources = viewedHistory.sources ?? [];
    vPhase = viewedHistory.currentPhase;
    vDone = viewedHistory.doneData ?? null;
    vCurrentId = viewedHistory.id;
  } else if (viewedActive) {
    vStatus = viewedActive.status;
    vLogs = viewedActive.logs;
    vSources = viewedActive.sources;
    vPhase = viewedActive.phase;
    vDone = viewedActive.doneData;
    vCurrentId = viewedActive.runId;
  }

  const anyRunning = activeRuns.some(r => r.status === 'running');

  // ── Sync to AppRunContext (aggregate: running if any run is running) ────────────

  const { setActivity } = useAppRun();

  useEffect(() => {
    const running = activeRuns.filter(r => r.status === 'running');
    if (running.length > 0) {
      const phase = running.length > 1 ? `${running.length} runs` : (running[0].phase ?? undefined);
      setActivity('studio', { label: 'Studio', phase, status: 'running' });
    } else if (activeRuns.length === 0) {
      setActivity('studio', null);
    } else {
      // All finished — reflect the most recent terminal status briefly.
      const last = activeRuns[activeRuns.length - 1];
      const st = last.status === 'running' ? 'success' : last.status;
      setActivity('studio', { label: 'Studio', status: st as 'success' | 'failure' | 'stopped' });
      const t = setTimeout(() => setActivity('studio', null), 3000);
      return () => clearTimeout(t);
    }
  }, [activeRuns, setActivity]);

  // ── Context value ─────────────────────────────────────────────────────────────

  return (
    <StudioRunContext.Provider value={{
      status: vStatus,
      logs: vLogs,
      sources: vSources,
      currentPhase: vPhase,
      doneData: vDone,
      gating,
      activeRuns,
      anyRunning,
      runs,
      currentRunId: vCurrentId,
      startRun, viewRun, stop, reset, abortAndLoad,
      setGating, setRuns,
    }}>
      {children}
    </StudioRunContext.Provider>
  );
}
