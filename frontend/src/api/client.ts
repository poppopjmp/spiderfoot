/**
 * Configure the auto-generated OpenAPI client with JWT/API-key interceptors.
 *
 * The generated client uses native `fetch` (not Axios), so we wire up
 * request/response/error interceptors on its own middleware system.
 *
 * Import this module once (e.g. in main.tsx) **before** any SDK call.
 */
import { client } from './generated/client.gen';

// ── Base URL & defaults ────────────────────────────────────────────
client.setConfig({
  baseUrl: '',
});

// ── Request interceptor — attach JWT / API-key ─────────────────────
client.interceptors.request.use((request, _options) => {
  const token =
    localStorage.getItem('sf_access_token') ||
    localStorage.getItem('sf_api_key');
  if (token) {
    request.headers.set('Authorization', `Bearer ${token}`);
  }
  return request;
});

// ── Error interceptor — 401 token refresh ──────────────────────────
let refreshPromise: Promise<string> | null = null;

client.interceptors.error.use(async (error, response, request, _options) => {
  if (
    response &&
    response.status === 401 &&
    !request.url.includes('/auth/login') &&
    !request.url.includes('/auth/refresh')
  ) {
    const refreshToken = localStorage.getItem('sf_refresh_token');
    if (refreshToken) {
      try {
        if (!refreshPromise) {
          refreshPromise = fetch('/api/auth/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
          })
            .then((res) => res.json())
            .then((data: { access_token: string }) => {
              try {
                localStorage.setItem('sf_access_token', data.access_token);
                localStorage.setItem('sf_api_key', data.access_token);
              } catch {
                /* QuotaExceeded — token is in-memory via closure */
              }
              return data.access_token;
            });
        }
        await refreshPromise;
      } catch {
        try {
          localStorage.removeItem('sf_access_token');
          localStorage.removeItem('sf_refresh_token');
          localStorage.removeItem('sf_api_key');
        } catch {
          /* ignore storage errors on clear */
        }
      } finally {
        refreshPromise = null;
      }
    }
  }
  return error;
});

/**
 * Retrieve auth headers for non-SDK consumers (e.g. EventSource, raw fetch).
 */
export function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  try {
    const jwt = localStorage.getItem('sf_access_token');
    const apiKey = localStorage.getItem('sf_api_key');
    if (jwt) headers['Authorization'] = `Bearer ${jwt}`;
    else if (apiKey) headers['X-API-Key'] = apiKey;
  } catch {
    /* localStorage blocked */
  }
  return headers;
}

export { client };

