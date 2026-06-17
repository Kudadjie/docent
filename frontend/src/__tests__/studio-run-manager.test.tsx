import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { AppRunProvider } from '@/lib/app-run-context';
import { StudioRunProvider, useStudioRun } from '@/lib/studio-run-context';
import type { FormState } from '@/app/studio/_shared';

// ── Fake WebSocket so startRun can open "connections" without a server ──────────
class FakeWS {
  static instances: FakeWS[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 0;
  constructor(url: string) { this.url = url; FakeWS.instances.push(this); }
  send(_data: string) { /* no-op */ }
  close() { this.readyState = 3; this.onclose?.(); }
  // test helper
  emit(obj: unknown) { this.onmessage?.({ data: JSON.stringify(obj) }); }
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

describe('studio run-manager (concurrent runs)', () => {
  beforeEach(() => {
    FakeWS.instances = [];
    vi.stubGlobal('WebSocket', FakeWS as unknown as typeof WebSocket);
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('starting a second run does not cancel the first', () => {
    const { result } = renderHook(() => useStudioRun(), { wrapper });

    act(() => { result.current.startRun({ actionId: 'deep', form }); });
    act(() => { result.current.startRun({ actionId: 'lit', form }); });

    expect(result.current.activeRuns).toHaveLength(2);
    expect(result.current.activeRuns.every(r => r.status === 'running')).toBe(true);
    // Both sockets are still open — neither was closed by the other's start.
    expect(FakeWS.instances).toHaveLength(2);
    expect(FakeWS.instances.every(ws => ws.readyState !== 3)).toBe(true);
  });

  it('one run finishing leaves the sibling running', () => {
    const { result } = renderHook(() => useStudioRun(), { wrapper });

    act(() => { result.current.startRun({ actionId: 'deep', form }); });
    act(() => { result.current.startRun({ actionId: 'lit', form }); });

    // Finish the first run.
    act(() => { FakeWS.instances[0].emit({ type: 'done', status: 'success', raw: '{}' }); });

    const byId = Object.fromEntries(result.current.activeRuns.map(r => [r.actionId, r.status]));
    expect(byId.deep).toBe('success');
    expect(byId.lit).toBe('running');
    // The finished run is recorded in history.
    expect(result.current.runs.some(r => r.status === 'success')).toBe(true);
  });

  it('stop() targets the viewed run only', () => {
    const { result } = renderHook(() => useStudioRun(), { wrapper });

    let firstId = '';
    act(() => { firstId = result.current.startRun({ actionId: 'deep', form }); });
    act(() => { result.current.startRun({ actionId: 'lit', form }); });

    // View + stop the first run.
    act(() => { result.current.viewRun(firstId); });
    act(() => { result.current.stop(); });

    const byId = Object.fromEntries(result.current.activeRuns.map(r => [r.actionId, r.status]));
    expect(byId.deep).toBe('stopped');
    expect(byId.lit).toBe('running');
  });

  it('does NOT client-queue notebook-bound runs (NLM is serialized server-side)', () => {
    const { result } = renderHook(() => useStudioRun(), { wrapper });

    // Two notebook-bound runs (a to-notebook and a deep→notebook) start together:
    // their research runs concurrently; the server mutex serializes only the brief
    // NLM auth/push moments. Client-queueing the whole run would waste concurrency.
    act(() => { result.current.startRun({ actionId: 'notebook', form }); });
    act(() => { result.current.startRun({ actionId: 'deep', form: { ...form, dest: 'Notebook' } }); });

    expect(result.current.activeRuns.filter(r => r.status === 'running')).toHaveLength(2);
    expect(result.current.activeRuns.some(r => r.status === 'queued')).toBe(false);
    expect(FakeWS.instances).toHaveLength(2); // both opened sockets immediately
  });

  it('enforces the parallel cap from config', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ research: { max_parallel_studio_runs: 1 } }),
    }));
    const { result } = renderHook(() => useStudioRun(), { wrapper });
    // Let the cap-fetch effect settle (fetch → .json() → capRef).
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });

    act(() => { result.current.startRun({ actionId: 'deep', form }); });
    act(() => { result.current.startRun({ actionId: 'lit', form }); });

    expect(result.current.activeRuns.filter(r => r.status === 'running')).toHaveLength(1);
    expect(result.current.activeRuns.filter(r => r.status === 'queued')).toHaveLength(1);

    // Finishing the running one promotes the queued one.
    act(() => { FakeWS.instances[0].emit({ type: 'done', status: 'success', raw: '{}' }); });
    expect(result.current.activeRuns.filter(r => r.status === 'running')).toHaveLength(1);
  });
});
