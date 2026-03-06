/**
 * SpiderFoot Frontend API Client
 *
 * Hand-written Axios-based helpers for the backend API.
 * Covers all major router endpoints for scans, config, data, workspaces,
 * reports, auth, schedules, STIX, ASM, monitoring and more.
 *
 * Generated OpenAPI SDK is available at `@/api` (sdk.gen.ts) but
 * this file remains the primary client used by all page components.
 *
 * Regenerate the SDK:  npm run generate:api
 */
import axios from 'axios';

const api = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  },
  timeout: 30_000,
});

// Request interceptor — attach JWT token if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sf_access_token') || localStorage.getItem('sf_api_key');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Retrieve auth headers for non-Axios consumers (e.g. EventSource).
 * Returns an object with Authorization and/or X-API-Key if set.
 */
export function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'X-Requested-With': 'XMLHttpRequest',
  };
  try {
    const jwt = localStorage.getItem('sf_access_token');
    const apiKey = localStorage.getItem('sf_api_key');
    if (jwt) headers['Authorization'] = `Bearer ${jwt}`;
    else if (apiKey) headers['X-API-Key'] = apiKey;
  } catch { /* localStorage blocked */ }
  return headers;
}

// Response interceptor — handle 401 with token refresh, 429 with retry-after
// Use a shared promise to deduplicate concurrent refresh attempts:
// the first 401 triggers a refresh; subsequent 401s await the same promise.
let refreshPromise: Promise<string> | null = null;

/** Maximum auto-retries for rate-limited (429) responses. */
const MAX_429_RETRIES = 2;

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const originalRequest = error.config;

    // ── 429 Retry-After handling ──
    if (
      error.response?.status === 429 &&
      (originalRequest._retryCount ?? 0) < MAX_429_RETRIES
    ) {
      originalRequest._retryCount = (originalRequest._retryCount ?? 0) + 1;
      const retryAfter = error.response.headers?.['retry-after'];
      // Respect Retry-After header (seconds), default 2s, cap at 30s
      const delaySec = retryAfter ? Math.min(Number(retryAfter) || 2, 30) : 2;
      await new Promise((r) => setTimeout(r, delaySec * 1000));
      return api(originalRequest);
    }

    // ── 401 Token refresh ──
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem('sf_refresh_token');
      if (refreshToken) {
        try {
          // If a refresh is already in-flight, wait for it instead of issuing another
          if (!refreshPromise) {
            refreshPromise = api
              .post('/api/auth/refresh', { refresh_token: refreshToken })
              .then((res) => {
                const newToken: string = res.data.access_token;
                try {
                  localStorage.setItem('sf_access_token', newToken);
                  localStorage.setItem('sf_api_key', newToken);
                } catch { /* QuotaExceeded — token is in-memory via closure */ }
                return newToken;
              });
          }
          const newToken = await refreshPromise;
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return api(originalRequest);
        } catch {
          try {
            localStorage.removeItem('sf_access_token');
            localStorage.removeItem('sf_refresh_token');
            localStorage.removeItem('sf_api_key');
          } catch { /* ignore storage errors on clear */ }
          // Redirect to login after refresh failure (avoid redirect loops)
          if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
            window.location.href = '/login';
          }
        } finally {
          refreshPromise = null;
        }
      }
    }
    return Promise.reject(error);
  },
);

export default api;

// ── Shared Types ──────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  has_next: boolean;
  has_previous: boolean;
}

// ── Scan Types & API ──────────────────────────────────────────
export interface Scan {
  scan_id: string;
  name: string;
  target: string;
  status: string;
  created: number;
  started: number;
  ended: number;
  // extended
  state_machine?: object;
  result_count?: number;
  profile?: string;
  engine?: string;
}

export interface ScanCreateRequest {
  name: string;
  target: string;
  modules?: string[];
  type_filter?: string[];
  engine?: string;
  profile?: string;
  stealth_level?: StealthLevelName;
}

/** Stealth level names accepted by the scan-creation endpoint. */
export type StealthLevelName = 'none' | 'low' | 'medium' | 'high' | 'maximum';

export interface ScanCreateResponse {
  id: string;
  name: string;
  target: string;
  status: string;
  message: string;
}

export interface EventSummaryDetail {
  key: string;
  description: string;
  last_in: number;
  total: number;
  unique_total: number;
}

export interface ScanEvent {
  generated: number;
  data: string;
  module: string;
  hash: string;
  type: string;
  source_event_hash: string;
  confidence: number;
  visibility: number;
  risk: number;
  false_positive?: boolean;
  source_data?: string;
}

export interface ScanCorrelation {
  id: string;
  title: string;
  rule_id: string;
  rule_risk: string;
  rule_name: string;
  rule_descr: string;
  rule_logic: string;
  event_count: number;
  scan_id?: string;
}

export interface ScanLogEntry {
  generated: number;
  component: string;
  type: string;
  message: string;
  rowid: number;
}

export const scanApi = {
  list: (params?: { page?: number; page_size?: number; sort_by?: string; sort_order?: string }, signal?: AbortSignal) =>
    api.get<PaginatedResponse<Scan>>('/api/scans', { params, signal }).then((r) => r.data),

  search: (params: {
    target?: string; status?: string; tag?: string;
    started_after?: string; started_before?: string;
    module?: string; sort_by?: string; sort_order?: string;
    limit?: number; offset?: number;
  }, signal?: AbortSignal) =>
    api.get<{ total: number; scans: Scan[]; facets: { status: Record<string, number> } }>(
      '/api/scans/search', { params, signal },
    ).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) => api.get<Scan>(`/api/scans/${id}`, { signal }).then((r) => r.data),

  create: (data: ScanCreateRequest, signal?: AbortSignal) =>
    api.post<ScanCreateResponse>('/api/scans', data, { signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) => api.delete(`/api/scans/${id}`, { signal }).then((r) => r.data),

  deleteFull: (id: string, signal?: AbortSignal) => api.delete(`/api/scans/${id}/full`, { signal }).then((r) => r.data),

  stop: (id: string, signal?: AbortSignal) =>
    api.post<{ message: string; status: string }>(`/api/scans/${id}/stop`, null, { signal }).then((r) => r.data),

  rerun: (id: string, signal?: AbortSignal) =>
    api.post<{ new_scan_id: string; message: string }>(`/api/scans/${id}/rerun`, null, { signal }).then((r) => r.data),

  clone: (id: string, signal?: AbortSignal) =>
    api.post<{ new_scan_id: string; message: string }>(`/api/scans/${id}/clone`, null, { signal }).then((r) => r.data),

  summary: (id: string, by: 'type' | 'module' | 'entity' = 'type', signal?: AbortSignal) =>
    api.get<{
      summary: Record<string, number>;
      details: EventSummaryDetail[];
      total_types: number;
    }>(`/api/scans/${id}/summary`, { params: { by }, signal }).then((r) => r.data),

  events: (id: string, params?: { event_type?: string; filter_fp?: boolean }, signal?: AbortSignal) =>
    api.get<{ events: ScanEvent[]; total: number }>(`/api/scans/${id}/events`, { params, signal }).then((r) => r.data),

  eventsUnique: (id: string, eventType?: string, signal?: AbortSignal) =>
    api.get<{ events: { data: string; type: string; count: number }[]; total: number }>(
      `/api/scans/${id}/events/unique`, { params: { event_type: eventType || 'ALL' }, signal },
    ).then((r) => r.data),

  correlations: (id: string, signal?: AbortSignal) =>
    api.get<{ correlations: ScanCorrelation[]; total: number }>(`/api/scans/${id}/correlations`, { signal }).then((r) => r.data),

  correlationsSummary: (id: string, by: 'risk' | 'rule' = 'risk', signal?: AbortSignal) =>
    api.get(`/api/scans/${id}/correlations/summary`, { params: { by }, signal }).then((r) => r.data),

  runCorrelations: (id: string, signal?: AbortSignal) =>
    api.post(`/api/scans/${id}/correlations/run`, null, { signal }).then((r) => r.data),

  logs: (id: string, params?: { limit?: number; offset?: number }, signal?: AbortSignal) =>
    api.get<{ logs: ScanLogEntry[]; total: number }>(`/api/scans/${id}/logs`, { params, signal }).then((r) => r.data),

  timeline: (id: string, limit = 200, signal?: AbortSignal) =>
    api.get(`/api/scans/${id}/timeline`, { params: { limit }, signal }).then((r) => r.data),

  options: (id: string, signal?: AbortSignal) =>
    api.get(`/api/scans/${id}/options`, { signal }).then((r) => r.data),

  exportEvents: (id: string, params?: { event_type?: string; filetype?: string }, signal?: AbortSignal) =>
    api.get(`/api/scans/${id}/events/export`, { params, responseType: 'blob' as const, signal }),

  exportLogs: (id: string, signal?: AbortSignal) =>
    api.get(`/api/scans/${id}/logs/export`, { responseType: 'blob' as const, signal }),

  viz: (id: string, gexf = false, signal?: AbortSignal) =>
    api.get(`/api/scans/${id}/viz`, { params: { gexf: gexf ? '1' : '0' }, signal }).then((r) => r.data),

  compare: (scanA: string, scanB: string, signal?: AbortSignal) =>
    api.get('/api/scans/compare', { params: { scan_a: scanA, scan_b: scanB }, signal }).then((r) => r.data),

  setFalsePositive: (id: string, resultIds: string[], fp: boolean, signal?: AbortSignal) =>
    api.post(`/api/scans/${id}/results/falsepositive`, { resultids: resultIds, fp: fp ? '1' : '0' }, { signal }).then((r) => r.data),

  tags: (id: string, signal?: AbortSignal) =>
    api.get<{ scan_id: string; tags: string[] }>(`/api/scans/${id}/tags`, { signal }).then((r) => r.data),

  setTags: (id: string, tags: string[], signal?: AbortSignal) =>
    api.put(`/api/scans/${id}/tags`, tags, { signal }).then((r) => r.data),

  metadata: (id: string, signal?: AbortSignal) =>
    api.get(`/api/scans/${id}/metadata`, { signal }).then((r) => r.data),

  notes: (id: string, signal?: AbortSignal) =>
    api.get<{ notes: string }>(`/api/scans/${id}/notes`, { signal }).then((r) => r.data),

  setNotes: (id: string, notes: string, signal?: AbortSignal) =>
    api.patch(`/api/scans/${id}/notes`, { notes }, { signal }).then((r) => r.data),

  archive: (id: string, signal?: AbortSignal) => api.post(`/api/scans/${id}/archive`, null, { signal }).then((r) => r.data),
  unarchive: (id: string, signal?: AbortSignal) => api.post(`/api/scans/${id}/unarchive`, null, { signal }).then((r) => r.data),

  bulkStop: (ids: string[], signal?: AbortSignal) =>
    api.post('/api/scans/bulk/stop', { scan_ids: ids }, { signal }).then((r) => r.data),
  bulkDelete: (ids: string[], signal?: AbortSignal) =>
    api.post('/api/scans/bulk/delete', { scan_ids: ids }, { signal }).then((r) => r.data),

  profiles: (signal?: AbortSignal) =>
    api.get<{ profiles: ScanProfile[]; total: number }>('/api/scan-profiles', { signal }).then((r) => r.data),

  profile: (name: string, signal?: AbortSignal) =>
    api.get<ScanProfile>(`/api/scan-profiles/${name}`, { signal }).then((r) => r.data),
};

export interface ScanProfile {
  name: string;
  display_name: string;
  description: string;
  category: string;
  module_count: number;
  modules: string[];
  tags: string[];
  max_threads: number;
  timeout_minutes: number;
}

// ── Module / Data API ─────────────────────────────────────────
export interface Module {
  name: string;
  descr?: string;
  description?: string;
  cats?: string[];
  category?: string;
  labels?: string[];
  flags?: string[];
  provides?: string[];
  consumes?: string[];
  group?: string[];
  opts?: Record<string, unknown>;
  optdescs?: Record<string, string>;
  meta?: Record<string, unknown>;
  modern?: boolean;
  enabled?: boolean;
}

export const dataApi = {
  modules: (params?: { page?: number; page_size?: number }, signal?: AbortSignal) =>
    api.get<PaginatedResponse<Module>>('/api/data/modules', { params, signal }).then((r) => r.data),

  module: (name: string, signal?: AbortSignal) =>
    api.get<{ module: Module }>(`/api/data/modules/${name}`, { signal }).then((r) => r.data),

  moduleOptions: (name: string, signal?: AbortSignal) =>
    api.get(`/api/data/modules/${name}/options`, { signal }).then((r) => r.data),

  moduleCategories: (signal?: AbortSignal) =>
    api.get<{ module_categories: string[] }>('/api/data/module-categories', { signal }).then((r) => r.data),

  moduleTypes: (signal?: AbortSignal) =>
    api.get<{ module_types: string[] }>('/api/data/module-types', { signal }).then((r) => r.data),

  entityTypes: (signal?: AbortSignal) =>
    api.get<{ entity_types: string[] }>('/api/data/entity-types', { signal }).then((r) => r.data),

  riskLevels: (signal?: AbortSignal) =>
    api.get<{ risk_levels: string[] }>('/api/data/risk-levels', { signal }).then((r) => r.data),

  sources: (signal?: AbortSignal) =>
    api.get('/api/data/sources', { signal }).then((r) => r.data),

  modulesStatus: (signal?: AbortSignal) =>
    api.get<{
      total: number; enabled: number; disabled: number;
      modules: { module: string; enabled: boolean }[];
    }>('/api/data/modules/status', { signal }).then((r) => r.data),

  moduleStats: (signal?: AbortSignal) =>
    api.get('/api/data/modules/stats', { signal }).then((r) => r.data),

  moduleDependencies: (signal?: AbortSignal) =>
    api.get('/api/data/modules/dependencies', { signal }).then((r) => r.data),

  enableModule: (name: string, signal?: AbortSignal) =>
    api.post(`/api/data/modules/${name}/enable`, null, { signal }).then((r) => r.data),

  disableModule: (name: string, signal?: AbortSignal) =>
    api.post(`/api/data/modules/${name}/disable`, null, { signal }).then((r) => r.data),

  validateModuleConfig: (name: string, config: Record<string, unknown>, signal?: AbortSignal) =>
    api.post(`/api/data/modules/${name}/validate-config`, config, { signal }).then((r) => r.data),

  globalOptions: (signal?: AbortSignal) =>
    api.get('/api/data/global-options', { signal }).then((r) => r.data),
};

// ── Config API ────────────────────────────────────────────────
export const configApi = {
  get: (signal?: AbortSignal) =>
    api.get<{ summary: object; config: Record<string, unknown>; version: string }>('/api/config', { signal }).then((r) => r.data),

  update: (options: Record<string, unknown>, signal?: AbortSignal) =>
    api.patch('/api/config', { options }, { signal }).then((r) => r.data),

  replace: (newConfig: Record<string, unknown>, signal?: AbortSignal) =>
    api.put('/api/config', newConfig, { signal }).then((r) => r.data),

  reload: (signal?: AbortSignal) => api.post('/api/config/reload', null, { signal }).then((r) => r.data),

  validate: (options: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/config/validate', { options }, { signal }).then((r) => r.data),

  validateAll: (signal?: AbortSignal) =>
    api.get('/api/config/validate', { signal }).then((r) => r.data),

  scanDefaults: (signal?: AbortSignal) =>
    api.get<{ scan_defaults: object }>('/api/config/scan-defaults', { signal }).then((r) => r.data),

  updateScanDefaults: (options: Record<string, unknown>, signal?: AbortSignal) =>
    api.patch('/api/config/scan-defaults', { options }, { signal }).then((r) => r.data),

  summary: (signal?: AbortSignal) =>
    api.get('/api/config/summary', { signal }).then((r) => r.data),

  exportConfig: (signal?: AbortSignal) =>
    api.get('/api/config/export', { signal }).then((r) => r.data),

  importConfig: (config: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/config/import', config, { signal }).then((r) => r.data),

  history: (params?: { limit?: number; section?: string }, signal?: AbortSignal) =>
    api.get('/api/config/history', { params, signal }).then((r) => r.data),

  diff: (signal?: AbortSignal) => api.get('/api/config/diff', { signal }).then((r) => r.data),

  modules: (signal?: AbortSignal) =>
    api.get<{ modules: Module[] }>('/api/modules', { signal }).then((r) => r.data),

  eventTypes: (signal?: AbortSignal) =>
    api.get<{ event_types: Array<{ name: string; description?: string }> }>('/api/event-types', { signal }).then((r) => r.data),

  moduleConfig: (name: string, signal?: AbortSignal) =>
    api.get<{ module: string; config: Record<string, unknown> }>(`/api/module-config/${name}`, { signal }).then((r) => r.data),

  updateModuleConfig: (name: string, config: Record<string, unknown>, signal?: AbortSignal) =>
    api.put(`/api/module-config/${name}`, config, { signal }).then((r) => r.data),

  updateModuleOptions: (name: string, options: Record<string, unknown>, signal?: AbortSignal) =>
    api.patch(`/api/modules/${name}/options`, { options }, { signal }).then((r) => r.data),

  credentials: (signal?: AbortSignal) => api.get('/api/config/credentials', { signal }).then((r) => r.data),
  createCredential: (data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/config/credentials', data, { signal }).then((r) => r.data),
  deleteCredential: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/config/credentials/${id}`, { signal }).then((r) => r.data),
};

// ── Workspace API ─────────────────────────────────────────────
export interface Workspace {
  workspace_id: string;
  name: string;
  description: string;
  created_time: number;
  modified_time?: number;
  target_count?: number;
  scan_count?: number;
  targets?: unknown[];
  scans?: unknown[];
  metadata?: Record<string, unknown>;
}

export interface WorkspaceTarget {
  target_id: string;
  value: string;
  type: string;
  added_time: number;
  metadata?: Record<string, unknown>;
}

export const workspaceApi = {
  list: (params?: { page?: number; page_size?: number }, signal?: AbortSignal) =>
    api.get<PaginatedResponse<Workspace>>('/api/workspaces', { params, signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get<Workspace>(`/api/workspaces/${id}`, { signal }).then((r) => r.data),

  create: (data: { name: string; description?: string }, signal?: AbortSignal) =>
    api.post('/api/workspaces', data, { signal }).then((r) => r.data),

  update: (id: string, params: { name?: string; description?: string }, signal?: AbortSignal) =>
    api.put(`/api/workspaces/${id}`, null, { params, signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/workspaces/${id}`, { signal }).then((r) => r.data),

  summary: (id: string, signal?: AbortSignal) =>
    api.get(`/api/workspaces/${id}/summary`, { signal }).then((r) => r.data),

  targets: (id: string, signal?: AbortSignal) =>
    api.get<PaginatedResponse<WorkspaceTarget>>(`/api/workspaces/${id}/targets`, { signal }).then((r) => r.data),

  addTarget: (id: string, data: { target: string; target_type: string }, signal?: AbortSignal) =>
    api.post(`/api/workspaces/${id}/targets`, data, { signal }).then((r) => r.data),

  deleteTarget: (id: string, targetId: string, signal?: AbortSignal) =>
    api.delete(`/api/workspaces/${id}/targets/${targetId}`, { signal }).then((r) => r.data),

  setActive: (id: string, signal?: AbortSignal) =>
    api.post(`/api/workspaces/${id}/set-active`, null, { signal }).then((r) => r.data),

  clone: (id: string, signal?: AbortSignal) =>
    api.post(`/api/workspaces/${id}/clone`, null, { signal }).then((r) => r.data),

  multiScan: (id: string, modules: string[], signal?: AbortSignal) =>
    api.post(`/api/workspaces/${id}/multi-scan`, { modules }, { signal }).then((r) => r.data),

  linkScan: (workspaceId: string, scanId: string, signal?: AbortSignal) =>
    api.post(`/api/workspaces/${workspaceId}/scans/${scanId}`, null, { signal }).then((r) => r.data),

  unlinkScan: (workspaceId: string, scanId: string, signal?: AbortSignal) =>
    api.delete(`/api/workspaces/${workspaceId}/scans/${scanId}`, { signal }).then((r) => r.data),

  scans: (id: string, signal?: AbortSignal) =>
    api.get<{ scans: Array<{ scan_id: string; name: string; target: string; status: string; created: number }> }>(`/api/workspaces/${id}`, { signal }).then((r) => r.data?.scans ?? []),
};

// ── Health API ────────────────────────────────────────────────
export interface HealthComponent {
  status: string;
  latency_ms?: number;
  [key: string]: unknown;
}

export interface HealthResponse {
  status: 'up' | 'degraded' | 'down';
  uptime_seconds: number;
  components: Record<string, HealthComponent>;
}

export const healthApi = {
  check: (signal?: AbortSignal) => api.get<HealthResponse>('/health', { validateStatus: () => true, signal }).then((r) => r.data),
  live: (signal?: AbortSignal) => api.get('/health/live', { signal }).then((r) => r.data),
  ready: (signal?: AbortSignal) => api.get('/health/ready', { validateStatus: () => true, signal }).then((r) => r.data),
  dashboard: (signal?: AbortSignal) => api.get('/health/dashboard', { validateStatus: () => true, signal }).then((r) => r.data),
  component: (name: string, signal?: AbortSignal) => api.get(`/health/${name}`, { validateStatus: () => true, signal }).then((r) => r.data),
  version: (signal?: AbortSignal) => api.get('/version', { signal }).then((r) => r.data),
};

// ── AI Config API ─────────────────────────────────────────
export const aiConfigApi = {
  recommend: (data: {
    target: string;
    target_type: string;
    objective?: string;
    stealth?: string;
    include_api_key_modules?: boolean;
    max_modules?: number;
    exclude_modules?: string[];
    prefer_modules?: string[];
    scope_limit?: string;
  }, signal?: AbortSignal) => api.post('/api/ai-config/recommend', data, { signal }).then((r) => r.data),

  getRecommendation: (id: string, signal?: AbortSignal) =>
    api.get(`/api/ai-config/recommend/${id}`, { signal }).then((r) => r.data),

  compare: (data: {
    target: string;
    target_type: string;
    objectives: string[];
    stealth?: string;
  }, signal?: AbortSignal) => api.post('/api/ai-config/compare', data, { signal }).then((r) => r.data),

  feedback: (data: {
    recommendation_id: string;
    rating: number;
    actual_duration_minutes?: number;
    actual_events?: number;
    notes?: string;
  }, signal?: AbortSignal) => api.post('/api/ai-config/feedback', data, { signal }).then((r) => r.data),

  presets: (signal?: AbortSignal) =>
    api.get<{ presets: Array<{ id: string; name: string; description: string; estimated_time: string; module_count: string; stealth: string }> }>('/api/ai-config/presets', { signal }).then((r) => r.data),

  targetTypes: (signal?: AbortSignal) =>
    api.get<{ target_types: Array<{ id: string; name: string; description: string }> }>('/api/ai-config/target-types', { signal }).then((r) => r.data),

  stealthLevels: (signal?: AbortSignal) =>
    api.get<{ stealth_levels: Array<{ id: string; name: string; description: string; timing: Record<string, number> }> }>('/api/ai-config/stealth-levels', { signal }).then((r) => r.data),

  modules: (params?: { category?: string; passive_only?: boolean; target_type?: string }, signal?: AbortSignal) =>
    api.get<{ modules: Array<Record<string, unknown>>; total: number }>('/api/ai-config/modules', { params, signal }).then((r) => r.data),
};

// ── Agents Service API ────────────────────────────────────────
// The agents run as a separate container (sf-agents:8100).
// Traefik routes /api/agents/* → agents service (strips /api/agents prefix).
// nginx.conf proxies /api/agents/* → ${SF_AGENTS_URL} for direct port-3000 access.
export interface AgentMetrics {
  name: string;
  processed_total: number;
  errors_total: number;
  avg_processing_time_ms: number;
  last_processed?: string | null;
}

export interface AgentStatusResponse {
  agents: Record<string, AgentMetrics>;
  total_agents: number;
}

export const agentApi = {
  /** Status and metrics for all loaded agents. */
  status: (signal?: AbortSignal) =>
    api.get<AgentStatusResponse>('/api/agents/status', { signal }).then((r) => r.data),

  /** Health check of the agents sub-service. */
  health: (signal?: AbortSignal) =>
    api.get<{ status: string; service: string; agents: number }>('/api/agents/health', { signal }).then((r) => r.data),

  /** Submit events for agent analysis. */
  process: (data: {
    events: Array<Record<string, unknown>>;
    scan_id?: string;
    agent_name?: string;
  }, signal?: AbortSignal) =>
    api.post<{ results: Array<Record<string, unknown>>; total: number }>('/api/agents/process', data, { signal }).then((r) => r.data),

  /** Generate an AI-powered scan report. */
  generateReport: (data: {
    scan_id: string;
    target: string;
    scan_name?: string;
    findings?: Array<Record<string, unknown>>;
    correlations?: Array<Record<string, unknown>>;
    stats?: Record<string, unknown>;
  }, signal?: AbortSignal) =>
    api.post('/api/agents/report', data, { signal }).then((r) => r.data),

  /** Analyze a document or text content. */
  analyzeDocument: (data: {
    content: string;
    filename?: string;
    content_type?: string;
    target?: string;
    scan_id?: string;
  }, signal?: AbortSignal) =>
    api.post('/api/agents/analyze', data, { signal }).then((r) => r.data),
};

// ── Agents Report API (used by ReportTab & WorkspaceReportCard) ──
export const agentsApi = {
  report: (data: { scan_id?: string; scan_ids?: string[]; target: string; scan_name?: string; findings?: Array<Record<string, unknown>>; correlations?: Array<Record<string, unknown>>; stats?: Record<string, unknown>; agent_results?: Array<Record<string, unknown>>; geo_data?: Record<string, unknown> }, signal?: AbortSignal) =>
    api.post('/api/agents/report', data, { signal }).then((r) => r.data),
};

// ── IaC Generation API ────────────────────────────────────────

export interface IaCRequest {
  provider?: 'aws' | 'azure' | 'gcp' | 'digitalocean' | 'vmware';
  include_terraform?: boolean;
  include_ansible?: boolean;
  include_docker?: boolean;
  include_packer?: boolean;
  validate?: boolean;
}

export interface IaCValidationResult {
  artifact_type: string;
  file_name: string;
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface IaCResponse {
  scan_id: string;
  provider: string;
  profile_summary: {
    ip_count: number;
    port_count: number;
    service_count: number;
    web_server: string | null;
    os_detected: string | null;
  };
  /** Map of category → list of file names */
  files: Record<string, string[]>;
  /** Map of category → map of filename → file content string */
  bundle: Record<string, Record<string, string>>;
  validation: IaCValidationResult[];
  all_valid: boolean;
  message?: string;
}

export interface IaCReviewIssue {
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  category: 'security' | 'best_practice' | 'hardening' | 'optimisation';
  file: string;
  description: string;
  fix: string;
}

export interface IaCReviewData {
  security_score: number;
  review_status: 'approved' | 'needs_changes' | 'rejected';
  summary: string;
  issues: IaCReviewIssue[];
  positive_findings: string[];
  compliance_notes: string;
  raw_response?: string;
}

export interface IaCReviewResponse {
  agent: string;
  result_type: string;
  data: IaCReviewData;
  confidence: number;
  processing_time_ms: number;
  error: string | null;
}

export const iacApi = {
  /** Generate IaC artifacts (Terraform, Ansible, Docker Compose, Packer) from a finished scan. */
  generate: (scanId: string, data: IaCRequest = {}, signal?: AbortSignal) =>
    api.post<IaCResponse>(`/api/scans/${scanId}/iac`, data, { signal }).then((r) => r.data),

  /** Ask the IaC Advisor agent to review a generated bundle for security / best-practice issues. */
  review: (data: {
    scan_id?: string;
    target?: string;
    provider?: string;
    bundle: IaCResponse['bundle'];
    files: IaCResponse['files'];
  }, signal?: AbortSignal) =>
    api.post<IaCReviewResponse>('/api/agents/iac/review', data, { signal }).then((r) => r.data),
};

// ── Helpers ───────────────────────────────────────────────────

/** Detect if a numeric timestamp is in seconds or milliseconds and normalise to ms. */
function normaliseEpoch(epoch: number): number {
  if (!epoch) return 0;
  // Values below 1e12 are in seconds (up to ~year 33658); above are milliseconds
  return epoch < 1e12 ? epoch * 1000 : epoch;
}

export function formatEpoch(epoch: number): string {
  if (!epoch) return '\u2014';
  return new Date(normaliseEpoch(epoch)).toLocaleString();
}

export function formatDuration(startEpoch: number, endEpoch: number): string {
  if (!startEpoch) return '\u2014';
  const startMs = normaliseEpoch(startEpoch);
  const endMs = endEpoch ? normaliseEpoch(endEpoch) : Date.now();
  const seconds = Math.floor((endMs - startMs) / 1000);
  if (seconds < 0) return '\u2014';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

export const SCAN_STATUSES = [
  'CREATED', 'STARTING', 'RUNNING', 'FINISHED', 'ABORTED', 'ERROR-FAILED', 'STOPPED', 'SKIPPED',
] as const;

export function statusColor(status: string): string {
  switch (status?.toUpperCase()) {
    case 'RUNNING': case 'STARTING': return 'status-text-running';
    case 'FINISHED': return 'status-text-finished';
    case 'ABORTED': case 'STOPPED': return 'status-text-aborted';
    case 'ERROR-FAILED': return 'status-text-failed';
    case 'SKIPPED': return 'status-text-skipped';
    default: return 'status-text-default';
  }
}

export function statusBadgeClass(status: string): string {
  switch (status?.toUpperCase()) {
    case 'RUNNING': case 'STARTING': return 'badge badge-running';
    case 'FINISHED': return 'badge badge-success';
    case 'ABORTED': case 'STOPPED': return 'badge badge-medium';
    case 'ERROR-FAILED': return 'badge badge-critical';
    case 'SKIPPED': return 'badge badge-skipped';
    default: return 'badge badge-info';
  }
}

/* ── Schedule API ──────────────────────────────────────────── */

export interface Schedule {
  id: string;
  name: string;
  target: string;
  engine: string | null;
  modules: string[] | null;
  interval_hours: number;
  enabled: boolean;
  description: string;
  tags: string[];
  notify_on_change: boolean;
  max_runs: number;
  runs_completed: number;
  last_run_at: number | null;
  next_run_at: number | null;
  created_at: number;
}

export interface ScheduleCreate {
  name: string;
  target: string;
  engine?: string;
  modules?: string[];
  interval_hours?: number;
  enabled?: boolean;
  description?: string;
  tags?: string[];
  notify_on_change?: boolean;
  max_runs?: number;
}

export const scheduleApi = {
  list: (signal?: AbortSignal) =>
    api.get<{ schedules: Schedule[]; total: number }>('/api/schedules', { signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get<Schedule>(`/api/schedules/${id}`, { signal }).then((r) => r.data),

  create: (data: ScheduleCreate, signal?: AbortSignal) =>
    api.post<Schedule>('/api/schedules', data, { signal }).then((r) => r.data),

  update: (id: string, data: Partial<ScheduleCreate>, signal?: AbortSignal) =>
    api.put<Schedule>(`/api/schedules/${id}`, data, { signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/schedules/${id}`, { signal }).then((r) => r.data),

  trigger: (id: string, signal?: AbortSignal) =>
    api.post<{ message: string; scan_id?: string }>(`/api/schedules/${id}/trigger`, null, { signal }).then((r) => r.data),
};

/* ── STIX Export API ───────────────────────────────────────── */

export const stixApi = {
  exportBundle: (scanId: string, _eventTypes?: string[], signal?: AbortSignal) =>
    api.get(`/api/scans/${scanId}/export/stix`, { signal }).then((r) => r.data),

  exportBundlePost: (data: { scan_id: string; event_types?: string[]; stix_version?: string }, signal?: AbortSignal) =>
    api.post('/api/stix/export', data, { signal }).then((r) => r.data),

  eventTypes: (signal?: AbortSignal) =>
    api.get<{ event_types: string[] }>('/api/stix/event-types', { signal }).then((r) => r.data),
};

/* ── Reports API ───────────────────────────────────────────── */

export interface Report {
  report_id: string;
  scan_id: string;
  format: string;
  status: string;
  created_at: number;
  completed_at?: number;
  download_url?: string;
}

export const reportApi = {
  generate: (data: { scan_id: string; format?: string; template_id?: string; include_raw?: boolean }, signal?: AbortSignal) =>
    api.post<{ report_id: string; status: string }>('/api/reports/generate', data, { signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get<Report>(`/api/reports/${id}`, { signal }).then((r) => r.data),

  status: (id: string, signal?: AbortSignal) =>
    api.get<{ status: string; progress?: number }>(`/api/reports/${id}/status`, { signal }).then((r) => r.data),

  preview: (id: string, signal?: AbortSignal) =>
    api.get(`/api/reports/${id}/preview`, { signal }).then((r) => r.data),

  exportReport: (id: string, format?: string, signal?: AbortSignal) =>
    api.get(`/api/reports/${id}/export`, { params: { format }, responseType: 'blob' as const, signal }),

  list: (params?: { page?: number; page_size?: number; scan_id?: string }, signal?: AbortSignal) =>
    api.get<PaginatedResponse<Report>>('/api/reports', { params, signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/reports/${id}`, { signal }).then((r) => r.data),

  pdf: (id: string, signal?: AbortSignal) =>
    api.get(`/api/reports/${id}/pdf`, { responseType: 'blob' as const, signal }),
};

/* ── Report Templates API ─────────────────────────────────── */

export const reportTemplateApi = {
  list: (params?: { page?: number; page_size?: number; category?: string }, signal?: AbortSignal) =>
    api.get('/api/report-templates', { params, signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get(`/api/report-templates/${id}`, { signal }).then((r) => r.data),

  create: (data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/report-templates', data, { signal }).then((r) => r.data),

  update: (id: string, data: Record<string, unknown>, signal?: AbortSignal) =>
    api.put(`/api/report-templates/${id}`, data, { signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/report-templates/${id}`, { signal }).then((r) => r.data),

  clone: (id: string, signal?: AbortSignal) =>
    api.post(`/api/report-templates/${id}/clone`, null, { signal }).then((r) => r.data),

  render: (id: string, data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post(`/api/report-templates/${id}/render`, data, { signal }).then((r) => r.data),

  variables: (signal?: AbortSignal) =>
    api.get('/api/report-templates/variables', { signal }).then((r) => r.data),

  categories: (signal?: AbortSignal) =>
    api.get('/api/report-templates/categories', { signal }).then((r) => r.data),

  formats: (signal?: AbortSignal) =>
    api.get('/api/report-templates/formats', { signal }).then((r) => r.data),
};

/* ── Audit API ─────────────────────────────────────────────── */

export interface AuditEntry {
  id: string;
  action: string;
  user: string;
  resource: string;
  resource_id?: string;
  timestamp: number;
  details?: Record<string, unknown>;
  ip_address?: string;
}

export const auditApi = {
  list: (params?: {
    page?: number; page_size?: number; action?: string;
    user?: string; resource?: string; start_date?: string; end_date?: string;
  }, signal?: AbortSignal) =>
    api.get<PaginatedResponse<AuditEntry>>('/api/audit', { params, signal }).then((r) => r.data),

  actions: (signal?: AbortSignal) =>
    api.get<{ actions: string[] }>('/api/audit/actions', { signal }).then((r) => r.data),

  stats: (signal?: AbortSignal) =>
    api.get('/api/audit/stats', { signal }).then((r) => r.data),
};

/* ── API Keys API ──────────────────────────────────────────── */

export interface ApiKey {
  key_id: string;
  name: string;
  prefix: string;
  created_at: number;
  expires_at?: number;
  last_used_at?: number;
  scopes?: string[];
  revoked: boolean;
}

export const keysApi = {
  list: (signal?: AbortSignal) =>
    api.get<{ keys: ApiKey[]; total: number }>('/api/keys', { signal }).then((r) => r.data),

  create: (data: { name: string; expires_days?: number; scopes?: string[] }, signal?: AbortSignal) =>
    api.post<{ key_id: string; key: string }>('/api/keys', data, { signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get<ApiKey>(`/api/keys/${id}`, { signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/keys/${id}`, { signal }).then((r) => r.data),

  revoke: (id: string, signal?: AbortSignal) =>
    api.post(`/api/keys/${id}/revoke`, null, { signal }).then((r) => r.data),
};

/* ── Tasks API ─────────────────────────────────────────────── */

export interface Task {
  task_id: string;
  name: string;
  status: string;
  progress?: number;
  created_at: number;
  started_at?: number;
  completed_at?: number;
  result?: unknown;
  error?: string;
}

export const tasksApi = {
  list: (params?: { status?: string; page?: number; page_size?: number }, signal?: AbortSignal) =>
    api.get<PaginatedResponse<Task>>('/api/tasks', { params, signal }).then((r) => r.data),

  active: (signal?: AbortSignal) =>
    api.get<{ tasks: Task[]; total: number }>('/api/tasks/active', { signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get<Task>(`/api/tasks/${id}`, { signal }).then((r) => r.data),

  submit: (data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/tasks', data, { signal }).then((r) => r.data),

  deleteCompleted: (signal?: AbortSignal) =>
    api.delete('/api/tasks/completed', { signal }).then((r) => r.data),

  cancel: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/tasks/${id}`, { signal }).then((r) => r.data),
};

/* ── Webhooks API ──────────────────────────────────────────── */

export interface Webhook {
  webhook_id: string;
  name: string;
  url: string;
  events: string[];
  enabled: boolean;
  created_at: number;
  last_triggered_at?: number;
  secret?: string;
}

export const webhookApi = {
  list: (signal?: AbortSignal) =>
    api.get<{ webhooks: Webhook[]; total: number }>('/api/webhooks', { signal }).then((r) => r.data),

  create: (data: { name: string; url: string; events: string[]; secret?: string }, signal?: AbortSignal) =>
    api.post<Webhook>('/api/webhooks', data, { signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get<Webhook>(`/api/webhooks/${id}`, { signal }).then((r) => r.data),

  update: (id: string, data: Partial<Webhook>, signal?: AbortSignal) =>
    api.put<Webhook>(`/api/webhooks/${id}`, data, { signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/webhooks/${id}`, { signal }).then((r) => r.data),

  stats: (signal?: AbortSignal) =>
    api.get('/api/webhooks/stats', { signal }).then((r) => r.data),

  eventTypes: (signal?: AbortSignal) =>
    api.get<{ event_types: string[] }>('/api/webhooks/event-types', { signal }).then((r) => r.data),

  test: (id: string, signal?: AbortSignal) =>
    api.post(`/api/webhooks/${id}/test`, null, { signal }).then((r) => r.data),

  history: (id: string, params?: { page?: number; page_size?: number }, signal?: AbortSignal) =>
    api.get(`/api/webhooks/${id}/history`, { params, signal }).then((r) => r.data),

  eventFilter: (id: string, signal?: AbortSignal) =>
    api.get(`/api/webhooks/${id}/event-filter`, { signal }).then((r) => r.data),
};

/* ── Tags & Groups API ─────────────────────────────────────── */

export interface Tag {
  tag_id: string;
  name: string;
  color?: string;
  parent_id?: string;
  created_at: number;
  item_count?: number;
}

export interface TagGroup {
  group_id: string;
  name: string;
  description?: string;
  tag_ids: string[];
  created_at: number;
}

export const tagApi = {
  list: (params?: { page?: number; page_size?: number }, signal?: AbortSignal) =>
    api.get<PaginatedResponse<Tag>>('/api/tags', { params, signal }).then((r) => r.data),

  tree: (signal?: AbortSignal) =>
    api.get('/api/tags/tree', { signal }).then((r) => r.data),

  create: (data: { name: string; color?: string; parent_id?: string }, signal?: AbortSignal) =>
    api.post<Tag>('/api/tags', data, { signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get<Tag>(`/api/tags/${id}`, { signal }).then((r) => r.data),

  update: (id: string, data: Partial<Tag>, signal?: AbortSignal) =>
    api.put<Tag>(`/api/tags/${id}`, data, { signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/tags/${id}`, { signal }).then((r) => r.data),

  stats: (signal?: AbortSignal) =>
    api.get('/api/tags/stats', { signal }).then((r) => r.data),

  colors: (signal?: AbortSignal) =>
    api.get<{ colors: string[] }>('/api/tags/colors', { signal }).then((r) => r.data),

  assign: (tagId: string, data: { resource_type: string; resource_id: string }, signal?: AbortSignal) =>
    api.post(`/api/tags/${tagId}/assign`, data, { signal }).then((r) => r.data),

  unassign: (tagId: string, data: { resource_type: string; resource_id: string }, signal?: AbortSignal) =>
    api.post(`/api/tags/${tagId}/unassign`, data, { signal }).then((r) => r.data),

  // Groups
  groups: (signal?: AbortSignal) =>
    api.get<{ groups: TagGroup[]; total: number }>('/api/groups', { signal }).then((r) => r.data),

  createGroup: (data: { name: string; description?: string; tag_ids?: string[] }, signal?: AbortSignal) =>
    api.post<TagGroup>('/api/groups', data, { signal }).then((r) => r.data),

  getGroup: (id: string, signal?: AbortSignal) =>
    api.get<TagGroup>(`/api/groups/${id}`, { signal }).then((r) => r.data),

  updateGroup: (id: string, data: Partial<TagGroup>, signal?: AbortSignal) =>
    api.put<TagGroup>(`/api/groups/${id}`, data, { signal }).then((r) => r.data),

  deleteGroup: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/groups/${id}`, { signal }).then((r) => r.data),
};

/* ── Monitor API ───────────────────────────────────────────── */

export interface MonitoredDomain {
  domain_id: string;
  domain: string;
  enabled: boolean;
  check_interval_hours: number;
  last_checked_at?: number;
  change_count: number;
  created_at: number;
}

export const monitorApi = {
  list: (params?: { page?: number; page_size?: number }, signal?: AbortSignal) =>
    api.get<PaginatedResponse<MonitoredDomain>>('/api/monitor/domains', { params, signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get<MonitoredDomain>(`/api/monitor/domains/${id}`, { signal }).then((r) => r.data),

  create: (data: { domain: string; check_interval_hours?: number }, signal?: AbortSignal) =>
    api.post<MonitoredDomain>('/api/monitor/domains', data, { signal }).then((r) => r.data),

  update: (id: string, data: Partial<MonitoredDomain>, signal?: AbortSignal) =>
    api.put<MonitoredDomain>(`/api/monitor/domains/${id}`, data, { signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/monitor/domains/${id}`, { signal }).then((r) => r.data),

  changes: (id: string, params?: { page?: number; page_size?: number }, signal?: AbortSignal) =>
    api.get(`/api/monitor/domains/${id}/changes`, { params, signal }).then((r) => r.data),

  check: (id: string, signal?: AbortSignal) =>
    api.post(`/api/monitor/domains/${id}/check`, null, { signal }).then((r) => r.data),
};

/* ── ASM (Attack Surface Management) API ───────────────────── */

export interface AsmAsset {
  asset_id: string;
  type: string;
  value: string;
  risk_level?: string;
  first_seen: number;
  last_seen: number;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

export const asmApi = {
  assets: (params?: {
    page?: number; page_size?: number; type?: string;
    risk_level?: string; search?: string;
  }, signal?: AbortSignal) =>
    api.get<PaginatedResponse<AsmAsset>>('/api/asm/assets', { params, signal }).then((r) => r.data),

  getAsset: (id: string, signal?: AbortSignal) =>
    api.get<AsmAsset>(`/api/asm/assets/${id}`, { signal }).then((r) => r.data),

  summary: (signal?: AbortSignal) =>
    api.get('/api/asm/summary', { signal }).then((r) => r.data),

  types: (signal?: AbortSignal) =>
    api.get<{ types: string[] }>('/api/asm/types', { signal }).then((r) => r.data),

  risks: (signal?: AbortSignal) =>
    api.get('/api/asm/risks', { signal }).then((r) => r.data),

  ingest: (data: { assets: Array<{ type: string; value: string; metadata?: Record<string, unknown> }> }, signal?: AbortSignal) =>
    api.post('/api/asm/assets/ingest', data, { signal }).then((r) => r.data),

  addTags: (assetId: string, tags: string[], signal?: AbortSignal) =>
    api.post(`/api/asm/assets/${assetId}/tags`, { tags }, { signal }).then((r) => r.data),

  link: (sourceId: string, targetId: string, signal?: AbortSignal) =>
    api.post(`/api/asm/assets/${sourceId}/link/${targetId}`, null, { signal }).then((r) => r.data),
};

/* ── Notification Rules API ────────────────────────────────── */

export const notificationApi = {
  list: (params?: { page?: number; page_size?: number }, signal?: AbortSignal) =>
    api.get('/api/notification-rules', { params, signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get(`/api/notification-rules/${id}`, { signal }).then((r) => r.data),

  create: (data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/notification-rules', data, { signal }).then((r) => r.data),

  update: (id: string, data: Record<string, unknown>, signal?: AbortSignal) =>
    api.put(`/api/notification-rules/${id}`, data, { signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/notification-rules/${id}`, { signal }).then((r) => r.data),

  evaluate: (id: string, signal?: AbortSignal) =>
    api.post(`/api/notification-rules/${id}/evaluate`, null, { signal }).then((r) => r.data),

  history: (id: string, params?: { page?: number; page_size?: number }, signal?: AbortSignal) =>
    api.get(`/api/notification-rules/${id}/history`, { params, signal }).then((r) => r.data),

  stats: (signal?: AbortSignal) =>
    api.get('/api/notification-rules/stats', { signal }).then((r) => r.data),

  operators: (signal?: AbortSignal) =>
    api.get('/api/notification-rules/operators', { signal }).then((r) => r.data),

  channels: (signal?: AbortSignal) =>
    api.get('/api/notification-rules/channels', { signal }).then((r) => r.data),
};

/* ── Data Retention API ────────────────────────────────────── */

export const retentionApi = {
  list: (signal?: AbortSignal) =>
    api.get('/api/retention/rules', { signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get(`/api/retention/rules/${id}`, { signal }).then((r) => r.data),

  create: (data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/retention/rules', data, { signal }).then((r) => r.data),

  update: (id: string, data: Record<string, unknown>, signal?: AbortSignal) =>
    api.put(`/api/retention/rules/${id}`, data, { signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/retention/rules/${id}`, { signal }).then((r) => r.data),

  preview: (id: string, signal?: AbortSignal) =>
    api.get(`/api/retention/rules/${id}/preview`, { signal }).then((r) => r.data),

  enforce: (id: string, signal?: AbortSignal) =>
    api.post(`/api/retention/rules/${id}/enforce`, null, { signal }).then((r) => r.data),

  history: (signal?: AbortSignal) =>
    api.get('/api/retention/history', { signal }).then((r) => r.data),

  stats: (signal?: AbortSignal) =>
    api.get('/api/retention/stats', { signal }).then((r) => r.data),
};

/* ── Scan Metrics API ──────────────────────────────────────── */

export const metricsApi = {
  prometheus: (signal?: AbortSignal) =>
    api.get('/metrics', { signal, responseType: 'text' as const }),

  dashboard: (signal?: AbortSignal) =>
    api.get('/api/scan-metrics', { signal }).then((r) => r.data),

  reset: (signal?: AbortSignal) =>
    api.post('/api/scan-metrics/reset', null, { signal }).then((r) => r.data),
};

/* ── Correlation Rules API ─────────────────────────────────── */

export const correlationRuleApi = {
  list: (params?: { page?: number; page_size?: number }, signal?: AbortSignal) =>
    api.get('/api/correlation-rules', { params, signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get(`/api/correlation-rules/${id}`, { signal }).then((r) => r.data),

  create: (data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/correlation-rules', data, { signal }).then((r) => r.data),

  update: (id: string, data: Record<string, unknown>, signal?: AbortSignal) =>
    api.put(`/api/correlation-rules/${id}`, data, { signal }).then((r) => r.data),

  delete: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/correlation-rules/${id}`, { signal }).then((r) => r.data),

  test: (data: { rule: Record<string, unknown>; scan_id: string }, signal?: AbortSignal) =>
    api.post('/api/correlation-rules/test', data, { signal }).then((r) => r.data),
};

/* ── Visualization API ─────────────────────────────────────── */

export const vizApi = {
  graph: (scanId: string, signal?: AbortSignal) =>
    api.get(`/api/visualization/graph/${scanId}`, { signal }).then((r) => r.data),

  graphMulti: (scanIds: string[], signal?: AbortSignal) =>
    api.post('/api/visualization/graph/multi', { scan_ids: scanIds }, { signal }).then((r) => r.data),

  summary: (scanId: string, signal?: AbortSignal) =>
    api.get(`/api/visualization/summary/${scanId}`, { signal }).then((r) => r.data),

  timeline: (scanId: string, signal?: AbortSignal) =>
    api.get(`/api/visualization/timeline/${scanId}`, { signal }).then((r) => r.data),

  heatmap: (scanId: string, signal?: AbortSignal) =>
    api.get(`/api/visualization/heatmap/${scanId}`, { signal }).then((r) => r.data),
};

/* ── Scan Comparison API ───────────────────────────────────── */

export const scanCompareApi = {
  compare: (scanA: string, scanB: string, signal?: AbortSignal) =>
    api.post('/api/scan-comparison/compare', { scan_a: scanA, scan_b: scanB }, { signal }).then((r) => r.data),

  quick: (scanA: string, scanB: string, signal?: AbortSignal) =>
    api.get('/api/scan-comparison/quick', { params: { scan_a: scanA, scan_b: scanB }, signal }).then((r) => r.data),

  history: (signal?: AbortSignal) =>
    api.get('/api/scan-comparison/history', { signal }).then((r) => r.data),

  get: (id: string, signal?: AbortSignal) =>
    api.get(`/api/scan-comparison/${id}`, { signal }).then((r) => r.data),

  categories: (signal?: AbortSignal) =>
    api.get('/api/scan-comparison/categories', { signal }).then((r) => r.data),

  severityLevels: (signal?: AbortSignal) =>
    api.get('/api/scan-comparison/severity-levels', { signal }).then((r) => r.data),
};

/* ── Auth / User Management API ────────────────────────────── */

export const authApi = {
  login: (data: { username: string; password: string }, signal?: AbortSignal) =>
    api.post('/api/auth/login', data, { signal }).then((r) => r.data),

  ldapLogin: (data: { username: string; password: string }, signal?: AbortSignal) =>
    api.post('/api/auth/ldap/login', data, { signal }).then((r) => r.data),

  refresh: (refreshToken: string, signal?: AbortSignal) =>
    api.post('/api/auth/refresh', { refresh_token: refreshToken }, { signal }).then((r) => r.data),

  logout: (signal?: AbortSignal) =>
    api.post('/api/auth/logout', null, { signal }).then((r) => r.data),

  me: (signal?: AbortSignal) =>
    api.get('/api/auth/me', { signal }).then((r) => r.data),

  status: (signal?: AbortSignal) =>
    api.get('/api/auth/status', { signal }).then((r) => r.data),

  // User management
  users: (signal?: AbortSignal) =>
    api.get('/api/auth/users', { signal }).then((r) => r.data),

  createUser: (data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/auth/users', data, { signal }).then((r) => r.data),

  updateUser: (id: string, data: Record<string, unknown>, signal?: AbortSignal) =>
    api.patch(`/api/auth/users/${id}`, data, { signal }).then((r) => r.data),

  deleteUser: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/auth/users/${id}`, { signal }).then((r) => r.data),

  setPassword: (id: string, data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post(`/api/auth/users/${id}/password`, data, { signal }).then((r) => r.data),

  // Auth API keys (different from /api/keys)
  authApiKeys: (signal?: AbortSignal) =>
    api.get('/api/auth/api-keys', { signal }).then((r) => r.data),

  authApiKeysMine: (signal?: AbortSignal) =>
    api.get('/api/auth/api-keys/mine', { signal }).then((r) => r.data),

  createAuthApiKey: (data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/auth/api-keys', data, { signal }).then((r) => r.data),

  revokeAuthApiKey: (id: string, signal?: AbortSignal) =>
    api.post(`/api/auth/api-keys/${id}/revoke`, null, { signal }).then((r) => r.data),

  deleteAuthApiKey: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/auth/api-keys/${id}`, { signal }).then((r) => r.data),

  // SSO providers
  ssoProviders: (signal?: AbortSignal) =>
    api.get('/api/auth/sso/providers/all', { signal }).then((r) => r.data),

  createSsoProvider: (data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/auth/sso/providers', data, { signal }).then((r) => r.data),

  updateSsoProvider: (id: string, data: Record<string, unknown>, signal?: AbortSignal) =>
    api.patch(`/api/auth/sso/providers/${id}`, data, { signal }).then((r) => r.data),

  deleteSsoProvider: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/auth/sso/providers/${id}`, { signal }).then((r) => r.data),
};

/* ── Distributed Scan API ──────────────────────────────────── */

export const distributedApi = {
  workers: (signal?: AbortSignal) =>
    api.get('/api/distributed/workers', { signal }).then((r) => r.data),

  worker: (id: string, signal?: AbortSignal) =>
    api.get(`/api/distributed/workers/${id}`, { signal }).then((r) => r.data),

  registerWorker: (data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post('/api/distributed/workers', data, { signal }).then((r) => r.data),

  removeWorker: (id: string, signal?: AbortSignal) =>
    api.delete(`/api/distributed/workers/${id}`, { signal }).then((r) => r.data),

  drainWorker: (id: string, signal?: AbortSignal) =>
    api.post(`/api/distributed/workers/${id}/drain`, null, { signal }).then((r) => r.data),

  heartbeat: (id: string, data: Record<string, unknown>, signal?: AbortSignal) =>
    api.post(`/api/distributed/workers/${id}/heartbeat`, data, { signal }).then((r) => r.data),

  scans: (signal?: AbortSignal) =>
    api.get('/api/distributed/scans', { signal }).then((r) => r.data),

  poolStats: (signal?: AbortSignal) =>
    api.get('/api/distributed/pool/stats', { signal }).then((r) => r.data),

  strategies: (signal?: AbortSignal) =>
    api.get('/api/distributed/strategies', { signal }).then((r) => r.data),
};

/* ── Marketplace API ───────────────────────────────────────── */

export const marketplaceApi = {
  plugins: (params?: { page?: number; page_size?: number; category?: string; search?: string }, signal?: AbortSignal) =>
    api.get('/api/marketplace/plugins', { params, signal }).then((r) => r.data),

  featured: (signal?: AbortSignal) =>
    api.get('/api/marketplace/plugins/featured', { signal }).then((r) => r.data),

  plugin: (id: string, signal?: AbortSignal) =>
    api.get(`/api/marketplace/plugins/${id}`, { signal }).then((r) => r.data),

  install: (id: string, signal?: AbortSignal) =>
    api.post(`/api/marketplace/plugins/${id}/install`, null, { signal }).then((r) => r.data),

  uninstall: (id: string, signal?: AbortSignal) =>
    api.post(`/api/marketplace/plugins/${id}/uninstall`, null, { signal }).then((r) => r.data),

  categories: (signal?: AbortSignal) =>
    api.get('/api/marketplace/categories', { signal }).then((r) => r.data),

  stats: (signal?: AbortSignal) =>
    api.get('/api/marketplace/stats', { signal }).then((r) => r.data),
};

/* ── Frontend Data API (aggregated dashboard endpoints) ────── */

export const frontendDataApi = {
  moduleHealth: (signal?: AbortSignal) =>
    api.get('/api/frontend-data/module-health', { signal }).then((r) => r.data),

  timeline: (signal?: AbortSignal) =>
    api.get('/api/frontend-data/timeline', { signal }).then((r) => r.data),

  resultsFilter: (params: Record<string, unknown>, signal?: AbortSignal) =>
    api.get('/api/frontend-data/results/filter', { params, signal }).then((r) => r.data),

  threatMap: (signal?: AbortSignal) =>
    api.get('/api/frontend-data/threat-map', { signal }).then((r) => r.data),

  scanDiff: (scanA: string, scanB: string, signal?: AbortSignal) =>
    api.get('/api/frontend-data/scan-diff', { params: { scan_a: scanA, scan_b: scanB }, signal }).then((r) => r.data),

  facets: (params?: Record<string, unknown>, signal?: AbortSignal) =>
    api.get('/api/frontend-data/facets', { params, signal }).then((r) => r.data),
};

/* ── Rate Limits API ───────────────────────────────────────── */

export const rateLimitApi = {
  list: (signal?: AbortSignal) =>
    api.get('/api/rate-limits', { signal }).then((r) => r.data),

  stats: (signal?: AbortSignal) =>
    api.get('/api/rate-limits/stats', { signal }).then((r) => r.data),

  tiers: (signal?: AbortSignal) =>
    api.get('/api/rate-limits/tiers', { signal }).then((r) => r.data),

  endpointOverrides: (signal?: AbortSignal) =>
    api.get('/api/rate-limits/endpoint-overrides', { signal }).then((r) => r.data),

  reset: (signal?: AbortSignal) =>
    api.post('/api/rate-limits/reset', null, { signal }).then((r) => r.data),
};
