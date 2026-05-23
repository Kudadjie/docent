/**
 * Extract a human-readable message from a string that may contain raw JSON.
 * Backend error bodies sometimes serialize as JSON objects; this pulls out
 * the first meaningful text field so users never see `{"error": "..."}` in toasts.
 */
export function extractMessage(raw: string): string {
  const trimmed = (raw ?? '').trim();
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return trimmed;
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
      const obj = parsed as Record<string, unknown>;
      for (const key of ['message', 'detail', 'error', 'msg', 'text', 'description', 'reason', 'stderr', 'stdout']) {
        const val = obj[key];
        if (typeof val === 'string' && val.trim()) {
          return val.trim().split('\n').find(l => l.trim()) ?? val.trim().slice(0, 160);
        }
      }
    }
    return 'An unexpected response was received.';
  } catch {
    return trimmed;
  }
}
