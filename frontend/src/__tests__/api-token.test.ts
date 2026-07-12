import { describe, it, expect, afterEach, vi } from 'vitest';

// api-token.ts patches window.fetch at import time and captures the original
// fetch in a module closure, so each test stubs window.fetch FIRST, then
// re-imports a fresh module copy via vi.resetModules() + dynamic import.

function jsonResponse(body: unknown, ok = true): Response {
  return { ok, json: async () => body } as unknown as Response;
}

interface Recorded {
  url: string;
  init?: RequestInit;
}

async function loadPatched(opts?: { token?: string | null; tokenFails?: boolean }) {
  const token = opts?.token === undefined ? 'tok-123' : opts.token;
  const calls: Recorded[] = [];
  const base = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : String(input);
    calls.push({ url, init });
    if (url.includes('/api/auth/token')) {
      if (opts?.tokenFails) throw new Error('network down');
      return jsonResponse({ token });
    }
    return jsonResponse({ ok: true });
  });
  window.fetch = base as unknown as typeof fetch;
  vi.resetModules();
  const mod = await import('@/lib/api-token');
  return { base, calls, mod };
}

function sentHeader(rec: Recorded | undefined): string | null {
  if (!rec) return null;
  return new Headers(rec.init?.headers).get('X-Docent-Token');
}

describe('api-token fetch patch', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('leaves GET /api requests untouched (no token fetch, no header)', async () => {
    const { calls } = await loadPatched();
    await window.fetch('/api/queue');
    expect(calls.map(c => c.url)).toEqual(['/api/queue']);
    expect(sentHeader(calls[0])).toBeNull();
  });

  it('injects X-Docent-Token on mutating same-origin /api requests', async () => {
    const { calls } = await loadPatched({ token: 'tok-abc' });
    await window.fetch('/api/tools/invoke', { method: 'POST', body: '{}' });
    const invoke = calls.find(c => c.url === '/api/tools/invoke');
    expect(sentHeader(invoke)).toBe('tok-abc');
  });

  it('fetches the token once and reuses it across requests', async () => {
    const { calls } = await loadPatched();
    await window.fetch('/api/a', { method: 'POST' });
    await window.fetch('/api/b', { method: 'DELETE' });
    const tokenCalls = calls.filter(c => c.url.includes('/api/auth/token'));
    expect(tokenCalls).toHaveLength(1);
    expect(sentHeader(calls.find(c => c.url === '/api/b'))).toBe('tok-123');
  });

  it('does not attach the token to cross-origin /api URLs', async () => {
    const { calls } = await loadPatched();
    await window.fetch('http://evil.example.com/api/steal', { method: 'POST' });
    const evil = calls.find(c => c.url.includes('evil.example.com'));
    expect(sentHeader(evil)).toBeNull();
  });

  it('attaches the token to absolute same-origin /api URLs', async () => {
    const { calls } = await loadPatched();
    await window.fetch(`${window.location.origin}/api/config`, { method: 'PUT' });
    const cfg = calls.find(c => c.url.endsWith('/api/config'));
    expect(sentHeader(cfg)).toBe('tok-123');
  });

  it('proceeds without the header when the token endpoint fails', async () => {
    const { calls } = await loadPatched({ tokenFails: true });
    await window.fetch('/api/tools/invoke', { method: 'POST' });
    const invoke = calls.find(c => c.url === '/api/tools/invoke');
    expect(invoke).toBeDefined();
    expect(sentHeader(invoke)).toBeNull();
  });

  it('proceeds without the header when the backend has no token set', async () => {
    const { calls } = await loadPatched({ token: null });
    await window.fetch('/api/tools/invoke', { method: 'POST' });
    expect(sentHeader(calls.find(c => c.url === '/api/tools/invoke'))).toBeNull();
  });

  it('getApiToken resolves the token for the WebSocket first-message path', async () => {
    const { mod } = await loadPatched({ token: 'ws-token' });
    await expect(mod.getApiToken()).resolves.toBe('ws-token');
  });
});
