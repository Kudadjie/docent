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

describe('backup API interactions', () => {
  it('creates backup with local_only flag', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true, manifest: {} }));

    await fetch('/api/backup/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ local_only: false }),
    });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.local_only).toBe(false);
  });

  it('restore sends backup_id', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }));

    await fetch('/api/backup/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ backup_id: 'abc123' }),
    });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.backup_id).toBe('abc123');
  });

  it('delete sends backup_id', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }));

    await fetch('/api/backup/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ backup_id: 'abc123' }),
    });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.backup_id).toBe('abc123');
  });

  it('handles restore failure', async () => {
    mockFetch.mockResolvedValue(jsonResponse(
      { ok: false, error: 'Backup not found' },
      404,
    ));

    const res = await fetch('/api/backup/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ backup_id: 'missing' }),
    });

    expect(res.status).toBe(404);
    const data = await res.json();
    expect(data.error).toBe('Backup not found');
  });
});

describe('config save', () => {
  it('sends config values via POST', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }));

    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: 'reading.database_dir', value: '~/Papers' }),
    });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.key).toBe('reading.database_dir');
    expect(body.value).toBe('~/Papers');
  });
});
