import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import DashboardPage from './pages/Dashboard';
import ScansPage from './pages/Scans';
import ScanDetailPage from './pages/ScanDetail';
import NewScanPage from './pages/NewScan';
import EnginesPage from './pages/Engines';
import SchedulesPage from './pages/Schedules';
import MonitorPage from './pages/Monitor';
import SettingsPage from './pages/Settings';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="scans" element={<ScansPage />} />
        <Route path="scans/new" element={<NewScanPage />} />
        <Route path="scans/:scanId" element={<ScanDetailPage />} />
        <Route path="engines" element={<EnginesPage />} />
        <Route path="schedules" element={<SchedulesPage />} />
        <Route path="monitor" element={<MonitorPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
