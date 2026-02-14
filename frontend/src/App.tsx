import { Routes, Route, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import Layout from './components/Layout';

// Core pages (eagerly loaded — most visited)
import DashboardPage from './pages/Dashboard';
import ScansPage from './pages/Scans';
import ScanDetailPage from './pages/ScanDetail';
import NewScanPage from './pages/NewScan';
import SettingsPage from './pages/Settings';

// Secondary pages (lazy loaded)
const WorkspacesPage = lazy(() => import('./pages/Workspaces'));
const DocumentationPage = lazy(() => import('./pages/Documentation'));
const AgentsPage = lazy(() => import('./pages/Agents'));

function LazyFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin h-8 w-8 border-2 border-spider-500 border-t-transparent rounded-full" />
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        {/* Dashboard / overview */}
        <Route index element={<DashboardPage />} />

        {/* Scans — matches CherryPy: /scanlist, /newscan, /scaninfo?id= */}
        <Route path="scans" element={<ScansPage />} />
        <Route path="scans/new" element={<NewScanPage />} />
        <Route path="scans/:scanId" element={<ScanDetailPage />} />

        {/* Workspaces — matches CherryPy: /workspaces, /workspacedetails */}
        <Route path="workspaces" element={<Suspense fallback={<LazyFallback />}><WorkspacesPage /></Suspense>} />

        {/* Documentation — matches CherryPy: /documentation */}
        <Route path="documentation" element={<Suspense fallback={<LazyFallback />}><DocumentationPage /></Suspense>} />

        {/* Settings — matches CherryPy: /opts */}
        <Route path="settings" element={<SettingsPage />} />

        {/* Agents — matches CherryPy: /agents (from Services) */}
        <Route path="agents" element={<Suspense fallback={<LazyFallback />}><AgentsPage /></Suspense>} />

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
