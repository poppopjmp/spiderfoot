import { Routes, Route } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import Layout from './components/Layout';

// Core pages
import DashboardPage from './pages/Dashboard';
import ScansPage from './pages/Scans';
import ScanDetailPage from './pages/ScanDetail';
import NewScanPage from './pages/NewScan';
import EnginesPage from './pages/Engines';
import SchedulesPage from './pages/Schedules';
import MonitorPage from './pages/Monitor';
import SettingsPage from './pages/Settings';

// Advanced pages (lazy loaded)
const RBACPage = lazy(() => import('./pages/RBAC'));
const ApiKeysPage = lazy(() => import('./pages/ApiKeys'));
const AuditPage = lazy(() => import('./pages/Audit'));
const CorrelationsPage = lazy(() => import('./pages/Correlations'));
const ReportTemplatesPage = lazy(() => import('./pages/ReportTemplates'));
const WebhooksPage = lazy(() => import('./pages/Webhooks'));
const TagsGroupsPage = lazy(() => import('./pages/TagsGroups'));
const NotificationsPage = lazy(() => import('./pages/Notifications'));
const ScanComparisonPage = lazy(() => import('./pages/ScanComparison'));
const DataRetentionPage = lazy(() => import('./pages/DataRetention'));
const DistributedPage = lazy(() => import('./pages/Distributed'));
const SSOPage = lazy(() => import('./pages/SSO'));
const ASMPage = lazy(() => import('./pages/ASM'));
const TenantsPage = lazy(() => import('./pages/Tenants'));
const MarketplacePage = lazy(() => import('./pages/Marketplace'));
const ExportPage = lazy(() => import('./pages/Export'));

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
        {/* Core */}
        <Route index element={<DashboardPage />} />
        <Route path="scans" element={<ScansPage />} />
        <Route path="scans/new" element={<NewScanPage />} />
        <Route path="scans/:scanId" element={<ScanDetailPage />} />
        <Route path="engines" element={<EnginesPage />} />
        <Route path="schedules" element={<SchedulesPage />} />
        <Route path="monitor" element={<MonitorPage />} />

        {/* Analysis */}
        <Route path="correlations" element={<Suspense fallback={<LazyFallback />}><CorrelationsPage /></Suspense>} />
        <Route path="scan-compare" element={<Suspense fallback={<LazyFallback />}><ScanComparisonPage /></Suspense>} />
        <Route path="asm" element={<Suspense fallback={<LazyFallback />}><ASMPage /></Suspense>} />

        {/* Reports & Export */}
        <Route path="report-templates" element={<Suspense fallback={<LazyFallback />}><ReportTemplatesPage /></Suspense>} />
        <Route path="export" element={<Suspense fallback={<LazyFallback />}><ExportPage /></Suspense>} />

        {/* Security */}
        <Route path="rbac" element={<Suspense fallback={<LazyFallback />}><RBACPage /></Suspense>} />
        <Route path="api-keys" element={<Suspense fallback={<LazyFallback />}><ApiKeysPage /></Suspense>} />
        <Route path="audit" element={<Suspense fallback={<LazyFallback />}><AuditPage /></Suspense>} />
        <Route path="sso" element={<Suspense fallback={<LazyFallback />}><SSOPage /></Suspense>} />

        {/* Enterprise */}
        <Route path="tenants" element={<Suspense fallback={<LazyFallback />}><TenantsPage /></Suspense>} />
        <Route path="tags-groups" element={<Suspense fallback={<LazyFallback />}><TagsGroupsPage /></Suspense>} />
        <Route path="data-retention" element={<Suspense fallback={<LazyFallback />}><DataRetentionPage /></Suspense>} />

        {/* Integrations */}
        <Route path="webhooks" element={<Suspense fallback={<LazyFallback />}><WebhooksPage /></Suspense>} />
        <Route path="notifications" element={<Suspense fallback={<LazyFallback />}><NotificationsPage /></Suspense>} />
        <Route path="marketplace" element={<Suspense fallback={<LazyFallback />}><MarketplacePage /></Suspense>} />
        <Route path="distributed" element={<Suspense fallback={<LazyFallback />}><DistributedPage /></Suspense>} />

        {/* Settings */}
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
