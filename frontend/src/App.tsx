import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { lazy, Suspense, useEffect } from 'react';
import Layout from './components/Layout';
import { useAuthStore } from './lib/auth';

// Core pages (eagerly loaded — most visited)
import DashboardPage from './pages/Dashboard';
import ScansPage from './pages/Scans';
import LoginPage from './pages/Login';

// Secondary pages (lazy loaded for reduced initial bundle)
const ScanDetailPage = lazy(() => import('./pages/ScanDetail'));
const NewScanPage = lazy(() => import('./pages/NewScan'));
const SettingsPage = lazy(() => import('./pages/Settings'));
const WorkspacesPage = lazy(() => import('./pages/Workspaces'));
const ModulesPage = lazy(() => import('./pages/Modules'));
const DocumentationPage = lazy(() => import('./pages/Documentation'));
const AgentsPage = lazy(() => import('./pages/Agents'));
const UsersPage = lazy(() => import('./pages/Users'));
const SSOSettingsPage = lazy(() => import('./pages/SSOSettings'));
const ApiKeysPage = lazy(() => import('./pages/ApiKeys'));

function LazyFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin h-8 w-8 border-2 border-spider-500 border-t-transparent rounded-full" />
    </div>
  );
}

/**
 * Auth-aware route guard. When auth is required and the user is not
 * authenticated, redirects to /login. When auth is optional (default),
 * all routes are accessible.
 */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, authRequired, isLoading } = useAuthStore();
  const location = useLocation();

  if (isLoading) {
    return <LazyFallback />;
  }

  if (authRequired && !isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

/**
 * Permission-aware route guard.  Redirects to "/" when the current user
 * lacks the required permission.  Falls through silently when auth is
 * not enforced (authRequired === false) so development isn't impacted.
 */
function RequirePermission({ permission, children }: { permission: string; children: React.ReactNode }) {
  const { hasPermission, authRequired } = useAuthStore();

  if (authRequired && !hasPermission(permission)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  const { fetchAuthStatus, fetchCurrentUser, setTokensFromUrl, accessToken } = useAuthStore();

  // On mount: check for SSO tokens in URL, load auth status & current user
  useEffect(() => {
    setTokensFromUrl();
    fetchAuthStatus();
  }, [setTokensFromUrl, fetchAuthStatus]);

  // Fetch current user when access token changes
  useEffect(() => {
    if (accessToken) {
      fetchCurrentUser();
    }
  }, [accessToken, fetchCurrentUser]);

  return (
    <Routes>
      {/* Login page — always accessible */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected routes */}
      <Route path="/" element={<RequireAuth><Layout /></RequireAuth>}>
        {/* Dashboard / overview */}
        <Route index element={<DashboardPage />} />

        {/* Scans — matches CherryPy: /scanlist, /newscan, /scaninfo?id= */}
        <Route path="scans" element={<ScansPage />} />
        <Route path="scans/new" element={<Suspense fallback={<LazyFallback />}><NewScanPage /></Suspense>} />
        <Route path="scans/:scanId" element={<Suspense fallback={<LazyFallback />}><ScanDetailPage /></Suspense>} />

        {/* Workspaces — matches CherryPy: /workspaces, /workspacedetails */}
        <Route path="workspaces" element={<Suspense fallback={<LazyFallback />}><WorkspacesPage /></Suspense>} />

        {/* Modules — browse & manage all loaded modules */}
        <Route path="modules" element={<Suspense fallback={<LazyFallback />}><ModulesPage /></Suspense>} />

        {/* Documentation — matches CherryPy: /documentation */}
        <Route path="documentation" element={<Suspense fallback={<LazyFallback />}><DocumentationPage /></Suspense>} />

        {/* Settings — matches CherryPy: /opts */}
        <Route path="settings" element={<Suspense fallback={<LazyFallback />}><SettingsPage /></Suspense>} />

        {/* Agents — matches CherryPy: /agents (from Services) */}
        <Route path="agents" element={<Suspense fallback={<LazyFallback />}><AgentsPage /></Suspense>} />

        {/* User Management (admin only) */}
        <Route path="users" element={<RequirePermission permission="user:read"><Suspense fallback={<LazyFallback />}><UsersPage /></Suspense></RequirePermission>} />

        {/* SSO Settings (admin only) */}
        <Route path="sso-settings" element={<RequirePermission permission="system:admin"><Suspense fallback={<LazyFallback />}><SSOSettingsPage /></Suspense></RequirePermission>} />

        {/* API Keys (admin only) */}
        <Route path="api-keys" element={<RequirePermission permission="system:admin"><Suspense fallback={<LazyFallback />}><ApiKeysPage /></Suspense></RequirePermission>} />

        {/* CherryPy URL redirects for backward compatibility */}
        <Route path="newscan" element={<Navigate to="/scans/new" replace />} />
        <Route path="opts" element={<Navigate to="/settings" replace />} />
        <Route path="index" element={<Navigate to="/" replace />} />

        {/* 404 catch-all */}
        <Route path="*" element={
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <p className="text-4xl font-bold text-dark-400 mb-2">404</p>
            <p className="text-dark-500">Page not found</p>
          </div>
        } />
      </Route>
    </Routes>
  );
}
