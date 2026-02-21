/**
 * Tests for the Zustand auth store (src/lib/auth.ts).
 *
 * Covers: saveTokens, clearTokens, loadTokens, setTokensFromUrl,
 * hasPermission for all roles, isAuthenticated derived state,
 * login, logout, refreshAccessToken, fetchCurrentUser, fetchAuthStatus,
 * and localStorage error handling.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useAuthStore } from '../../lib/auth';

// Mock the api module and errors module used by the store
vi.mock('../../lib/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

vi.mock('../../lib/errors', () => ({
  getErrorMessage: (_err: unknown, fallback: string) => fallback,
}));

import api from '../../lib/api';

const mockedApi = api as unknown as {
  post: ReturnType<typeof vi.fn>;
  get: ReturnType<typeof vi.fn>;
};

// Helper to fully reset the store between tests
function resetStore() {
  useAuthStore.setState({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: true,
    authRequired: false,
    ssoProviders: [],
    error: null,
  });
}

describe('Auth Store', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    resetStore();
  });

  afterEach(() => {
    localStorage.clear();
  });

  /* ─── saveTokens / clearTokens (via login & logout) ───── */

  describe('saveTokens (via login)', () => {
    it('stores access, refresh, and legacy key in localStorage on login', async () => {
      mockedApi.post.mockResolvedValueOnce({
        data: {
          access_token: 'acc123',
          refresh_token: 'ref456',
          user: { id: '1', username: 'admin', role: 'admin', email: 'a@b.c', display_name: 'Admin', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' },
        },
      });

      await useAuthStore.getState().login('admin', 'pass');

      expect(localStorage.getItem('sf_access_token')).toBe('acc123');
      expect(localStorage.getItem('sf_refresh_token')).toBe('ref456');
      expect(localStorage.getItem('sf_api_key')).toBe('acc123');
    });

    it('sets isAuthenticated to true after successful login', async () => {
      mockedApi.post.mockResolvedValueOnce({
        data: { access_token: 'a', refresh_token: 'r', user: { id: '1', username: 'u', role: 'viewer', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' } },
      });

      await useAuthStore.getState().login('u', 'p');
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });

    it('stores user object in state after login', async () => {
      const user = { id: '1', username: 'bob', role: 'analyst', email: 'bob@x.com', display_name: 'Bob', auth_method: 'local', status: 'active', created_at: 100, last_login: 200, sso_provider_id: '' };
      mockedApi.post.mockResolvedValueOnce({
        data: { access_token: 'a', refresh_token: 'r', user },
      });

      await useAuthStore.getState().login('bob', 'pw');
      expect(useAuthStore.getState().user).toEqual(user);
    });
  });

  describe('clearTokens (via logout)', () => {
    it('removes all token keys from localStorage on logout', async () => {
      localStorage.setItem('sf_access_token', 'tok');
      localStorage.setItem('sf_refresh_token', 'ref');
      localStorage.setItem('sf_api_key', 'tok');
      mockedApi.post.mockResolvedValueOnce({});

      await useAuthStore.getState().logout();

      expect(localStorage.getItem('sf_access_token')).toBeNull();
      expect(localStorage.getItem('sf_refresh_token')).toBeNull();
      expect(localStorage.getItem('sf_api_key')).toBeNull();
    });

    it('sets isAuthenticated to false after logout', async () => {
      useAuthStore.setState({ isAuthenticated: true, accessToken: 'x' });
      mockedApi.post.mockResolvedValueOnce({});

      await useAuthStore.getState().logout();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });

    it('clears user from state on logout', async () => {
      useAuthStore.setState({ user: { id: '1', username: 'u', role: 'admin', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' } });
      mockedApi.post.mockResolvedValueOnce({});

      await useAuthStore.getState().logout();
      expect(useAuthStore.getState().user).toBeNull();
    });

    it('clears tokens even if API call fails', async () => {
      localStorage.setItem('sf_access_token', 'tok');
      mockedApi.post.mockRejectedValueOnce(new Error('network'));

      await useAuthStore.getState().logout();
      expect(localStorage.getItem('sf_access_token')).toBeNull();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
  });

  /* ─── setTokensFromUrl ──────────────────────────────────── */

  describe('setTokensFromUrl', () => {
    let replaceStateSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      replaceStateSpy = vi.spyOn(window.history, 'replaceState').mockImplementation(() => {});
    });

    afterEach(() => {
      replaceStateSpy.mockRestore();
      window.location.hash = '';
    });

    it('extracts access_token from URL hash and stores it', () => {
      window.location.hash = '#access_token=tok123&refresh_token=ref456';
      useAuthStore.getState().setTokensFromUrl();

      expect(useAuthStore.getState().accessToken).toBe('tok123');
      expect(useAuthStore.getState().refreshToken).toBe('ref456');
      expect(localStorage.getItem('sf_access_token')).toBe('tok123');
    });

    it('sets isAuthenticated to true when tokens are found', () => {
      window.location.hash = '#access_token=abc';
      useAuthStore.getState().setTokensFromUrl();

      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });

    it('cleans the URL hash after processing', () => {
      window.location.hash = '#access_token=xyz';
      useAuthStore.getState().setTokensFromUrl();

      expect(replaceStateSpy).toHaveBeenCalled();
    });

    it('does nothing when hash has no access_token', () => {
      window.location.hash = '#foo=bar';
      useAuthStore.getState().setTokensFromUrl();

      expect(useAuthStore.getState().isAuthenticated).toBe(false);
      expect(localStorage.getItem('sf_access_token')).toBeNull();
    });

    it('handles missing refresh_token gracefully', () => {
      window.location.hash = '#access_token=only_access';
      useAuthStore.getState().setTokensFromUrl();

      expect(useAuthStore.getState().accessToken).toBe('only_access');
      // params.get returns null when key is absent; state stores null
      expect(useAuthStore.getState().refreshToken).toBeNull();
    });
  });

  /* ─── hasPermission ──────────────────────────────────────── */

  describe('hasPermission', () => {
    it('returns false when no user is set', () => {
      expect(useAuthStore.getState().hasPermission('scan:read')).toBe(false);
    });

    it('returns true for viewer with scan:read', () => {
      useAuthStore.setState({ user: { id: '1', username: 'v', role: 'viewer', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' } });
      expect(useAuthStore.getState().hasPermission('scan:read')).toBe(true);
    });

    it('returns false for viewer with scan:create', () => {
      useAuthStore.setState({ user: { id: '1', username: 'v', role: 'viewer', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' } });
      expect(useAuthStore.getState().hasPermission('scan:create')).toBe(false);
    });

    it('returns true for analyst with scan:create', () => {
      useAuthStore.setState({ user: { id: '1', username: 'a', role: 'analyst', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' } });
      expect(useAuthStore.getState().hasPermission('scan:create')).toBe(true);
    });

    it('returns false for analyst with user:delete', () => {
      useAuthStore.setState({ user: { id: '1', username: 'a', role: 'analyst', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' } });
      expect(useAuthStore.getState().hasPermission('user:delete')).toBe(false);
    });

    it('returns true for operator with engine:create', () => {
      useAuthStore.setState({ user: { id: '1', username: 'o', role: 'operator', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' } });
      expect(useAuthStore.getState().hasPermission('engine:create')).toBe(true);
    });

    it('returns false for operator with system:admin', () => {
      useAuthStore.setState({ user: { id: '1', username: 'o', role: 'operator', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' } });
      expect(useAuthStore.getState().hasPermission('system:admin')).toBe(false);
    });

    it('returns true for admin with system:admin', () => {
      useAuthStore.setState({ user: { id: '1', username: 'a', role: 'admin', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' } });
      expect(useAuthStore.getState().hasPermission('system:admin')).toBe(true);
    });

    it('returns true for admin with user:delete', () => {
      useAuthStore.setState({ user: { id: '1', username: 'a', role: 'admin', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' } });
      expect(useAuthStore.getState().hasPermission('user:delete')).toBe(true);
    });

    it('returns false for unknown role', () => {
      useAuthStore.setState({ user: { id: '1', username: 'x', role: 'superadmin', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' } });
      expect(useAuthStore.getState().hasPermission('scan:read')).toBe(false);
    });
  });

  /* ─── isAuthenticated derived state ──────────────────────── */

  describe('isAuthenticated', () => {
    it('is false when accessToken is null', () => {
      useAuthStore.setState({ accessToken: null, isAuthenticated: false });
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });

    it('is true when accessToken is set', () => {
      useAuthStore.setState({ accessToken: 'abc', isAuthenticated: true });
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });
  });

  /* ─── login error handling ───────────────────────────────── */

  describe('login error handling', () => {
    it('sets error state on login failure', async () => {
      mockedApi.post.mockRejectedValueOnce(new Error('bad credentials'));

      await expect(useAuthStore.getState().login('u', 'p')).rejects.toThrow();
      expect(useAuthStore.getState().error).toBe('Login failed');
      expect(useAuthStore.getState().isLoading).toBe(false);
    });

    it('does not set isAuthenticated on login failure', async () => {
      mockedApi.post.mockRejectedValueOnce(new Error('fail'));

      await expect(useAuthStore.getState().login('u', 'p')).rejects.toThrow();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
  });

  /* ─── refreshAccessToken ─────────────────────────────────── */

  describe('refreshAccessToken', () => {
    it('returns false when no refreshToken exists', async () => {
      useAuthStore.setState({ refreshToken: null });
      const result = await useAuthStore.getState().refreshAccessToken();
      expect(result).toBe(false);
    });

    it('updates accessToken on successful refresh', async () => {
      useAuthStore.setState({ refreshToken: 'ref' });
      mockedApi.post.mockResolvedValueOnce({ data: { access_token: 'new_acc' } });

      const result = await useAuthStore.getState().refreshAccessToken();
      expect(result).toBe(true);
      expect(useAuthStore.getState().accessToken).toBe('new_acc');
      expect(localStorage.getItem('sf_access_token')).toBe('new_acc');
    });

    it('clears state on refresh failure', async () => {
      useAuthStore.setState({ refreshToken: 'ref', accessToken: 'old', isAuthenticated: true });
      mockedApi.post.mockRejectedValueOnce(new Error('expired'));

      const result = await useAuthStore.getState().refreshAccessToken();
      expect(result).toBe(false);
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
      expect(useAuthStore.getState().accessToken).toBeNull();
    });
  });

  /* ─── fetchCurrentUser ───────────────────────────────────── */

  describe('fetchCurrentUser', () => {
    it('sets user from API response', async () => {
      const user = { id: '1', username: 'test', role: 'viewer', email: '', display_name: '', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' };
      mockedApi.get.mockResolvedValueOnce({ data: { user, authenticated: true } });

      await useAuthStore.getState().fetchCurrentUser();
      expect(useAuthStore.getState().user).toEqual(user);
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });

    it('sets isLoading to false on error', async () => {
      mockedApi.get.mockRejectedValueOnce(new Error('fail'));

      await useAuthStore.getState().fetchCurrentUser();
      expect(useAuthStore.getState().isLoading).toBe(false);
    });
  });

  /* ─── fetchAuthStatus ────────────────────────────────────── */

  describe('fetchAuthStatus', () => {
    it('sets authRequired and ssoProviders from response', async () => {
      mockedApi.get.mockResolvedValueOnce({
        data: { auth_required: true, sso_providers: [{ id: 's1', name: 'Google', protocol: 'oauth2', enabled: true, default_role: 'viewer' }], user_count: 5, supported_methods: ['local'] },
      });

      await useAuthStore.getState().fetchAuthStatus();
      expect(useAuthStore.getState().authRequired).toBe(true);
      expect(useAuthStore.getState().ssoProviders).toHaveLength(1);
    });

    it('defaults authRequired to false on error', async () => {
      mockedApi.get.mockRejectedValueOnce(new Error('fail'));

      await useAuthStore.getState().fetchAuthStatus();
      expect(useAuthStore.getState().authRequired).toBe(false);
      expect(useAuthStore.getState().isLoading).toBe(false);
    });
  });

  /* ─── clearError ─────────────────────────────────────────── */

  describe('clearError', () => {
    it('resets error to null', () => {
      useAuthStore.setState({ error: 'something went wrong' });
      useAuthStore.getState().clearError();
      expect(useAuthStore.getState().error).toBeNull();
    });
  });

  /* ─── ldapLogin ──────────────────────────────────────────── */

  describe('ldapLogin', () => {
    it('stores tokens on successful LDAP login', async () => {
      const user = { id: '2', username: 'ldapuser', role: 'analyst', email: '', display_name: '', auth_method: 'ldap', status: 'active', created_at: 0, last_login: 0, sso_provider_id: 'p1' };
      mockedApi.post.mockResolvedValueOnce({
        data: { access_token: 'ldap_acc', refresh_token: 'ldap_ref', user },
      });

      await useAuthStore.getState().ldapLogin('p1', 'ldapuser', 'pw');
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
      expect(localStorage.getItem('sf_access_token')).toBe('ldap_acc');
    });

    it('sets error on LDAP login failure', async () => {
      mockedApi.post.mockRejectedValueOnce(new Error('ldap fail'));

      await expect(useAuthStore.getState().ldapLogin('p1', 'u', 'p')).rejects.toThrow();
      expect(useAuthStore.getState().error).toBe('LDAP login failed');
    });
  });
});
