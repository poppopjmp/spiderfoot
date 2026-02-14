/**
 * SpiderFoot Login Page
 *
 * Supports local username/password, LDAP, OAuth2 SSO, and SAML SSO.
 * Displays available SSO providers fetched from the auth status endpoint.
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, SSOProvider } from '../lib/auth';
import {
  Shield,
  LogIn,
  Eye,
  EyeOff,
  Server,
  Globe,
  KeyRound,
  AlertCircle,
} from 'lucide-react';
import { clsx } from 'clsx';

export default function LoginPage() {
  const navigate = useNavigate();
  const {
    login,
    ldapLogin,
    isAuthenticated,
    ssoProviders,
    fetchAuthStatus,
    setTokensFromUrl,
    error,
    clearError,
  } = useAuthStore();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loginMethod, setLoginMethod] = useState<'local' | 'ldap'>('local');
  const [selectedLdapProvider, setSelectedLdapProvider] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Check for SSO callback tokens in URL
  useEffect(() => {
    setTokensFromUrl();
  }, [setTokensFromUrl]);

  // Fetch auth status for SSO providers
  useEffect(() => {
    fetchAuthStatus();
  }, [fetchAuthStatus]);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const ldapProviders = ssoProviders.filter(
    (p: SSOProvider) => p.protocol === 'ldap' && p.enabled
  );
  const oauthProviders = ssoProviders.filter(
    (p: SSOProvider) => p.protocol === 'oauth2' && p.enabled
  );
  const samlProviders = ssoProviders.filter(
    (p: SSOProvider) => p.protocol === 'saml' && p.enabled
  );

  const handleLocalLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    clearError();
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch {
      // Error is set in store
    } finally {
      setSubmitting(false);
    }
  };

  const handleLdapLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLdapProvider) return;
    setSubmitting(true);
    clearError();
    try {
      await ldapLogin(selectedLdapProvider, username, password);
      navigate('/', { replace: true });
    } catch {
      // Error is set in store
    } finally {
      setSubmitting(false);
    }
  };

  const handleOAuthLogin = (provider: SSOProvider) => {
    window.location.href = `/api/auth/sso/oauth2/login/${provider.id}`;
  };

  const handleSamlLogin = (provider: SSOProvider) => {
    window.location.href = `/api/auth/sso/saml/login/${provider.id}`;
  };

  // URL error from SSO callback
  const urlError = new URLSearchParams(window.location.search).get('error');

  return (
    <div className="min-h-screen bg-dark-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo & title */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <img src="/spiderfoot-icon.png" alt="SpiderFoot" className="h-12 w-12" />
            <h1 className="text-3xl font-bold text-white">SpiderFoot</h1>
          </div>
          <p className="text-dark-400 text-sm">OSINT Automation Platform</p>
        </div>

        {/* Login card */}
        <div className="bg-dark-900 border border-dark-700 rounded-xl p-6 shadow-2xl">
          {/* Error display */}
          {(error || urlError) && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-red-400 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-400">{error || urlError}</p>
            </div>
          )}

          {/* Login method tabs */}
          {ldapProviders.length > 0 && (
            <div className="flex mb-6 bg-dark-800 rounded-lg p-1">
              <button
                className={clsx(
                  'flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors flex items-center justify-center gap-1.5',
                  loginMethod === 'local'
                    ? 'bg-dark-700 text-white'
                    : 'text-dark-400 hover:text-dark-300'
                )}
                onClick={() => { setLoginMethod('local'); clearError(); }}
              >
                <KeyRound className="h-4 w-4" />
                Local
              </button>
              <button
                className={clsx(
                  'flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors flex items-center justify-center gap-1.5',
                  loginMethod === 'ldap'
                    ? 'bg-dark-700 text-white'
                    : 'text-dark-400 hover:text-dark-300'
                )}
                onClick={() => { setLoginMethod('ldap'); clearError(); }}
              >
                <Server className="h-4 w-4" />
                LDAP
              </button>
            </div>
          )}

          {/* Local login form */}
          {loginMethod === 'local' && (
            <form onSubmit={handleLocalLogin} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-dark-300 mb-1.5">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-3 py-2.5 bg-dark-800 border border-dark-600 rounded-lg text-white placeholder-dark-500 focus:outline-none focus:border-spider-500 focus:ring-1 focus:ring-spider-500 transition-colors"
                  placeholder="Enter username"
                  autoFocus
                  autoComplete="username"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-300 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-3 py-2.5 bg-dark-800 border border-dark-600 rounded-lg text-white placeholder-dark-500 focus:outline-none focus:border-spider-500 focus:ring-1 focus:ring-spider-500 transition-colors pr-10"
                    placeholder="Enter password"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-500 hover:text-dark-300"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <button
                type="submit"
                disabled={submitting || !username || !password}
                className="w-full py-2.5 bg-spider-600 hover:bg-spider-500 disabled:bg-dark-700 disabled:text-dark-500 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                {submitting ? (
                  <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                ) : (
                  <LogIn className="h-4 w-4" />
                )}
                Sign In
              </button>
            </form>
          )}

          {/* LDAP login form */}
          {loginMethod === 'ldap' && (
            <form onSubmit={handleLdapLogin} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-dark-300 mb-1.5">
                  LDAP Provider
                </label>
                <select
                  value={selectedLdapProvider}
                  onChange={(e) => setSelectedLdapProvider(e.target.value)}
                  className="w-full px-3 py-2.5 bg-dark-800 border border-dark-600 rounded-lg text-white focus:outline-none focus:border-spider-500 focus:ring-1 focus:ring-spider-500 transition-colors"
                >
                  <option value="">Select provider...</option>
                  {ldapProviders.map((p: SSOProvider) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-300 mb-1.5">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-3 py-2.5 bg-dark-800 border border-dark-600 rounded-lg text-white placeholder-dark-500 focus:outline-none focus:border-spider-500 focus:ring-1 focus:ring-spider-500 transition-colors"
                  placeholder="LDAP username"
                  autoComplete="username"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-300 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-3 py-2.5 bg-dark-800 border border-dark-600 rounded-lg text-white placeholder-dark-500 focus:outline-none focus:border-spider-500 focus:ring-1 focus:ring-spider-500 transition-colors pr-10"
                    placeholder="LDAP password"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-500 hover:text-dark-300"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <button
                type="submit"
                disabled={submitting || !username || !password || !selectedLdapProvider}
                className="w-full py-2.5 bg-spider-600 hover:bg-spider-500 disabled:bg-dark-700 disabled:text-dark-500 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                {submitting ? (
                  <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                ) : (
                  <Server className="h-4 w-4" />
                )}
                Sign In with LDAP
              </button>
            </form>
          )}

          {/* SSO divider */}
          {(oauthProviders.length > 0 || samlProviders.length > 0) && (
            <div className="mt-6">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-dark-700" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-dark-900 px-2 text-dark-500 uppercase tracking-wider">
                    or continue with
                  </span>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                {oauthProviders.map((p: SSOProvider) => (
                  <button
                    key={p.id}
                    onClick={() => handleOAuthLogin(p)}
                    className="w-full py-2.5 bg-dark-800 hover:bg-dark-700 border border-dark-600 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <Globe className="h-4 w-4 text-blue-400" />
                    {p.name}
                  </button>
                ))}
                {samlProviders.map((p: SSOProvider) => (
                  <button
                    key={p.id}
                    onClick={() => handleSamlLogin(p)}
                    className="w-full py-2.5 bg-dark-800 hover:bg-dark-700 border border-dark-600 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <Shield className="h-4 w-4 text-green-400" />
                    {p.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-dark-600 text-xs mt-6">
          SpiderFoot OSINT Platform — Secure Access
        </p>
      </div>
    </div>
  );
}
