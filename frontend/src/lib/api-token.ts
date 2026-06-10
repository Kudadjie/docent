/**
 * Per-session API token plumbing.
 *
 * The backend issues a random token at startup (`GET /api/auth/token`) and
 * rejects any mutating `/api/*` request that doesn't echo it back in the
 * `X-Docent-Token` header. A cross-origin page (including one on a different
 * localhost port) can never read the GET response, so it can never forge the
 * header — this closes the gap the Origin check alone leaves open.
 *
 * Rather than threading a header through ~60 call sites, we patch
 * `window.fetch` once at module load: same-origin mutating requests to /api/
 * get the header injected transparently. The WebSocket path can't carry
 * headers, so `getApiToken()` is also exported for inclusion in the first
 * WS message (see studio-run-context.tsx).
 */

let tokenPromise: Promise<string | null> | null = null;

export function getApiToken(): Promise<string | null> {
  if (!tokenPromise) {
    tokenPromise = originalFetch('/api/auth/token')
      .then(r => (r.ok ? r.json() : null))
      .then(data => (data && typeof data.token === 'string' ? data.token : null))
      .catch(() => null);
  }
  return tokenPromise;
}

const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

const originalFetch: typeof fetch =
  typeof window !== 'undefined' ? window.fetch.bind(window) : fetch;

function isMutatingApiRequest(input: RequestInfo | URL, init?: RequestInit): boolean {
  const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase();
  if (!MUTATING.has(method)) return false;
  const url = input instanceof Request ? input.url : String(input);
  // Same-origin relative paths ("/api/...") and absolute same-origin URLs.
  if (url.startsWith('/api/')) return true;
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.origin === window.location.origin && parsed.pathname.startsWith('/api/');
  } catch {
    return false;
  }
}

if (typeof window !== 'undefined') {
  window.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    if (!isMutatingApiRequest(input, init)) return originalFetch(input, init);
    const token = await getApiToken();
    if (token === null) return originalFetch(input, init); // backend has no token set
    const headers = new Headers(
      init?.headers ?? (input instanceof Request ? input.headers : undefined),
    );
    headers.set('X-Docent-Token', token);
    return originalFetch(input, { ...init, headers });
  }) as typeof fetch;
}
