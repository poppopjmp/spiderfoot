import axios from 'axios';

const api = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
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
  const headers: Record<string, string> = {};
  try {
    const jwt = localStorage.getItem('sf_access_token');
    const apiKey = localStorage.getItem('sf_api_key');
    if (jwt) headers['Authorization'] = `Bearer ${jwt}`;
    else if (apiKey) headers['X-API-Key'] = apiKey;
  } catch { /* localStorage blocked */ }
  return headers;
}

// Response interceptor — handle 401 with token refresh
// Use a shared promise to deduplicate concurrent refresh attempts:
// the first 401 triggers a refresh; subsequent 401s await the same promise.
let refreshPromise: Promise<string> | null = null;

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const originalRequest = error.config;
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
}

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
    api.get<{ event_types: unknown[] }>('/api/event-types', { signal }).then((r) => r.data),

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

// ── Agents Service API ────────────────────────────────────
export const agentsApi = {
  status: (signal?: AbortSignal) =>
    api.get<{
      agents: Record<string, { agent_name: string; status: string; processed_total: number; errors_total: number; avg_processing_time_ms: number }>;
      total_agents: number;
    }>('/api/agents/status', { signal }).then((r) => r.data),

  process: (data: { events: Array<Record<string, unknown>>; agent_name?: string }, signal?: AbortSignal) =>
    api.post('/api/agents/process', data, { signal }).then((r) => r.data),

  analyze: (data: { filename: string; content: string; content_type?: string; target?: string; scan_id?: string }, signal?: AbortSignal) =>
    api.post('/api/agents/analyze', data, { signal }).then((r) => r.data),

  report: (data: { scan_id?: string; scan_ids?: string[]; target: string; scan_name?: string; findings?: Array<Record<string, unknown>>; correlations?: Array<Record<string, unknown>>; stats?: Record<string, unknown>; agent_results?: Array<Record<string, unknown>>; geo_data?: Record<string, unknown> }, signal?: AbortSignal) =>
    api.post('/api/agents/report', data, { signal }).then((r) => r.data),
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
  exportBundle: (scanId: string, eventTypes?: string[], signal?: AbortSignal) =>
    api.post('/api/stix/export', {
      scan_id: scanId,
      event_types: eventTypes ?? [],
    }, { signal }).then((r) => r.data),
};
