import { useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scanApi, formatEpoch, formatDuration, type Scan } from '../lib/api';
import {
  ArrowLeft, StopCircle, RotateCcw,
  BarChart3, List, Settings, ScrollText,
  Shield, Network, Loader2, MapPin, Brain, PartyPopper,
} from 'lucide-react';
import { Tabs, StatusBadge, CopyButton, Skeleton, Toast, ProgressBar, Tooltip, type ToastType } from '../components/ui';
import {
  SummaryTab, BrowseTab, CorrelationsTab, GraphTab,
  GeoMapTab, ReportTab, SettingsTab, LogTab, ExportDropdown,
} from '../components/scan';
import { useScanProgress } from '../hooks/useScanProgress';
import { useNotificationStore } from '../lib/notifications';

type DetailTab = 'summary' | 'browse' | 'correlations' | 'graph' | 'geomap' | 'report' | 'settings' | 'log';

export default function ScanDetailPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<DetailTab>('summary');
  const [toast, setToast] = useState<{ type: ToastType; message: string } | null>(null);

  const isRunning = (s?: Scan) => ['RUNNING', 'STARTING'].includes(s?.status?.toUpperCase() ?? '');

  const [showCelebration, setShowCelebration] = useState(false);
  const addNotification = useNotificationStore((s) => s.add);

  const { data: scan, isLoading: scanLoading } = useQuery({
    queryKey: ['scan', scanId],
    queryFn: ({ signal }) => scanApi.get(scanId!, signal),
    enabled: !!scanId,
    refetchInterval: (query) => isRunning(query.state.data) ? 5000 : 30000,
  });

  // Real-time scan progress via SSE
  const { progress } = useScanProgress(scanId, {
    enabled: isRunning(scan),
    interval: 2,
    onComplete: useCallback(() => {
      queryClient.invalidateQueries({ queryKey: ['scan', scanId] });
      setShowCelebration(true);
      setTimeout(() => setShowCelebration(false), 4000);
      addNotification({
        type: 'scan_complete',
        title: 'Scan Complete',
        message: `${scan?.name || 'Scan'} finished successfully`,
        href: `/scans/${scanId}`,
      });
    }, [queryClient, scanId, scan?.name, addNotification]),
  });

  /* Mutations */
  const stopMut = useMutation({
    mutationFn: () => scanApi.stop(scanId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scan', scanId] });
      setToast({ type: 'success', message: 'Scan stopped' });
    },
    onError: () => {
      setToast({ type: 'error', message: 'Failed to stop scan' });
    },
  });
  const rerunMut = useMutation({
    mutationFn: () => scanApi.rerun(scanId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      setToast({ type: 'success', message: 'Rerun started' });
    },
    onError: () => {
      setToast({ type: 'error', message: 'Failed to rerun scan' });
    },
  });

  if (!scanId) return null;

  const tabs = [
    { key: 'summary' as const, label: 'Summary', icon: BarChart3 },
    { key: 'browse' as const, label: 'Browse', icon: List },
    { key: 'correlations' as const, label: 'Correlations', icon: Shield },
    { key: 'graph' as const, label: 'Graph', icon: Network },
    { key: 'geomap' as const, label: 'GeoMap', icon: MapPin },
    { key: 'report' as const, label: 'AI Report', icon: Brain },
    { key: 'settings' as const, label: 'Scan Settings', icon: Settings },
    { key: 'log' as const, label: 'Log', icon: ScrollText },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="animate-fade-in">
        <Link to="/scans" className="text-dark-400 hover:text-dark-200 text-sm flex items-center gap-1 mb-3 group">
          <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" /> Back to Scans
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            {scanLoading ? (
              <Skeleton className="h-8 w-64 mb-2" />
            ) : (
              <>
                <div className="flex items-center gap-3 mb-1">
                  <h1 className="text-2xl font-bold text-foreground">{scan?.name || 'Untitled Scan'}</h1>
                  <StatusBadge status={scan?.status ?? ''} />
                </div>
                <div className="flex items-center gap-3 text-sm text-dark-400">
                  <span className="font-mono">{scan?.target}</span>
                  <CopyButton text={scanId} />
                  <span>Started {formatEpoch(scan?.started ?? 0)}</span>
                  <span>{formatDuration(scan?.started ?? 0, scan?.ended ?? 0)}</span>
                </div>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {isRunning(scan) && (
              <button className="btn-danger" onClick={() => stopMut.mutate()} disabled={stopMut.isPending}>
                <StopCircle className="h-4 w-4" /> Stop
              </button>
            )}
            {!isRunning(scan) && (
              <button className="btn-secondary" onClick={() => rerunMut.mutate()} disabled={rerunMut.isPending}>
                <RotateCcw className="h-4 w-4" /> Rerun
              </button>
            )}
            <ExportDropdown scanId={scanId} scanName={scan?.name ?? ''} onToast={setToast} />
          </div>
        </div>
      </div>

      {/* Progress section */}
      {scan && (
        <div className="flex flex-col gap-3 animate-fade-in" style={{ animationDelay: '50ms' }}>
          <div className="flex items-center gap-6">
            {scan.result_count != null && (
              <span className="text-sm text-dark-400">{scan.result_count.toLocaleString()} results</span>
            )}
            {isRunning(scan) && progress && (
              <Tooltip content={`${progress.modules_finished}/${progress.modules_total} modules complete`} side="bottom">
                <span className="text-sm text-dark-400">
                  {progress.modules_running} modules running
                </span>
              </Tooltip>
            )}
            {isRunning(scan) && !progress && (
              <span className="flex items-center gap-1.5 text-blue-400 text-sm">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Scan in progress...
              </span>
            )}
          </div>
          {/* Live progress bar */}
          {isRunning(scan) && progress && (
            <div className="w-full max-w-xl animate-fade-in">
              <ProgressBar
                value={progress.overall_percent}
                max={100}
                color="bg-spider-500"
                showLabel
              />
            </div>
          )}
          {/* Celebration banner */}
          {showCelebration && (
            <div className="flex items-center gap-3 px-4 py-3 bg-green-900/20 border border-green-800/40 rounded-xl animate-fade-in-up">
              <PartyPopper className="h-5 w-5 text-green-400 animate-bounce" />
              <div>
                <p className="text-sm font-medium text-green-300">Scan Complete!</p>
                <p className="text-xs text-green-400/70">All modules finished — review your results below.</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <Tabs<DetailTab> tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {/* Tab Content */}
      <div className="animate-fade-in" key={activeTab}>
        {activeTab === 'summary' && <SummaryTab scanId={scanId} scan={scan} />}
        {activeTab === 'browse' && <BrowseTab scanId={scanId} />}
        {activeTab === 'correlations' && <CorrelationsTab scanId={scanId} />}
        {activeTab === 'graph' && <GraphTab scanId={scanId} />}
        {activeTab === 'geomap' && <GeoMapTab scanId={scanId} />}
        {activeTab === 'report' && <ReportTab scanId={scanId} scan={scan} />}
        {activeTab === 'settings' && <SettingsTab scanId={scanId} scan={scan} />}
        {activeTab === 'log' && <LogTab scanId={scanId} />}
      </div>

      {toast && <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} />}
    </div>
  );
}
