import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { AppRunProvider } from '@/lib/app-run-context';
import { StudioRunProvider, useStudioRun } from '@/lib/studio-run-context';
import type { FormState } from '@/app/studio/_shared';

// ── Fake backend: submit → job id, poll → mutable job snapshots ────────────────
//
// Runs are submitted via POST /api/studio/submit and polled via
// GET /api/jobs/{id} (the jobs transport that replaced the WS path in v2.3).
// Tests drive a run's lifecycle by mutating `jobs[id]` and advancing the fake
// 2s poll clock.

interface FakeJob {
  state: string;
  events: { ts: string; phase: string; message: string; level: string }[];
  result_json?: string;
  error?: string;
}

let jobs: Record<string, FakeJob>;
let submitted: { url: string; body: Record<string, unknown> }[];
let cancelled: string[];
let jobSeq = 0;
let maxParallel = 3;

function installFakeBackend() {
  jobs = {};
  submitted = [];
  cancelled = [];
  jobSeq = 0;
  const json = (body: unknown, ok = true) =>
    ({ ok, status: ok ? 200 : 400, json: async () => body }) as unknown as Response;

  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/api/config')) {
      return json({ research: { max_parallel_studio_runs: maxParallel } });
    }
    if (url.endsWith('/api/studio/submit')) {
      jobSeq += 1;
      const id = `job-${jobSeq}`;
      jobs[id] = { state: 'running', events: [] };
      submitted.push({ url, body: JSON.parse(String(init?.body ?? '{}')) });
      return json({ ok: true, job_id: id, state: 'queued' });
    }
    const cancel = url.match(/\/api\/jobs\/(job-\d+)\/cancel$/);
    if (cancel) {
      cancelled.push(cancel[1]);
      const j = jobs[cancel[1]];
      if (j) j.state = 'cancelled';
      return json({ state: 'cancelled' });
    }
    const poll = url.match(/\/api\/jobs\/(job-\d+)$/);
    if (poll) {
      const j = jobs[poll[1]];
      return j ? json(j) : json({ error: 'not found' }, false);
    }
    return json({});
  }));
}

const form: FormState = {
  topic: 'x', backend: 'Free', dest: 'Local', guides: [],
  artifact: '', artifactA: '', artifactB: '',
  query: '', maxResults: 10, arxivId: '',
  outPath: '', srcPath: '', maxSources: 20,
  nlm: true, gate: true, persp: true, cfgKey: '', cfgVal: '',
  citeIdentifier: '', citeDirection: 'cited-by', citeMax: 25, expandCitations: false,
};

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AppRunProvider><StudioRunProvider>{children}</StudioRunProvider></AppRunProvider>
);

/** Flush the submit fetch promise chain (start → job id → poll timer armed). */
async function flushSubmits() {
  await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
}

/** Advance past one poll tick and flush its fetch promise chain. */
async function pollOnce() {
  await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
}

describe('studio run-manager (jobs polling)', () => {
  beforeEach(() => {
    maxParallel = 3;
    installFakeBackend();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('starting a second run does not cancel the first', async () => {
    const { result } = renderHook(() => useStudioRun(), { wrapper });

    act(() => { result.current.startRun({ actionId: 'deep', form }); });
    act(() => { result.current.startRun({ actionId: 'lit', form }); });
    await flushSubmits();

    expect(result.current.activeRuns).toHaveLength(2);
    expect(result.current.activeRuns.every(r => r.status === 'running')).toBe(true);
    // Both runs were submitted as separate backend jobs; nothing was cancelled.
    expect(submitted).toHaveLength(2);
    expect(cancelled).toHaveLength(0);
  });

  it('submit body carries the action and form fields', async () => {
    const { result } = renderHook(() => useStudioRun(), { wrapper });
    act(() => { result.current.startRun({ actionId: 'deep', form: { ...form, topic: 'waves' } }); });
    await flushSubmits();

    expect(submitted).toHaveLength(1);
    expect(submitted[0].body.action_id).toBe('deep');
    expect(submitted[0].body.topic).toBe('waves');
    expect(submitted[0].body.backend).toBe('free');
    // No token field — the api-token fetch patch injects the header instead.
    expect('token' in submitted[0].body).toBe(false);
  });

  it('one run finishing leaves the sibling running', async () => {
    const { result } = renderHook(() => useStudioRun(), { wrapper });

    act(() => { result.current.startRun({ actionId: 'deep', form }); });
    act(() => { result.current.startRun({ actionId: 'lit', form }); });
    await flushSubmits();

    // Finish the first job server-side; next poll picks it up.
    jobs['job-1'] = { state: 'done', events: [], result_json: '{"ok": true, "output_file": "r.md"}' };
    await pollOnce();

    const byId = Object.fromEntries(result.current.activeRuns.map(r => [r.actionId, r.status]));
    expect(byId.deep).toBe('success');
    expect(byId.lit).toBe('running');
    // The finished run is recorded in history with the parsed result envelope.
    const rec = result.current.runs.find(r => r.status === 'success');
    expect(rec).toBeDefined();
    expect(rec?.doneData?.output_file).toBe('r.md');
    expect((rec?.doneData?.data as Record<string, unknown>)?.ok).toBe(true);
  });

  it('progress events become log lines with the latest phase', async () => {
    const { result } = renderHook(() => useStudioRun(), { wrapper });
    act(() => { result.current.startRun({ actionId: 'deep', form }); });
    await flushSubmits();

    jobs['job-1'].events = [
      { ts: 't', phase: 'search', message: 'querying', level: 'info' },
      { ts: 't', phase: 'synthesis', message: 'writing', level: 'info' },
    ];
    await pollOnce();

    const run = result.current.activeRuns[0];
    expect(run.logs.map(l => l.text)).toEqual(['querying', 'writing']);
    expect(run.phase).toBe('synthesis');
  });

  it('a failed job marks the run failure with the error in the log', async () => {
    const { result } = renderHook(() => useStudioRun(), { wrapper });
    act(() => { result.current.startRun({ actionId: 'deep', form }); });
    await flushSubmits();

    jobs['job-1'] = { state: 'failed', events: [], error: 'RuntimeError: boom' };
    await pollOnce();

    expect(result.current.activeRuns[0].status).toBe('failure');
    expect(result.current.activeRuns[0].logs.some(l => l.text.includes('boom'))).toBe(true);
  });

  it('stop() targets the viewed run only and cancels its backend job', async () => {
    const { result } = renderHook(() => useStudioRun(), { wrapper });

    let firstId = '';
    act(() => { firstId = result.current.startRun({ actionId: 'deep', form }); });
    act(() => { result.current.startRun({ actionId: 'lit', form }); });
    await flushSubmits();

    act(() => { result.current.viewRun(firstId); });
    act(() => { result.current.stop(); });
    await flushSubmits();

    const byId = Object.fromEntries(result.current.activeRuns.map(r => [r.actionId, r.status]));
    expect(byId.deep).toBe('stopped');
    expect(byId.lit).toBe('running');
    expect(cancelled).toEqual(['job-1']);
  });

  it('does NOT client-queue notebook-bound runs (NLM is serialized server-side)', async () => {
    const { result } = renderHook(() => useStudioRun(), { wrapper });

    act(() => { result.current.startRun({ actionId: 'notebook', form }); });
    act(() => { result.current.startRun({ actionId: 'deep', form: { ...form, dest: 'Notebook' } }); });
    await flushSubmits();

    expect(result.current.activeRuns.filter(r => r.status === 'running')).toHaveLength(2);
    expect(result.current.activeRuns.some(r => r.status === 'queued')).toBe(false);
    expect(submitted).toHaveLength(2); // both submitted immediately
  });

  it('enforces the parallel cap from config', async () => {
    maxParallel = 1;
    const { result } = renderHook(() => useStudioRun(), { wrapper });
    // Let the cap-fetch effect settle (fetch → .json() → capRef).
    await flushSubmits();

    act(() => { result.current.startRun({ actionId: 'deep', form }); });
    act(() => { result.current.startRun({ actionId: 'lit', form }); });
    await flushSubmits();

    expect(result.current.activeRuns.filter(r => r.status === 'running')).toHaveLength(1);
    expect(result.current.activeRuns.filter(r => r.status === 'queued')).toHaveLength(1);

    // Finishing the running one promotes the queued one.
    jobs['job-1'] = { state: 'done', events: [], result_json: '{"ok": true}' };
    await pollOnce();
    await flushSubmits();
    expect(result.current.activeRuns.filter(r => r.status === 'running')).toHaveLength(1);
  });
});
