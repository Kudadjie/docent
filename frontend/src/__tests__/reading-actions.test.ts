import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch);
});

afterEach(() => {
  vi.restoreAllMocks();
});

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

async function postAction(action: string, id?: string, extra?: Record<string, unknown>) {
  return fetch('/api/actions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, id, ...extra }),
  });
}

describe('reading action requests', () => {
  it('sends edit action with id and fields', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true, stdout: '' }));
    await postAction('edit', 'smith-2024', { notes: 'updated' });

    expect(mockFetch).toHaveBeenCalledWith('/api/actions', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ action: 'edit', id: 'smith-2024', notes: 'updated' }),
    }));
  });

  it('sends done action with id', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true, stdout: '' }));
    await postAction('done', 'smith-2024');

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body).toEqual({ action: 'done', id: 'smith-2024' });
  });

  it('sends sync without id', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true, stdout: '3 added, 0 unchanged, 0 failed.' }));
    await postAction('sync');

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body).toEqual({ action: 'sync' });
    expect(body.id).toBeUndefined();
  });

  it('sends queue-clear with confirmed flag', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true, stdout: '' }));
    await postAction('queue-clear', undefined, { confirmed: true });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body).toEqual({ action: 'queue-clear', confirmed: true });
  });

  it('handles server error response', async () => {
    mockFetch.mockResolvedValue(jsonResponse(
      { ok: false, error: 'id required' },
      400,
    ));
    const res = await postAction('edit');
    const data = await res.json();

    expect(res.status).toBe(400);
    expect(data.error).toBe('id required');
  });

  it('handles network failure', async () => {
    mockFetch.mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(postAction('done', 'x')).rejects.toThrow('Failed to fetch');
  });
});

describe('queue data fetch', () => {
  it('fetches queue and returns entries with banner', async () => {
    const queueData = {
      entries: [{ id: 'test-1', title: 'Paper', status: 'queued', order: 1 }],
      banner: { queued: 1, reading: 0, done: 0 },
      last_updated: '2026-05-25T12:00:00',
      database_count: 5,
    };
    mockFetch.mockResolvedValue(jsonResponse(queueData));

    const res = await fetch('/api/queue');
    const data = await res.json();

    expect(data.entries).toHaveLength(1);
    expect(data.banner.queued).toBe(1);
    expect(data.database_count).toBe(5);
  });
});
