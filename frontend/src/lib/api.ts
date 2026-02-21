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
                localStorage.setItem('sf_access_token', newToken);
                localStorage.setItem('sf_api_key', newToken);
                return newToken;
              });
          }
          const newToken = await refreshPromise;
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return api(originalRequest);
        } catch {
          localStorage.removeItem('sf_access_token');
          localStorage.removeItem('sf_refresh_token');
          localStorage.removeItem('sf_api_key');
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
  list: (params?: { page?: number; page_size?: number; sort_by?: string; sort_order?: string }) =>
    api.get<PaginatedResponse<Scan>>('/api/scans', { params }).then((r) => r.data),

  search: (params: {
    target?: string; status?: string; tag?: string;
    started_after?: string; started_before?: string;
    module?: string; sort_by?: string; sort_order?: string;
    limit?: number; offset?: number;
  }) =>
    api.get<{ total: number; scans: Scan[]; facets: { status: Record<string, number> } }>(
      '/api/scans/search', { params },
    ).then((r) => r.data),

  get: (id: string) => api.get<Scan>(`/api/scans/${id}`).then((r) => r.data),

  create: (data: ScanCreateRequest) =>
    api.post<ScanCreateResponse>('/api/scans', data).then((r) => r.data),

  delete: (id: string) => api.delete(`/api/scans/${id}`).then((r) => r.data),

  deleteFull: (id: string) => api.delete(`/api/scans/${id}/full`).then((r) => r.data),

  stop: (id: string) =>
    api.post<{ message: string; status: string }>(`/api/scans/${id}/stop`).then((r) => r.data),

  rerun: (id: string) =>
    api.post<{ new_scan_id: string; message: string }>(`/api/scans/${id}/rerun`).then((r) => r.data),

  clone: (id: string) =>
    api.post<{ new_scan_id: string; message: string }>(`/api/scans/${id}/clone`).then((r) => r.data),

  summary: (id: string, by: 'type' | 'module' | 'entity' = 'type') =>
    api.get<{
      summary: Record<string, number>;
      details: EventSummaryDetail[];
      total_types: number;
    }>(`/api/scans/${id}/summary`, { params: { by } }).then((r) => r.data),

  events: (id: string, params?: { event_type?: string; filter_fp?: boolean }) =>
    api.get<{ events: ScanEvent[]; total: number }>(`/api/scans/${id}/events`, { params }).then((r) => r.data),

  eventsUnique: (id: string, eventType?: string) =>
    api.get<{ events: { data: string; type: string; count: number }[]; total: number }>(
      `/api/scans/${id}/events/unique`, { params: { event_type: eventType || 'ALL' } },
    ).then((r) => r.data),

  correlations: (id: string) =>
    api.get<{ correlations: ScanCorrelation[]; total: number }>(`/api/scans/${id}/correlations`).then((r) => r.data),

  correlationsSummary: (id: string, by: 'risk' | 'rule' = 'risk') =>
    api.get(`/api/scans/${id}/correlations/summary`, { params: { by } }).then((r) => r.data),

  runCorrelations: (id: string) =>
    api.post(`/api/scans/${id}/correlations/run`).then((r) => r.data),

  logs: (id: string, params?: { limit?: number; offset?: number }) =>
    api.get<{ logs: ScanLogEntry[]; total: number }>(`/api/scans/${id}/logs`, { params }).then((r) => r.data),

  timeline: (id: string, limit = 200) =>
    api.get(`/api/scans/${id}/timeline`, { params: { limit } }).then((r) => r.data),

  options: (id: string) =>
    api.get(`/api/scans/${id}/options`).then((r) => r.data),

  exportEvents: (id: string, params?: { event_type?: string; filetype?: string }) =>
    api.get(`/api/scans/${id}/events/export`, { params, responseType: 'blob' as const }),

  exportLogs: (id: string) =>
    api.get(`/api/scans/${id}/logs/export`, { responseType: 'blob' as const }),

  viz: (id: string, gexf = false) =>
    api.get(`/api/scans/${id}/viz`, { params: { gexf: gexf ? '1' : '0' } }).then((r) => r.data),

  compare: (scanA: string, scanB: string) =>
    api.get('/api/scans/compare', { params: { scan_a: scanA, scan_b: scanB } }).then((r) => r.data),

  setFalsePositive: (id: string, resultIds: string[], fp: boolean) =>
    api.post(`/api/scans/${id}/results/falsepositive`, { resultids: resultIds, fp: fp ? '1' : '0' }).then((r) => r.data),

  tags: (id: string) =>
    api.get<{ scan_id: string; tags: string[] }>(`/api/scans/${id}/tags`).then((r) => r.data),

  setTags: (id: string, tags: string[]) =>
    api.put(`/api/scans/${id}/tags`, tags).then((r) => r.data),

  metadata: (id: string) =>
    api.get(`/api/scans/${id}/metadata`).then((r) => r.data),

  notes: (id: string) =>
    api.get<{ notes: string }>(`/api/scans/${id}/notes`).then((r) => r.data),

  setNotes: (id: string, notes: string) =>
    api.patch(`/api/scans/${id}/notes`, { notes }).then((r) => r.data),

  archive: (id: string) => api.post(`/api/scans/${id}/archive`).then((r) => r.data),
  unarchive: (id: string) => api.post(`/api/scans/${id}/unarchive`).then((r) => r.data),

  bulkStop: (ids: string[]) =>
    api.post('/api/scans/bulk/stop', { scan_ids: ids }).then((r) => r.data),
  bulkDelete: (ids: string[]) =>
    api.post('/api/scans/bulk/delete', { scan_ids: ids }).then((r) => r.data),

  profiles: () =>
    api.get<{ profiles: ScanProfile[]; total: number }>('/api/scan-profiles').then((r) => r.data),

  profile: (name: string) =>
    api.get<ScanProfile>(`/api/scan-profiles/${name}`).then((r) => r.data),
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
  modules: (params?: { page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Module>>('/api/data/modules', { params }).then((r) => r.data),

  module: (name: string) =>
    api.get<{ module: Module }>(`/api/data/modules/${name}`).then((r) => r.data),

  moduleOptions: (name: string) =>
    api.get(`/api/data/modules/${name}/options`).then((r) => r.data),

  moduleCategories: () =>
    api.get<{ module_categories: string[] }>('/api/data/module-categories').then((r) => r.data),

  moduleTypes: () =>
    api.get<{ module_types: string[] }>('/api/data/module-types').then((r) => r.data),

  entityTypes: () =>
    api.get<{ entity_types: string[] }>('/api/data/entity-types').then((r) => r.data),

  riskLevels: () =>
    api.get<{ risk_levels: string[] }>('/api/data/risk-levels').then((r) => r.data),

  sources: () =>
    api.get('/api/data/sources').then((r) => r.data),

  modulesStatus: () =>
    api.get<{
      total: number; enabled: number; disabled: number;
      modules: { module: string; enabled: boolean }[];
    }>('/api/data/modules/status').then((r) => r.data),

  moduleStats: () =>
    api.get('/api/data/modules/stats').then((r) => r.data),

  moduleDependencies: () =>
    api.get('/api/data/modules/dependencies').then((r) => r.data),

  enableModule: (name: string) =>
    api.post(`/api/data/modules/${name}/enable`).then((r) => r.data),

  disableModule: (name: string) =>
    api.post(`/api/data/modules/${name}/disable`).then((r) => r.data),

  validateModuleConfig: (name: string, config: Record<string, unknown>) =>
    api.post(`/api/data/modules/${name}/validate-config`, config).then((r) => r.data),

  globalOptions: () =>
    api.get('/api/data/global-options').then((r) => r.data),
};

// ── Config API ────────────────────────────────────────────────
export const configApi = {
  get: () =>
    api.get<{ summary: object; config: Record<string, unknown>; version: string }>('/api/config').then((r) => r.data),

  update: (options: Record<string, unknown>) =>
    api.patch('/api/config', { options }).then((r) => r.data),

  replace: (newConfig: Record<string, unknown>) =>
    api.put('/api/config', newConfig).then((r) => r.data),

  reload: () => api.post('/api/config/reload').then((r) => r.data),

  validate: (options: Record<string, unknown>) =>
    api.post('/api/config/validate', { options }).then((r) => r.data),

  validateAll: () =>
    api.get('/api/config/validate').then((r) => r.data),

  scanDefaults: () =>
    api.get<{ scan_defaults: object }>('/api/config/scan-defaults').then((r) => r.data),

  updateScanDefaults: (options: Record<string, unknown>) =>
    api.patch('/api/config/scan-defaults', { options }).then((r) => r.data),

  summary: () =>
    api.get('/api/config/summary').then((r) => r.data),

  exportConfig: () =>
    api.get('/api/config/export').then((r) => r.data),

  importConfig: (config: Record<string, unknown>) =>
    api.post('/api/config/import', config).then((r) => r.data),

  history: (params?: { limit?: number; section?: string }) =>
    api.get('/api/config/history', { params }).then((r) => r.data),

  diff: () => api.get('/api/config/diff').then((r) => r.data),

  modules: () =>
    api.get<{ modules: Module[] }>('/api/modules').then((r) => r.data),

  eventTypes: () =>
    api.get<{ event_types: unknown[] }>('/api/event-types').then((r) => r.data),

  moduleConfig: (name: string) =>
    api.get<{ module: string; config: Record<string, unknown> }>(`/api/module-config/${name}`).then((r) => r.data),

  updateModuleConfig: (name: string, config: Record<string, unknown>) =>
    api.put(`/api/module-config/${name}`, config).then((r) => r.data),

  updateModuleOptions: (name: string, options: Record<string, unknown>) =>
    api.patch(`/api/modules/${name}/options`, { options }).then((r) => r.data),

  credentials: () => api.get('/api/config/credentials').then((r) => r.data),
  createCredential: (data: Record<string, unknown>) =>
    api.post('/api/config/credentials', data).then((r) => r.data),
  deleteCredential: (id: string) =>
    api.delete(`/api/config/credentials/${id}`).then((r) => r.data),
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
  list: (params?: { page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Workspace>>('/api/workspaces', { params }).then((r) => r.data),

  get: (id: string) =>
    api.get<Workspace>(`/api/workspaces/${id}`).then((r) => r.data),

  create: (data: { name: string; description?: string }) =>
    api.post('/api/workspaces', data).then((r) => r.data),

  update: (id: string, params: { name?: string; description?: string }) =>
    api.put(`/api/workspaces/${id}`, null, { params }).then((r) => r.data),

  delete: (id: string) =>
    api.delete(`/api/workspaces/${id}`).then((r) => r.data),

  summary: (id: string) =>
    api.get(`/api/workspaces/${id}/summary`).then((r) => r.data),

  targets: (id: string) =>
    api.get<PaginatedResponse<WorkspaceTarget>>(`/api/workspaces/${id}/targets`).then((r) => r.data),

  addTarget: (id: string, data: { target: string; target_type: string }) =>
    api.post(`/api/workspaces/${id}/targets`, data).then((r) => r.data),

  deleteTarget: (id: string, targetId: string) =>
    api.delete(`/api/workspaces/${id}/targets/${targetId}`).then((r) => r.data),

  setActive: (id: string) =>
    api.post(`/api/workspaces/${id}/set-active`).then((r) => r.data),

  clone: (id: string) =>
    api.post(`/api/workspaces/${id}/clone`).then((r) => r.data),

  multiScan: (id: string, modules: string[]) =>
    api.post(`/api/workspaces/${id}/multi-scan`, { modules }).then((r) => r.data),

  linkScan: (workspaceId: string, scanId: string) =>
    api.post(`/api/workspaces/${workspaceId}/scans/${scanId}`).then((r) => r.data),

  unlinkScan: (workspaceId: string, scanId: string) =>
    api.delete(`/api/workspaces/${workspaceId}/scans/${scanId}`).then((r) => r.data),

  scans: (id: string) =>
    api.get<{ scans: Array<{ scan_id: string; name: string; target: string; status: string; created: number }> }>(`/api/workspaces/${id}`).then((r) => r.data?.scans ?? []),
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
  check: () => api.get<HealthResponse>('/health', { validateStatus: () => true }).then((r) => r.data),
  live: () => api.get('/health/live').then((r) => r.data),
  ready: () => api.get('/health/ready', { validateStatus: () => true }).then((r) => r.data),
  dashboard: () => api.get('/health/dashboard', { validateStatus: () => true }).then((r) => r.data),
  component: (name: string) => api.get(`/health/${name}`, { validateStatus: () => true }).then((r) => r.data),
  version: () => api.get('/version').then((r) => r.data),
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
  }) => api.post('/api/ai-config/recommend', data).then((r) => r.data),

  getRecommendation: (id: string) =>
    api.get(`/api/ai-config/recommend/${id}`).then((r) => r.data),

  compare: (data: {
    target: string;
    target_type: string;
    objectives: string[];
    stealth?: string;
  }) => api.post('/api/ai-config/compare', data).then((r) => r.data),

  feedback: (data: {
    recommendation_id: string;
    rating: number;
    actual_duration_minutes?: number;
    actual_events?: number;
    notes?: string;
  }) => api.post('/api/ai-config/feedback', data).then((r) => r.data),

  presets: () =>
    api.get<{ presets: Array<{ id: string; name: string; description: string; estimated_time: string; module_count: string; stealth: string }> }>('/api/ai-config/presets').then((r) => r.data),

  targetTypes: () =>
    api.get<{ target_types: Array<{ id: string; name: string; description: string }> }>('/api/ai-config/target-types').then((r) => r.data),

  stealthLevels: () =>
    api.get<{ stealth_levels: Array<{ id: string; name: string; description: string; timing: Record<string, number> }> }>('/api/ai-config/stealth-levels').then((r) => r.data),

  modules: (params?: { category?: string; passive_only?: boolean; target_type?: string }) =>
    api.get<{ modules: Array<Record<string, unknown>>; total: number }>('/api/ai-config/modules', { params }).then((r) => r.data),
};

// ── Agents Service API ────────────────────────────────────
export const agentsApi = {
  status: () =>
    api.get<{
      agents: Record<string, { agent_name: string; status: string; processed_total: number; errors_total: number; avg_processing_time_ms: number }>;
      total_agents: number;
    }>('/api/agents/status').then((r) => r.data),

  process: (data: { events: Array<Record<string, unknown>>; agent_name?: string }) =>
    api.post('/api/agents/process', data).then((r) => r.data),

  analyze: (data: { filename: string; content: string; content_type?: string; target?: string; scan_id?: string }) =>
    api.post('/api/agents/analyze', data).then((r) => r.data),

  report: (data: { scan_id?: string; scan_ids?: string[]; target: string; scan_name?: string; findings?: Array<Record<string, unknown>>; correlations?: Array<Record<string, unknown>>; stats?: Record<string, unknown>; agent_results?: Array<Record<string, unknown>>; geo_data?: Record<string, unknown> }) =>
    api.post('/api/agents/report', data).then((r) => r.data),
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
