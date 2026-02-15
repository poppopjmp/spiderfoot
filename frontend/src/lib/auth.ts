/**
 * SpiderFoot Auth Store — Zustand-based authentication state management.
 *
 * Manages JWT tokens, user profile, login/logout, SSO providers,
 * and token refresh lifecycle.
 */
import { create } from 'zustand';
import api from './api';

// ── Types ────────────────────────────────────────────────

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  role: string;
  display_name: string;
  auth_method: string;
  status: string;
  created_at: number;
  last_login: number;
  sso_provider_id: string;
}

export interface SSOProvider {
  id: string;
  name: string;
  protocol: string;  // oauth2 | saml | ldap
  enabled: boolean;
  default_role: string;
}

export interface AuthStatus {
  auth_required: boolean;
  rbac_enforced: boolean;
  user_count: number;
  sso_providers: SSOProvider[];
  supported_methods: string[];
}

interface AuthState {
  // State
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  authRequired: boolean;
  ssoProviders: SSOProvider[];
  error: string | null;

  // Actions
  login: (username: string, password: string) => Promise<void>;
  ldapLogin: (providerId: string, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<boolean>;
  fetchCurrentUser: () => Promise<void>;
  fetchAuthStatus: () => Promise<void>;
  setTokensFromUrl: () => void;
  clearError: () => void;
  hasPermission: (permission: string) => boolean;
}

// ── Permission table (mirrors backend RBAC) ──────────────

const ROLE_PERMISSIONS: Record<string, Set<string>> = {
  viewer: new Set([
    'scan:read', 'report:read', 'data:read', 'engine:read',
    'schedule:read', 'system:health', 'notification:read',
  ]),
  analyst: new Set([
    'scan:read', 'report:read', 'data:read', 'engine:read',
    'schedule:read', 'system:health', 'notification:read',
    'scan:create', 'scan:update', 'scan:abort', 'report:create',
    'data:export', 'schedule:create', 'schedule:update',
    'schedule:trigger', 'config:read', 'ratelimit:read',
  ]),
  operator: new Set([
    'scan:read', 'report:read', 'data:read', 'engine:read',
    'schedule:read', 'system:health', 'notification:read',
    'scan:create', 'scan:update', 'scan:abort', 'report:create',
    'data:export', 'schedule:create', 'schedule:update',
    'schedule:trigger', 'config:read', 'ratelimit:read',
    'scan:delete', 'engine:create', 'engine:update', 'engine:delete',
    'schedule:delete', 'notification:write',
  ]),
  admin: new Set([
    'scan:read', 'report:read', 'data:read', 'engine:read',
    'schedule:read', 'system:health', 'notification:read',
    'scan:create', 'scan:update', 'scan:abort', 'report:create',
    'data:export', 'schedule:create', 'schedule:update',
    'schedule:trigger', 'config:read', 'ratelimit:read',
    'scan:delete', 'engine:create', 'engine:update', 'engine:delete',
    'schedule:delete', 'notification:write',
    'config:write', 'ratelimit:write', 'user:read', 'user:create',
    'user:update', 'user:delete', 'system:admin',
  ]),
};


// ── Token helpers ────────────────────────────────────────

function saveTokens(access: string, refresh: string) {
  localStorage.setItem('sf_access_token', access);
  localStorage.setItem('sf_refresh_token', refresh);
  // Also set legacy key for backward compat
  localStorage.setItem('sf_api_key', access);
}

function clearTokens() {
  localStorage.removeItem('sf_access_token');
  localStorage.removeItem('sf_refresh_token');
  localStorage.removeItem('sf_api_key');
}

function loadTokens(): { access: string | null; refresh: string | null } {
  return {
    access: localStorage.getItem('sf_access_token') || localStorage.getItem('sf_api_key'),
    refresh: localStorage.getItem('sf_refresh_token'),
  };
}


// ── Store ────────────────────────────────────────────────

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: loadTokens().access,
  refreshToken: loadTokens().refresh,
  isAuthenticated: !!loadTokens().access,
  isLoading: true,
  authRequired: false,
  ssoProviders: [],
  error: null,

  login: async (username: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await api.post('/api/auth/login', { username, password });
      const { access_token, refresh_token, user } = res.data;
      saveTokens(access_token, refresh_token);
      set({
        user,
        accessToken: access_token,
        refreshToken: refresh_token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Login failed';
      set({ isLoading: false, error: msg });
      throw new Error(msg);
    }
  },

  ldapLogin: async (providerId: string, username: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await api.post('/api/auth/ldap/login', {
        provider_id: providerId,
        username,
        password,
      });
      const { access_token, refresh_token, user } = res.data;
      saveTokens(access_token, refresh_token);
      set({
        user,
        accessToken: access_token,
        refreshToken: refresh_token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'LDAP login failed';
      set({ isLoading: false, error: msg });
      throw new Error(msg);
    }
  },

  logout: async () => {
    try {
      await api.post('/api/auth/logout');
    } catch {
      // Ignore — we clear local state regardless
    }
    clearTokens();
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      error: null,
    });
  },

  refreshAccessToken: async () => {
    const { refreshToken } = get();
    if (!refreshToken) return false;
    try {
      const res = await api.post('/api/auth/refresh', {
        refresh_token: refreshToken,
      });
      const { access_token } = res.data;
      localStorage.setItem('sf_access_token', access_token);
      localStorage.setItem('sf_api_key', access_token);
      set({ accessToken: access_token, isAuthenticated: true });
      return true;
    } catch {
      clearTokens();
      set({
        user: null,
        accessToken: null,
        refreshToken: null,
        isAuthenticated: false,
      });
      return false;
    }
  },

  fetchCurrentUser: async () => {
    try {
      const res = await api.get('/api/auth/me');
      set({
        user: res.data.user,
        isAuthenticated: res.data.authenticated,
        isLoading: false,
      });
    } catch {
      set({ isLoading: false });
    }
  },

  fetchAuthStatus: async () => {
    try {
      const res = await api.get('/api/auth/status');
      const status: AuthStatus = res.data;
      set({
        authRequired: status.auth_required,
        ssoProviders: status.sso_providers || [],
        isLoading: false,
      });
    } catch {
      set({ isLoading: false, authRequired: false });
    }
  },

  setTokensFromUrl: () => {
    const params = new URLSearchParams(window.location.search);
    const access = params.get('access_token');
    const refresh = params.get('refresh_token');
    if (access) {
      saveTokens(access, refresh || '');
      set({
        accessToken: access,
        refreshToken: refresh,
        isAuthenticated: true,
      });
      // Clean URL
      window.history.replaceState({}, '', window.location.pathname);
    }
  },

  clearError: () => set({ error: null }),

  hasPermission: (permission: string) => {
    const { user } = get();
    if (!user) return false;
    const perms = ROLE_PERMISSIONS[user.role];
    return perms ? perms.has(permission) : false;
  },
}));

export default useAuthStore;
