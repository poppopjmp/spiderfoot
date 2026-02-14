import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  scanApi, agentsApi, formatEpoch, formatDuration,
  type Scan, type ScanEvent, type ScanCorrelation, type ScanLogEntry, type EventSummaryDetail,
} from '../lib/api';
import {
  ArrowLeft, StopCircle, RotateCcw, Download, Share2,
  BarChart3, List, Settings, ScrollText,
  AlertTriangle, Shield, Info, Eye, EyeOff,
  FileText, Network, Loader2, RefreshCw,
  MapPin, Brain, Edit3, Save, Sparkles,
} from 'lucide-react';
import {
  Tabs, StatusBadge, CopyButton, SearchInput,
  EmptyState, Skeleton, TableSkeleton, Toast,
  DropdownMenu, DropdownItem, Expandable,
  type ToastType,
} from '../components/ui';

type DetailTab = 'summary' | 'browse' | 'correlations' | 'graph' | 'geomap' | 'report' | 'settings' | 'log';

export default function ScanDetailPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<DetailTab>('summary');
  const [toast, setToast] = useState<{ type: ToastType; message: string } | null>(null);

  const isRunning = (s?: Scan) => ['RUNNING', 'STARTING'].includes(s?.status?.toUpperCase() ?? '');

  const { data: scan, isLoading: scanLoading } = useQuery({
    queryKey: ['scan', scanId],
    queryFn: () => scanApi.get(scanId!),
    enabled: !!scanId,
    refetchInterval: (query) => isRunning(query.state.data) ? 5000 : 30000,
  });

  /* Mutations */
  const stopMut = useMutation({
    mutationFn: () => scanApi.stop(scanId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scan', scanId] });
      setToast({ type: 'success', message: 'Scan stopped' });
    },
  });
  const rerunMut = useMutation({
    mutationFn: () => scanApi.rerun(scanId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      setToast({ type: 'success', message: 'Rerun started' });
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
                  <h1 className="text-2xl font-bold text-white">{scan?.name || 'Untitled Scan'}</h1>
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
            <ExportDropdown scanId={scanId} scanName={scan?.name ?? ''} />
          </div>
        </div>
      </div>

      {/* Risk pills row */}
      {scan && (
        <div className="flex items-center gap-6 animate-fade-in" style={{ animationDelay: '50ms' }}>
          {scan.result_count != null && (
            <span className="text-sm text-dark-400">{scan.result_count.toLocaleString()} results</span>
          )}
          {isRunning(scan) && (
            <span className="flex items-center gap-1.5 text-blue-400 text-sm">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Scan in progress...
            </span>
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

/* ── Export Dropdown ───────────────────────────────────────── */
function ExportDropdown({ scanId, scanName }: { scanId: string; scanName: string }) {
  const download = async (type: string) => {
    try {
      const resp = await scanApi.exportEvents(scanId, { filetype: type });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${scanName || scanId}.${type}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  };

  return (
    <DropdownMenu trigger={<button className="btn-secondary"><Download className="h-4 w-4" /> Export</button>}>
      <DropdownItem icon={FileText} onClick={() => download('csv')}>CSV</DropdownItem>
      <DropdownItem icon={FileText} onClick={() => download('xlsx')}>Excel (XLSX)</DropdownItem>
      <DropdownItem icon={FileText} onClick={() => download('json')}>JSON</DropdownItem>
      <DropdownItem icon={Share2} onClick={() => download('gexf')}>GEXF (Graph)</DropdownItem>
    </DropdownMenu>
  );
}

/* ── Summary Tab ──────────────────────────────────────────── */
function SummaryTab({ scanId, scan }: { scanId: string; scan?: Scan }) {
  const { data: summaryData, isLoading } = useQuery({
    queryKey: ['scan-summary', scanId],
    queryFn: () => scanApi.summary(scanId),
    enabled: !!scanId,
  });

  const { data: corrData } = useQuery({
    queryKey: ['scan-correlations-summary', scanId],
    queryFn: () => scanApi.correlationsSummary(scanId, 'risk'),
    enabled: !!scanId,
  });

  const details: EventSummaryDetail[] = summaryData?.details ?? [];
  const sorted = [...details].sort((a, b) => b.total - a.total);
  const totalEvents = sorted.reduce((sum, d) => sum + d.total, 0);

  /* Correlations summary */
  const corrRaw = corrData?.summary ?? [];
  const corrBreakdown: Record<string, number> = {};
  if (Array.isArray(corrRaw)) {
    corrRaw.forEach((item: { risk?: string; total?: number }) => {
      if (item.risk) corrBreakdown[item.risk] = item.total ?? 0;
    });
  } else if (typeof corrRaw === 'object') {
    Object.assign(corrBreakdown, corrRaw);
  }
  const corrTotal = Object.values(corrBreakdown).reduce((s, v) => s + v, 0);

  /* Simple doughnut - top 8 categories */
  const top8 = sorted.slice(0, 8);
  const colors = [
    '#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6',
    '#8b5cf6', '#ef4444', '#06b6d4',
  ];

  return (
    <div className="space-y-6">
      {/* Stat row */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <MiniStat label="Data Types" value={summaryData?.total_types ?? 0} />
        <MiniStat label="Total Events" value={totalEvents} />
        <MiniStat label="Unique Values" value={sorted.reduce((s, d) => s + d.unique_total, 0)} />
        <MiniStat label="Correlations" value={corrTotal} />
        <MiniStat label="Duration" value={formatDuration(scan?.started ?? 0, scan?.ended ?? 0)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Doughnut chart (CSS-based) */}
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-4">Event Distribution</h3>
          {isLoading ? (
            <Skeleton className="h-48 w-48 rounded-full mx-auto" />
          ) : top8.length > 0 ? (
            <div className="space-y-3">
              {top8.map((d, i) => {
                const pct = totalEvents > 0 ? (d.total / totalEvents) * 100 : 0;
                return (
                  <div key={d.key} className="flex items-center gap-3">
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: colors[i] }} />
                    <span className="text-xs text-dark-300 flex-1 truncate">{d.description || d.key}</span>
                    <span className="text-xs text-dark-500 tabular-nums w-8 text-right">{d.total}</span>
                    <div className="w-20">
                      <div className="progress-bar">
                        <div className="progress-fill animate-progress" style={{ width: `${pct}%`, backgroundColor: colors[i] }} />
                      </div>
                    </div>
                  </div>
                );
              })}
              {sorted.length > 8 && (
                <p className="text-xs text-dark-600 text-center">+{sorted.length - 8} more types</p>
              )}
            </div>
          ) : (
            <p className="text-dark-500 text-sm text-center py-8">No data yet</p>
          )}
        </div>

        {/* Full data types table */}
        <div className="lg:col-span-2 card">
          <h3 className="text-sm font-semibold text-white mb-4">Data Types ({sorted.length})</h3>
          {isLoading ? (
            <TableSkeleton rows={6} cols={4} />
          ) : (
            <div className="overflow-y-auto max-h-[500px] -mx-2">
              <table className="w-full">
                <thead className="sticky top-0 bg-dark-800">
                  <tr className="border-b border-dark-700/60">
                    <th className="table-header">Type</th>
                    <th className="table-header text-right">Total</th>
                    <th className="table-header text-right">Unique</th>
                    <th className="table-header text-right">Last Seen</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700/30">
                  {sorted.map((d, i) => (
                    <tr key={d.key} className="table-row animate-fade-in" style={{ animationDelay: `${i * 15}ms` }}>
                      <td className="table-cell text-white text-xs">{d.description || d.key}</td>
                      <td className="table-cell text-right tabular-nums text-dark-300">{d.total}</td>
                      <td className="table-cell text-right tabular-nums text-dark-400">{d.unique_total}</td>
                      <td className="table-cell text-right text-dark-500 text-xs whitespace-nowrap">{formatEpoch(d.last_in)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Correlation Risk Breakdown */}
      {corrTotal > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-4">Correlation Summary</h3>
          <div className="flex flex-wrap gap-4">
            {Object.entries(corrBreakdown).map(([risk, count]) => {
              const bgClass = risk.toLowerCase() === 'critical' || risk.toLowerCase() === 'high'
                ? 'bg-red-900/30 text-red-300 border-red-700/40'
                : risk.toLowerCase() === 'medium'
                ? 'bg-yellow-900/30 text-yellow-300 border-yellow-700/40'
                : risk.toLowerCase() === 'low'
                ? 'bg-blue-900/30 text-blue-300 border-blue-700/40'
                : 'bg-dark-700/30 text-dark-300 border-dark-600/40';
              return (
                <div key={risk} className={`px-4 py-3 rounded-lg border ${bgClass} text-center min-w-[100px]`}>
                  <p className="text-lg font-bold">{count}</p>
                  <p className="text-xs opacity-80 capitalize">{risk}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Browse Tab ───────────────────────────────────────────── */
function BrowseTab({ scanId }: { scanId: string }) {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewUnique, setViewUnique] = useState(false);
  const [hideFP, setHideFP] = useState(false);
  const queryClient = useQueryClient();

  const { data: summaryData } = useQuery({
    queryKey: ['scan-summary', scanId],
    queryFn: () => scanApi.summary(scanId),
  });

  const { data: eventsData, isLoading: eventsLoading } = useQuery({
    queryKey: ['scan-events', scanId, selectedType, false],
    queryFn: () => scanApi.events(scanId, { event_type: selectedType ?? undefined }),
    enabled: !!selectedType && !viewUnique,
  });

  const { data: uniqueData, isLoading: uniqueLoading } = useQuery({
    queryKey: ['scan-events-unique', scanId, selectedType],
    queryFn: () => scanApi.eventsUnique(scanId, selectedType ?? undefined),
    enabled: !!selectedType && viewUnique,
  });

  const details: EventSummaryDetail[] = summaryData?.details ?? [];
  const events: ScanEvent[] = eventsData?.events ?? [];
  const uniqueEvents = uniqueData?.events ?? [];

  /* False positive mutation */
  const fpMut = useMutation({
    mutationFn: ({ hashList, fp }: { hashList: string[]; fp: boolean }) =>
      scanApi.setFalsePositive(scanId, hashList, fp),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scan-events', scanId] });
    },
  });

  const filteredEvents = useMemo(() => {
    let list = events;
    if (hideFP) list = list.filter((e: ScanEvent) => !e.false_positive);
    if (!searchQuery) return list;
    const q = searchQuery.toLowerCase();
    return list.filter(
      (e: ScanEvent) => e.data?.toLowerCase().includes(q) || e.module?.toLowerCase().includes(q) || e.source_data?.toLowerCase().includes(q),
    );
  }, [events, searchQuery, hideFP]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
      {/* Type list */}
      <div className="card p-0 overflow-hidden">
        <div className="p-3 border-b border-dark-700/50">
          <h3 className="text-sm font-semibold text-white">Data Types</h3>
        </div>
        <div className="overflow-y-auto max-h-[600px]">
          {details.sort((a, b) => b.total - a.total).map((d) => (
            <button
              key={d.key}
              onClick={() => { setSelectedType(d.key); setSearchQuery(''); }}
              className={`w-full flex items-center justify-between px-3 py-2.5 text-left text-sm transition-colors ${
                selectedType === d.key
                  ? 'bg-spider-600/10 text-spider-400 border-l-2 border-spider-500'
                  : 'text-dark-300 hover:bg-dark-700/30 border-l-2 border-transparent'
              }`}
            >
              <span className="truncate">{d.description || d.key}</span>
              <span className="text-xs text-dark-500 tabular-nums ml-2">{d.total}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Events */}
      <div className="lg:col-span-3 card">
        {selectedType ? (
          <>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white">{selectedType}</h3>
              <div className="flex items-center gap-2">
                <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Filter events..." className="w-60" />
                <button
                  className={hideFP ? 'btn-primary text-xs' : 'btn-secondary text-xs'}
                  onClick={() => setHideFP(!hideFP)}
                  title={hideFP ? 'Show false positives' : 'Hide false positives'}
                >
                  {hideFP ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                  FP
                </button>
                <button
                  className={viewUnique ? 'btn-primary text-xs' : 'btn-secondary text-xs'}
                  onClick={() => setViewUnique(!viewUnique)}
                >
                  {viewUnique ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                  {viewUnique ? 'Unique' : 'All'}
                </button>
              </div>
            </div>

            {(eventsLoading || uniqueLoading) ? (
              <TableSkeleton rows={8} cols={4} />
            ) : viewUnique ? (
              uniqueEvents.length > 0 ? (
                <div className="overflow-y-auto max-h-[500px]">
                  <table className="w-full">
                    <thead className="sticky top-0 bg-dark-800">
                      <tr className="border-b border-dark-700/60">
                        <th className="table-header">Value</th>
                        <th className="table-header text-right">Count</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-700/30">
                      {uniqueEvents.map((e: { data: string; count: number }, i: number) => (
                        <tr key={i} className="table-row">
                          <td className="table-cell font-mono text-xs text-dark-200 break-all">{e.data}</td>
                          <td className="table-cell text-right tabular-nums text-dark-400">{e.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-dark-500 text-sm text-center py-8">No unique data</p>
              )
            ) : (
              filteredEvents.length > 0 ? (
                <div className="overflow-y-auto max-h-[500px]">
                  <table className="w-full">
                    <thead className="sticky top-0 bg-dark-800">
                      <tr className="border-b border-dark-700/60">
                        <th className="table-header">Data</th>
                        <th className="table-header">Module</th>
                        <th className="table-header">Source</th>
                        <th className="table-header text-right">Time</th>
                        <th className="table-header w-10 text-center" title="False Positive">FP</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-700/30">
                      {filteredEvents.map((e: ScanEvent, i: number) => (
                        <tr key={e.hash || i} className={`table-row ${e.false_positive ? 'opacity-40' : ''}`}>
                          <td className="table-cell font-mono text-xs text-dark-200 break-all max-w-md">
                            <span className={`line-clamp-3 ${e.false_positive ? 'line-through' : ''}`}>{e.data}</span>
                          </td>
                          <td className="table-cell text-dark-400 text-xs whitespace-nowrap">
                            {e.module?.replace('sfp_', '')}
                          </td>
                          <td className="table-cell text-dark-500 text-xs truncate max-w-xs">{e.source_data}</td>
                          <td className="table-cell text-right text-dark-500 text-xs whitespace-nowrap">
                            {formatEpoch(e.generated)}
                          </td>
                          <td className="table-cell text-center">
                            {e.hash && (
                              <button
                                onClick={() => fpMut.mutate({ hashList: [e.hash!], fp: !e.false_positive })}
                                className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                                  e.false_positive
                                    ? 'bg-yellow-900/30 text-yellow-400 hover:bg-yellow-900/50'
                                    : 'text-dark-600 hover:text-yellow-400 hover:bg-dark-700/50'
                                }`}
                                title={e.false_positive ? 'Unmark as false positive' : 'Mark as false positive'}
                              >
                                FP
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-dark-500 text-sm text-center py-8">
                  {searchQuery ? 'No matching events' : 'No events for this type'}
                </p>
              )
            )}
          </>
        ) : (
          <EmptyState
            icon={List}
            title="Select a data type"
            description="Choose a data type from the left panel to view its events."
            className="py-12"
          />
        )}
      </div>
    </div>
  );
}

/* ── Correlations Tab ─────────────────────────────────────── */
function CorrelationsTab({ scanId }: { scanId: string }) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['scan-correlations', scanId],
    queryFn: () => scanApi.correlations(scanId),
  });

  const runMut = useMutation({
    mutationFn: () => scanApi.runCorrelations(scanId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scan-correlations', scanId] }),
  });

  const correlations: ScanCorrelation[] = data?.correlations ?? [];

  const riskIcon = (risk: string) => {
    const r = risk?.toLowerCase();
    if (r === 'high' || r === 'critical') return <AlertTriangle className="h-4 w-4 text-red-400" />;
    if (r === 'medium') return <Info className="h-4 w-4 text-yellow-400" />;
    if (r === 'low') return <Shield className="h-4 w-4 text-blue-400" />;
    return <Info className="h-4 w-4 text-dark-400" />;
  };

  const riskBadge = (risk: string) => {
    const r = risk?.toLowerCase();
    if (r === 'high' || r === 'critical') return 'badge-critical';
    if (r === 'medium') return 'badge-medium';
    if (r === 'low') return 'badge-low';
    return 'badge-info';
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-dark-400">{correlations.length} correlation(s) found</p>
        <button
          className="btn-secondary"
          onClick={() => runMut.mutate()}
          disabled={runMut.isPending}
        >
          {runMut.isPending ? (
            <><Loader2 className="h-4 w-4 animate-spin" /> Running...</>
          ) : (
            <><RefreshCw className="h-4 w-4" /> Run Correlations</>
          )}
        </button>
      </div>

      {isLoading ? (
        <TableSkeleton rows={5} cols={4} />
      ) : correlations.length > 0 ? (
        <div className="space-y-3">
          {correlations.map((c, i) => (
            <Expandable
              key={c.id || i}
              title={c.rule_name || c.title}
              badge={<span className={`badge ${riskBadge(c.rule_risk)}`}>{c.rule_risk}</span>}
              className="animate-fade-in"
            >
              <div className="space-y-3 pt-2">
                <div className="flex items-start gap-2">
                  {riskIcon(c.rule_risk)}
                  <div>
                    <p className="text-sm text-dark-200">{c.rule_descr}</p>
                    <p className="text-xs text-dark-500 mt-1">Rule: {c.rule_id} · Events: {c.event_count}</p>
                    {c.rule_logic && (
                      <pre className="text-xs text-dark-500 mt-2 bg-dark-900/50 rounded p-2 overflow-x-auto">{c.rule_logic}</pre>
                    )}
                  </div>
                </div>
              </div>
            </Expandable>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Shield}
          title="No correlations yet"
          description="Click 'Run Correlations' to analyze the scan data for patterns and insights."
          action={
            <button className="btn-primary" onClick={() => runMut.mutate()} disabled={runMut.isPending}>
              <RefreshCw className="h-4 w-4" /> Run Now
            </button>
          }
        />
      )}
    </div>
  );
}

/* ── Graph Tab ────────────────────────────────────────────── */
function GraphTab({ scanId }: { scanId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['scan-viz', scanId],
    queryFn: () => scanApi.viz(scanId),
  });

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [graphReady, setGraphReady] = useState(false);

  const downloadGexf = async () => {
    try {
      const resp = await scanApi.exportEvents(scanId, { filetype: 'gexf' });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${scanId}.gexf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  };

  const nodes = data?.nodes ?? [];
  const edges = data?.edges ?? [];

  /* Simple force-directed graph on canvas */
  useEffect(() => {
    if (!canvasRef.current || nodes.length === 0) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.offsetWidth * (window.devicePixelRatio || 1);
    canvas.height = canvas.offsetHeight * (window.devicePixelRatio || 1);
    ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;

    // Initialize node positions
    const nodeMap = new Map<string, { x: number; y: number; vx: number; vy: number; label: string; color: string }>();
    const typeColors: Record<string, string> = {
      'ROOT': '#22c55e', 'IP_ADDRESS': '#3b82f6', 'INTERNET_NAME': '#6366f1',
      'EMAILADDR': '#ec4899', 'DOMAIN_NAME': '#f59e0b', 'HUMAN_NAME': '#8b5cf6',
      'PHONE_NUMBER': '#06b6d4', 'ASN': '#ef4444',
    };
    nodes.forEach((n: { id: string; label?: string; type?: string }) => {
      nodeMap.set(n.id, {
        x: w / 2 + (Math.random() - 0.5) * w * 0.6,
        y: h / 2 + (Math.random() - 0.5) * h * 0.6,
        vx: 0, vy: 0,
        label: n.label || n.id.slice(0, 16),
        color: typeColors[n.type || ''] || '#64748b',
      });
    });

    const edgeList = edges.map((e: { source: string; target: string }) => ({
      src: nodeMap.get(e.source),
      tgt: nodeMap.get(e.target),
    })).filter((e: { src?: unknown; tgt?: unknown }) => e.src && e.tgt);

    let running = true;
    let frame = 0;
    const maxFrames = 200;

    function tick() {
      if (!running || !ctx) return;
      frame++;
      const alpha = Math.max(0.01, 1 - frame / maxFrames);

      // Repulsion (simplified Barnes-Hut)
      const allNodes = [...nodeMap.values()];
      for (let i = 0; i < allNodes.length; i++) {
        for (let j = i + 1; j < allNodes.length; j++) {
          const a = allNodes[i], b = allNodes[j];
          let dx = b.x - a.x, dy = b.y - a.y;
          const d = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = (150 / (d * d)) * alpha;
          dx *= force; dy *= force;
          a.vx -= dx; a.vy -= dy;
          b.vx += dx; b.vy += dy;
        }
      }

      // Attraction (edges)
      edgeList.forEach((e: { src: { x: number; y: number; vx: number; vy: number }; tgt: { x: number; y: number; vx: number; vy: number } }) => {
        let dx = e.tgt.x - e.src.x, dy = e.tgt.y - e.src.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (d - 80) * 0.005 * alpha;
        dx = (dx / d) * force; dy = (dy / d) * force;
        e.src.vx += dx; e.src.vy += dy;
        e.tgt.vx -= dx; e.tgt.vy -= dy;
      });

      // Center gravity
      allNodes.forEach((n) => {
        n.vx += (w / 2 - n.x) * 0.001 * alpha;
        n.vy += (h / 2 - n.y) * 0.001 * alpha;
        n.vx *= 0.85; n.vy *= 0.85;
        n.x = Math.max(20, Math.min(w - 20, n.x + n.vx));
        n.y = Math.max(20, Math.min(h - 20, n.y + n.vy));
      });

      // Draw
      ctx.clearRect(0, 0, w, h);

      // Edges
      ctx.globalAlpha = 0.15;
      ctx.strokeStyle = '#64748b';
      ctx.lineWidth = 0.5;
      edgeList.forEach((e: { src: { x: number; y: number }; tgt: { x: number; y: number } }) => {
        ctx.beginPath();
        ctx.moveTo(e.src.x, e.src.y);
        ctx.lineTo(e.tgt.x, e.tgt.y);
        ctx.stroke();
      });

      // Nodes
      ctx.globalAlpha = 1;
      allNodes.forEach((n) => {
        ctx.beginPath();
        ctx.arc(n.x, n.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.fill();
      });

      // Labels (only for small graphs)
      if (allNodes.length <= 60) {
        ctx.font = '9px Inter, system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = '#94a3b8';
        allNodes.forEach((n) => {
          ctx.fillText(n.label.slice(0, 20), n.x, n.y + 14);
        });
      }

      if (frame < maxFrames) requestAnimationFrame(tick);
      else setGraphReady(true);
    }

    tick();
    return () => { running = false; };
  }, [nodes, edges]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-dark-400">
          {nodes.length} nodes · {edges.length} edges
          {graphReady && <span className="text-green-400 ml-2">● Layout complete</span>}
        </p>
        <button className="btn-secondary" onClick={downloadGexf}>
          <Download className="h-4 w-4" /> Download GEXF
        </button>
      </div>

      <div className="card p-0 overflow-hidden" style={{ minHeight: '500px' }}>
        {isLoading ? (
          <div className="flex items-center justify-center h-[500px]">
            <Loader2 className="h-8 w-8 text-dark-500 animate-spin" />
          </div>
        ) : nodes.length > 0 ? (
          <canvas
            ref={canvasRef}
            className="w-full h-[500px] cursor-move"
            style={{ background: '#0f172a' }}
          />
        ) : (
          <div className="flex items-center justify-center h-[500px]">
            <EmptyState
              icon={Network}
              title="No graph data"
              description="Graph data will be available once the scan produces results."
            />
          </div>
        )}
      </div>
    </div>
  );
}

/* ── GeoMap Tab ────────────────────────────────────────────── */
const GEO_EVENT_TYPES = ['GEOINFO', 'PHYSICAL_COORDINATES', 'COUNTRY_NAME', 'PHYSICAL_ADDRESS'];

// Country code → approximate lat/lon for map positioning
const COUNTRY_COORDS: Record<string, [number, number]> = {
  US: [37.0902, -95.7129], GB: [55.3781, -3.4360], DE: [51.1657, 10.4515], FR: [46.2276, 2.2137],
  CA: [56.1304, -106.3468], AU: [-25.2744, 133.7751], JP: [36.2048, 138.2529], CN: [35.8617, 104.1954],
  IN: [20.5937, 78.9629], BR: [-14.2350, -51.9253], RU: [61.5240, 105.3188], NL: [52.1326, 5.2913],
  SE: [60.1282, 18.6435], IT: [41.8719, 12.5674], ES: [40.4637, -3.7492], KR: [35.9078, 127.7669],
  SG: [1.3521, 103.8198], IE: [53.1424, -7.6921], CH: [46.8182, 8.2275], PL: [51.9194, 19.1451],
  NO: [60.4720, 8.4689], FI: [61.9241, 25.7482], DK: [56.2639, 9.5018], AT: [47.5162, 14.5501],
  BE: [50.5039, 4.4699], CZ: [49.8175, 15.4730], PT: [39.3999, -8.2245], MX: [23.6345, -102.5528],
  AR: [-38.4161, -63.6167], ZA: [-30.5595, 22.9375], IL: [31.0461, 34.8516], AE: [23.4241, 53.8478],
  TW: [23.6978, 120.9605], HK: [22.3193, 114.1694], MY: [4.2105, 101.9758], TH: [15.8700, 100.9925],
  PH: [12.8797, 121.7740], VN: [14.0583, 108.2772], ID: [-0.7893, 113.9213], NZ: [-40.9006, 174.8860],
  UA: [48.3794, 31.1656], RO: [45.9432, 24.9668], HU: [47.1625, 19.5033], BG: [42.7339, 25.4858],
  HR: [45.1000, 15.2000], SK: [48.6690, 19.6990], LT: [55.1694, 23.8813], LV: [56.8796, 24.6032],
  EE: [58.5953, 25.0136], GR: [39.0742, 21.8243], TR: [38.9637, 35.2433], EG: [26.8206, 30.8025],
  NG: [9.0820, 8.6753], KE: [0.0236, 37.9062], CO: [4.5709, -74.2973], CL: [-35.6751, -71.5430],
  PE: [-9.1900, -75.0152], VE: [6.4238, -66.5897],
};

function GeoMapTab({ scanId }: { scanId: string }) {
  /* Fetch all geo-related event types */
  const geoQueries = GEO_EVENT_TYPES.map((t) => ({
    queryKey: ['scan-events-geo', scanId, t],
    queryFn: () => scanApi.events(scanId, { event_type: t }),
    enabled: !!scanId,
  }));

  const q0 = useQuery(geoQueries[0]);
  const q1 = useQuery(geoQueries[1]);
  const q2 = useQuery(geoQueries[2]);
  const q3 = useQuery(geoQueries[3]);

  const isLoading = q0.isLoading || q1.isLoading || q2.isLoading || q3.isLoading;

  /* Parse country data from GEOINFO events */
  const countryMap = useMemo(() => {
    const map = new Map<string, { count: number; city?: string; full?: string }>();
    const geoEvents: ScanEvent[] = q0.data?.events ?? [];
    const countryNameEvents: ScanEvent[] = q2.data?.events ?? [];

    // GEOINFO data can be "US", "DE", or "Clifton, New Jersey, NJ, United States, US"
    geoEvents.forEach((e) => {
      const d = e.data?.trim();
      if (!d) return;
      // If it's a 2-char code
      if (d.length === 2 && /^[A-Z]{2}$/i.test(d)) {
        const code = d.toUpperCase();
        const prev = map.get(code) ?? { count: 0 };
        map.set(code, { ...prev, count: prev.count + 1 });
      } else {
        // Try to extract country code from the end: "..., US"
        const parts = d.split(',').map((p: string) => p.trim());
        const lastPart = parts[parts.length - 1];
        if (lastPart && lastPart.length === 2 && /^[A-Z]{2}$/i.test(lastPart)) {
          const code = lastPart.toUpperCase();
          const prev = map.get(code) ?? { count: 0 };
          const city = parts[0];
          map.set(code, { count: prev.count + 1, city: prev.city ?? city, full: d });
        }
      }
    });

    // Also parse COUNTRY_NAME events (full names like "United States")
    const ccMap: Record<string, string> = {
      'united states': 'US', 'united kingdom': 'GB', 'germany': 'DE', 'france': 'FR',
      'canada': 'CA', 'australia': 'AU', 'japan': 'JP', 'china': 'CN', 'india': 'IN',
      'brazil': 'BR', 'russia': 'RU', 'netherlands': 'NL', 'sweden': 'SE', 'italy': 'IT',
      'spain': 'ES', 'south korea': 'KR', 'singapore': 'SG', 'ireland': 'IE',
      'switzerland': 'CH', 'poland': 'PL', 'norway': 'NO', 'finland': 'FI', 'denmark': 'DK',
      'austria': 'AT', 'belgium': 'BE', 'czech republic': 'CZ', 'czechia': 'CZ',
      'portugal': 'PT', 'mexico': 'MX', 'argentina': 'AR', 'south africa': 'ZA',
      'israel': 'IL', 'united arab emirates': 'AE', 'taiwan': 'TW', 'hong kong': 'HK',
      'malaysia': 'MY', 'thailand': 'TH', 'philippines': 'PH', 'vietnam': 'VN',
      'indonesia': 'ID', 'new zealand': 'NZ', 'ukraine': 'UA', 'romania': 'RO',
      'hungary': 'HU', 'bulgaria': 'BG', 'croatia': 'HR', 'turkey': 'TR', 'egypt': 'EG',
      'nigeria': 'NG', 'kenya': 'KE', 'colombia': 'CO', 'chile': 'CL', 'peru': 'PE',
    };
    countryNameEvents.forEach((e) => {
      const name = e.data?.trim().toLowerCase();
      if (!name) return;
      const code = ccMap[name];
      if (code) {
        const prev = map.get(code) ?? { count: 0 };
        map.set(code, { ...prev, count: prev.count + 1 });
      }
    });

    return map;
  }, [q0.data, q2.data]);

  /* Parse coordinates */
  const coordinates = useMemo(() => {
    const coords: { lat: number; lon: number; label: string }[] = [];
    const coordEvents: ScanEvent[] = q1.data?.events ?? [];
    coordEvents.forEach((e) => {
      const parts = e.data?.split(',');
      if (parts?.length === 2) {
        const lat = parseFloat(parts[0]);
        const lon = parseFloat(parts[1]);
        if (!isNaN(lat) && !isNaN(lon)) {
          coords.push({ lat, lon, label: e.source_data || `${lat.toFixed(4)}, ${lon.toFixed(4)}` });
        }
      }
    });
    return coords;
  }, [q1.data]);

  /* Physical addresses */
  const addresses = useMemo(() => {
    return (q3.data?.events ?? []).map((e: ScanEvent) => e.data).filter(Boolean);
  }, [q3.data]);

  /* Sorted countries */
  const countryList = useMemo(() =>
    [...countryMap.entries()]
      .map(([code, info]) => ({ code, ...info }))
      .sort((a, b) => b.count - a.count),
    [countryMap],
  );

  const maxCount = countryList[0]?.count ?? 1;
  const totalGeoEvents = countryList.reduce((s, c) => s + c.count, 0) + coordinates.length + addresses.length;

  /* SVG World Map (equirectangular projection) */
  const mapWidth = 800;
  const mapHeight = 400;
  const projectLon = (lon: number) => ((lon + 180) / 360) * mapWidth;
  const projectLat = (lat: number) => ((90 - lat) / 180) * mapHeight;

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MiniStat label="Countries" value={countryList.length} />
        <MiniStat label="Geo Events" value={totalGeoEvents} />
        <MiniStat label="Coordinates" value={coordinates.length} />
        <MiniStat label="Addresses" value={addresses.length} />
      </div>

      {isLoading ? (
        <TableSkeleton rows={6} cols={3} />
      ) : totalGeoEvents === 0 ? (
        <EmptyState
          icon={MapPin}
          title="No geolocation data"
          description="Geolocation data will appear once the scan discovers location-related information."
        />
      ) : (
        <>
          {/* Map visualization */}
          <div className="card">
            <h3 className="text-sm font-semibold text-white mb-4">Geographic Distribution</h3>
            <div className="w-full overflow-x-auto">
              <svg viewBox={`0 0 ${mapWidth} ${mapHeight}`} className="w-full min-w-[600px]" style={{ background: '#0c1222' }}>
                {/* Grid lines */}
                {[-60, -30, 0, 30, 60].map((lat) => (
                  <line key={`lat-${lat}`} x1={0} y1={projectLat(lat)} x2={mapWidth} y2={projectLat(lat)}
                    stroke="#1e293b" strokeWidth={0.5} />
                ))}
                {[-120, -60, 0, 60, 120].map((lon) => (
                  <line key={`lon-${lon}`} x1={projectLon(lon)} y1={0} x2={projectLon(lon)} y2={mapHeight}
                    stroke="#1e293b" strokeWidth={0.5} />
                ))}
                {/* Equator */}
                <line x1={0} y1={projectLat(0)} x2={mapWidth} y2={projectLat(0)} stroke="#334155" strokeWidth={0.8} strokeDasharray="4,4" />
                {/* Prime Meridian */}
                <line x1={projectLon(0)} y1={0} x2={projectLon(0)} y2={mapHeight} stroke="#334155" strokeWidth={0.8} strokeDasharray="4,4" />

                {/* Country markers */}
                {countryList.map((c) => {
                  const pos = COUNTRY_COORDS[c.code];
                  if (!pos) return null;
                  const [lat, lon] = pos;
                  const r = 4 + (c.count / maxCount) * 16;
                  return (
                    <g key={c.code}>
                      <circle cx={projectLon(lon)} cy={projectLat(lat)} r={r}
                        fill="#6366f1" fillOpacity={0.3} stroke="#6366f1" strokeWidth={1} />
                      <circle cx={projectLon(lon)} cy={projectLat(lat)} r={3}
                        fill="#818cf8" />
                      <text x={projectLon(lon)} y={projectLat(lat) - r - 4}
                        textAnchor="middle" fill="#c7d2fe" fontSize={10} fontFamily="Inter, system-ui, sans-serif">
                        {c.code} ({c.count})
                      </text>
                    </g>
                  );
                })}

                {/* Coordinate pins */}
                {coordinates.map((c, i) => (
                  <g key={`coord-${i}`}>
                    <circle cx={projectLon(c.lon)} cy={projectLat(c.lat)} r={5}
                      fill="#f59e0b" fillOpacity={0.5} stroke="#f59e0b" strokeWidth={1.5} />
                    <circle cx={projectLon(c.lon)} cy={projectLat(c.lat)} r={2}
                      fill="#fbbf24" />
                  </g>
                ))}
              </svg>
            </div>
            <div className="flex items-center gap-6 mt-3 text-xs text-dark-500">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-indigo-500/50 border border-indigo-500 inline-block" /> Country (by event count)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-amber-500/50 border border-amber-500 inline-block" /> Exact Coordinates
              </span>
            </div>
          </div>

          {/* Country distribution */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card">
              <h3 className="text-sm font-semibold text-white mb-4">Country Distribution ({countryList.length})</h3>
              <div className="space-y-2.5 max-h-[400px] overflow-y-auto">
                {countryList.map((c, i) => {
                  const pct = maxCount > 0 ? (c.count / maxCount) * 100 : 0;
                  return (
                    <div key={c.code} className="flex items-center gap-3 animate-fade-in" style={{ animationDelay: `${i * 30}ms` }}>
                      <span className="text-sm font-mono text-dark-200 w-8">{c.code}</span>
                      <div className="flex-1">
                        <div className="progress-bar">
                          <div className="progress-fill animate-progress" style={{ width: `${pct}%`, backgroundColor: '#6366f1' }} />
                        </div>
                      </div>
                      <span className="text-xs text-dark-400 tabular-nums w-6 text-right">{c.count}</span>
                      {c.city && <span className="text-xs text-dark-600 truncate max-w-[120px]">{c.city}</span>}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="card">
              <h3 className="text-sm font-semibold text-white mb-4">Locations & Addresses</h3>
              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {coordinates.length > 0 && (
                  <div>
                    <p className="text-xs text-dark-500 uppercase tracking-wider mb-2">Coordinates</p>
                    {coordinates.map((c, i) => (
                      <div key={i} className="flex items-center gap-2 py-1.5 border-b border-dark-700/30 last:border-0">
                        <MapPin className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
                        <span className="text-xs font-mono text-dark-200">{c.lat.toFixed(4)}, {c.lon.toFixed(4)}</span>
                        <span className="text-xs text-dark-500 truncate flex-1">{c.label}</span>
                      </div>
                    ))}
                  </div>
                )}
                {addresses.length > 0 && (
                  <div>
                    <p className="text-xs text-dark-500 uppercase tracking-wider mb-2">Physical Addresses</p>
                    {addresses.map((addr: string, i: number) => (
                      <div key={i} className="flex items-start gap-2 py-1.5 border-b border-dark-700/30 last:border-0">
                        <MapPin className="h-3.5 w-3.5 text-green-400 flex-shrink-0 mt-0.5" />
                        <span className="text-xs text-dark-200">{addr}</span>
                      </div>
                    ))}
                  </div>
                )}
                {coordinates.length === 0 && addresses.length === 0 && (
                  <p className="text-dark-500 text-sm text-center py-8">No specific locations found</p>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ── AI Report Tab ────────────────────────────────────────── */
function ReportTab({ scanId, scan }: { scanId: string; scan?: Scan }) {
  const [reportContent, setReportContent] = useState<string>('');
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const editorRef = useRef<HTMLTextAreaElement>(null);

  /* Try to load persisted report from localStorage */
  const storageKey = `sf_report_${scanId}`;
  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) setReportContent(saved);
  }, [storageKey]);

  /* Fetch scan data for report context */
  const { data: summaryData } = useQuery({
    queryKey: ['scan-summary', scanId],
    queryFn: () => scanApi.summary(scanId),
    enabled: !!scanId,
  });

  const { data: corrData } = useQuery({
    queryKey: ['scan-correlations', scanId],
    queryFn: () => scanApi.correlations(scanId),
    enabled: !!scanId,
  });

  /* Generate report mutation */
  const generateMut = useMutation({
    mutationFn: async () => {
      const details = summaryData?.details ?? [];
      const correlations = corrData?.correlations ?? [];
      const findings = details.slice(0, 20).map((d: EventSummaryDetail) => ({
        type: d.key,
        description: d.description,
        total: d.total,
        unique: d.unique_total,
      }));

      return agentsApi.report({
        scan_id: scanId,
        target: scan?.target ?? '',
        findings,
        correlations: correlations.map((c: ScanCorrelation) => ({
          rule_id: c.rule_id,
          rule_name: c.rule_name,
          risk: c.rule_risk,
          description: c.rule_descr,
          event_count: c.event_count,
        })),
        stats: {
          total_events: details.reduce((s: number, d: EventSummaryDetail) => s + d.total, 0),
          total_types: summaryData?.total_types ?? 0,
          scan_status: scan?.status,
          duration: formatDuration(scan?.started ?? 0, scan?.ended ?? 0),
        },
      });
    },
    onSuccess: (data) => {
      const md = data?.report ?? data?.content ?? data?.markdown ?? JSON.stringify(data, null, 2);
      setReportContent(md);
      localStorage.setItem(storageKey, md);
    },
  });

  /* Fallback: generate a client-side report if the API fails or is unavailable */
  const generateClientReport = useCallback(() => {
    const details = summaryData?.details ?? [];
    const correlations: ScanCorrelation[] = corrData?.correlations ?? [];
    const totalEvents = details.reduce((s: number, d: EventSummaryDetail) => s + d.total, 0);

    const lines: string[] = [
      `# Threat Intelligence Report`,
      ``,
      `**Target:** ${scan?.target ?? 'Unknown'}`,
      `**Scan ID:** \`${scanId}\``,
      `**Status:** ${scan?.status ?? 'Unknown'}`,
      `**Generated:** ${new Date().toLocaleString()}`,
      `**Duration:** ${formatDuration(scan?.started ?? 0, scan?.ended ?? 0)}`,
      ``,
      `---`,
      ``,
      `## Executive Summary`,
      ``,
      `This report summarizes the findings from the OSINT scan of **${scan?.target}**.`,
      `The scan discovered **${totalEvents.toLocaleString()}** data points across **${details.length}** different types.`,
      correlations.length > 0
        ? `**${correlations.length}** correlation rules were triggered, indicating potential security insights.`
        : `No correlation rules were triggered.`,
      ``,
      `## Data Discovery`,
      ``,
      `| Type | Total | Unique |`,
      `|------|------:|-------:|`,
    ];

    const sorted = [...details].sort((a, b) => b.total - a.total);
    sorted.slice(0, 20).forEach((d) => {
      lines.push(`| ${d.description || d.key} | ${d.total} | ${d.unique_total} |`);
    });
    if (sorted.length > 20) lines.push(`| *(${sorted.length - 20} more types)* | | |`);

    if (correlations.length > 0) {
      lines.push('', '## Correlation Findings', '');
      const bySeverity: Record<string, ScanCorrelation[]> = {};
      correlations.forEach((c) => {
        const k = c.rule_risk || 'info';
        (bySeverity[k] ??= []).push(c);
      });

      ['critical', 'high', 'medium', 'low', 'info'].forEach((sev) => {
        const list = bySeverity[sev];
        if (!list?.length) return;
        lines.push(`### ${sev.charAt(0).toUpperCase() + sev.slice(1)} Severity`, '');
        list.forEach((c) => {
          lines.push(`- **${c.rule_name}** — ${c.rule_descr} *(${c.event_count} events)*`);
        });
        lines.push('');
      });
    }

    lines.push(
      '## Recommendations',
      '',
      '> *Edit this section to add your analysis and recommendations.*',
      '',
      '1. Review high-risk correlation findings above.',
      '2. Investigate exposed services and potential data leaks.',
      '3. Validate discovered credentials and access paths.',
      '',
      '---',
      '*Report generated by SpiderFoot AI Threat Intel Analyzer*',
    );

    const md = lines.join('\n');
    setReportContent(md);
    localStorage.setItem(storageKey, md);
  }, [summaryData, corrData, scan, scanId, storageKey]);

  const startEditing = () => {
    setEditContent(reportContent);
    setIsEditing(true);
    setTimeout(() => editorRef.current?.focus(), 50);
  };

  const saveEdit = () => {
    setReportContent(editContent);
    localStorage.setItem(storageKey, editContent);
    setIsEditing(false);
  };

  const cancelEdit = () => {
    setIsEditing(false);
  };

  /* Simple Markdown renderer */
  const renderMarkdown = (md: string) => {
    const lines = md.split('\n');
    const html: string[] = [];
    let inTable = false;
    let inBlockquote = false;
    let inList = false;

    lines.forEach((line) => {
      // HR
      if (/^---+$/.test(line.trim())) {
        if (inList) { html.push('</ul>'); inList = false; }
        if (inBlockquote) { html.push('</blockquote>'); inBlockquote = false; }
        html.push('<hr class="border-dark-700/50 my-4" />');
        return;
      }

      // Headers
      const hMatch = line.match(/^(#{1,6})\s+(.*)/);
      if (hMatch) {
        if (inList) { html.push('</ul>'); inList = false; }
        if (inBlockquote) { html.push('</blockquote>'); inBlockquote = false; }
        const level = hMatch[1].length;
        const sizes: Record<number, string> = { 1: 'text-xl', 2: 'text-lg', 3: 'text-base', 4: 'text-sm', 5: 'text-sm', 6: 'text-xs' };
        html.push(`<h${level} class="${sizes[level]} font-bold text-white mt-4 mb-2">${inlineFormat(hMatch[2])}</h${level}>`);
        return;
      }

      // Table row
      if (line.trim().startsWith('|')) {
        if (!inTable) { html.push('<table class="w-full text-xs my-2"><tbody>'); inTable = true; }
        // Skip separator rows
        if (/^\|[-:|\s]+\|$/.test(line.trim())) return;
        const cells = line.split('|').filter((c) => c.trim() !== '');
        const isHeader = !html.some((l) => l.includes('<tr'));
        html.push('<tr class="border-b border-dark-700/30">');
        cells.forEach((cell) => {
          const tag = isHeader ? 'th' : 'td';
          const cls = isHeader ? 'table-header text-left' : 'table-cell text-dark-300';
          const align = cell.trim().match(/^\d/) ? ' text-right' : '';
          html.push(`<${tag} class="${cls}${align}">${inlineFormat(cell.trim())}</${tag}>`);
        });
        html.push('</tr>');
        return;
      } else if (inTable) {
        html.push('</tbody></table>');
        inTable = false;
      }

      // Blockquote
      if (line.trim().startsWith('>')) {
        if (!inBlockquote) { html.push('<blockquote class="border-l-2 border-spider-500 pl-3 my-2 text-dark-400 italic text-sm">'); inBlockquote = true; }
        html.push(`<p>${inlineFormat(line.replace(/^>\s*/, ''))}</p>`);
        return;
      } else if (inBlockquote) {
        html.push('</blockquote>');
        inBlockquote = false;
      }

      // List items
      const liMatch = line.match(/^(\d+\.|[-*])\s+(.*)/);
      if (liMatch) {
        if (!inList) { html.push('<ul class="list-disc list-inside space-y-1 my-2 text-sm text-dark-300">'); inList = true; }
        html.push(`<li>${inlineFormat(liMatch[2])}</li>`);
        return;
      } else if (inList && line.trim() === '') {
        html.push('</ul>');
        inList = false;
      }

      // Empty line
      if (line.trim() === '') {
        html.push('<div class="h-2"></div>');
        return;
      }

      // Regular paragraph
      html.push(`<p class="text-sm text-dark-300 leading-relaxed">${inlineFormat(line)}</p>`);
    });

    if (inTable) html.push('</tbody></table>');
    if (inList) html.push('</ul>');
    if (inBlockquote) html.push('</blockquote>');

    return html.join('\n');
  };

  const inlineFormat = (text: string): string => {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code class="bg-dark-700 px-1 py-0.5 rounded text-spider-400 text-xs font-mono">$1</code>');
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-dark-400">
          {reportContent ? 'AI-generated threat intelligence report' : 'Generate a comprehensive threat report'}
        </p>
        <div className="flex items-center gap-2">
          {reportContent && !isEditing && (
            <button className="btn-secondary" onClick={startEditing}>
              <Edit3 className="h-4 w-4" /> Edit
            </button>
          )}
          {isEditing && (
            <>
              <button className="btn-secondary" onClick={cancelEdit}>Cancel</button>
              <button className="btn-primary" onClick={saveEdit}>
                <Save className="h-4 w-4" /> Save
              </button>
            </>
          )}
          <button
            className="btn-primary"
            onClick={() => generateMut.mutate()}
            disabled={generateMut.isPending}
          >
            {generateMut.isPending ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Generating...</>
            ) : (
              <><Sparkles className="h-4 w-4" /> Generate AI Report</>
            )}
          </button>
          {!reportContent && (
            <button className="btn-secondary" onClick={generateClientReport}>
              <FileText className="h-4 w-4" /> Quick Report
            </button>
          )}
        </div>
      </div>

      {generateMut.isError && (
        <div className="card border border-yellow-700/40 bg-yellow-900/10">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-yellow-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm text-yellow-300">AI report generation failed — the agents service may be unavailable.</p>
              <button className="text-xs text-yellow-400 underline mt-1" onClick={generateClientReport}>
                Generate client-side report instead
              </button>
            </div>
          </div>
        </div>
      )}

      {isEditing ? (
        <div className="card p-0 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-dark-700/30 border-b border-dark-700/50">
            <span className="text-xs text-dark-400">Markdown Editor</span>
            <span className="text-xs text-dark-600">{editContent.length} chars</span>
          </div>
          <textarea
            ref={editorRef}
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="w-full bg-dark-900 text-dark-200 font-mono text-xs p-4 focus:outline-none resize-y"
            style={{ minHeight: '500px' }}
            spellCheck={false}
          />
        </div>
      ) : reportContent ? (
        <div className="card">
          <div
            className="markdown-report"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(reportContent) }}
          />
        </div>
      ) : (
        <EmptyState
          icon={Brain}
          title="No report generated"
          description="Click 'Generate AI Report' to create a comprehensive threat intelligence report based on the scan data, or 'Quick Report' for a client-side summary."
          action={
            <div className="flex gap-2">
              <button className="btn-primary" onClick={() => generateMut.mutate()} disabled={generateMut.isPending}>
                <Sparkles className="h-4 w-4" /> Generate AI Report
              </button>
              <button className="btn-secondary" onClick={generateClientReport}>
                <FileText className="h-4 w-4" /> Quick Report
              </button>
            </div>
          }
        />
      )}
    </div>
  );
}

/* ── Scan Settings Tab ────────────────────────────────────── */
function SettingsTab({ scanId, scan }: { scanId: string; scan?: Scan }) {
  const { data: options, isLoading } = useQuery({
    queryKey: ['scan-options', scanId],
    queryFn: () => scanApi.options(scanId),
  });

  const scanOptions = options?.options ?? options ?? {};

  /* Separate global vs module settings */
  const globalEntries = Object.entries(scanOptions).filter(([k]) => !k.includes(':'));
  const moduleEntries = Object.entries(scanOptions).filter(([k]) => k.includes(':'));
  const moduleGroups = new Map<string, [string, unknown][]>();
  moduleEntries.forEach(([k, v]) => {
    const [mod] = k.split(':');
    if (!moduleGroups.has(mod)) moduleGroups.set(mod, []);
    moduleGroups.get(mod)!.push([k.split(':').slice(1).join(':'), v]);
  });

  return (
    <div className="space-y-6">
      {/* Scan Meta */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-4">Scan Information</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {[
            ['Scan ID', scanId],
            ['Name', scan?.name],
            ['Target', scan?.target],
            ['Status', scan?.status],
            ['Created', formatEpoch(scan?.created ?? 0)],
            ['Started', formatEpoch(scan?.started ?? 0)],
            ['Ended', formatEpoch(scan?.ended ?? 0)],
            ['Duration', formatDuration(scan?.started ?? 0, scan?.ended ?? 0)],
            ['Results', scan?.result_count?.toString()],
          ].map(([label, val]) => (
            <div key={label as string}>
              <p className="text-xs text-dark-500">{label as string}</p>
              <p className="text-sm text-dark-200 font-mono break-all">{(val as string) || '—'}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Global Settings */}
      {globalEntries.length > 0 && (
        <Expandable title={`Global Settings (${globalEntries.length})`} defaultOpen>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            {globalEntries.map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs">
                <span className="text-dark-400">{k}</span>
                <span className="text-dark-200 font-mono truncate ml-2 text-right max-w-[50%]">{String(v)}</span>
              </div>
            ))}
          </div>
        </Expandable>
      )}

      {/* Per-Module Settings */}
      {[...moduleGroups.entries()].map(([mod, entries]) => (
        <Expandable key={mod} title={`${mod} (${entries.length} options)`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            {entries.map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs">
                <span className="text-dark-400">{k}</span>
                <span className="text-dark-200 font-mono truncate ml-2 text-right max-w-[50%]">{String(v)}</span>
              </div>
            ))}
          </div>
        </Expandable>
      ))}

      {isLoading && <TableSkeleton rows={4} cols={2} />}
    </div>
  );
}

/* ── Log Tab ──────────────────────────────────────────────── */
function LogTab({ scanId }: { scanId: string }) {
  const [logFilter, setLogFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['scan-logs', scanId],
    queryFn: () => scanApi.logs(scanId, { limit: 1000 }),
  });

  const logs: ScanLogEntry[] = data?.logs ?? [];

  const filteredLogs = useMemo(() => {
    let list = logs;
    if (logFilter) {
      const q = logFilter.toLowerCase();
      list = list.filter(
        (l: ScanLogEntry) => l.message?.toLowerCase().includes(q) || l.component?.toLowerCase().includes(q),
      );
    }
    if (typeFilter) {
      list = list.filter((l: ScanLogEntry) => l.type === typeFilter);
    }
    return list;
  }, [logs, logFilter, typeFilter]);

  const logTypes = [...new Set(logs.map((l: ScanLogEntry) => l.type).filter(Boolean))];

  const downloadLogs = async () => {
    try {
      const resp = await scanApi.exportLogs(scanId);
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${scanId}-logs.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex gap-3 items-center flex-1">
          <SearchInput value={logFilter} onChange={setLogFilter} placeholder="Filter log messages..." className="flex-1 max-w-md" />
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="input-field w-auto min-w-[120px] text-sm">
            <option value="">All Types</option>
            {logTypes.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <button className="btn-secondary text-sm" onClick={downloadLogs}>
          <Download className="h-3.5 w-3.5" /> Export Logs
        </button>
      </div>

      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="p-6"><TableSkeleton rows={10} cols={4} /></div>
        ) : filteredLogs.length > 0 ? (
          <div className="overflow-x-auto max-h-[600px]">
            <table className="w-full">
              <thead className="sticky top-0 bg-dark-800 z-10">
                <tr className="border-b border-dark-700/60">
                  <th className="table-header w-40">Time</th>
                  <th className="table-header w-28">Type</th>
                  <th className="table-header w-36">Component</th>
                  <th className="table-header">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700/30 font-mono text-xs">
                {filteredLogs.map((log: ScanLogEntry, i: number) => (
                  <tr key={log.rowid ?? i} className="table-row">
                    <td className="table-cell text-dark-500 whitespace-nowrap">{formatEpoch(log.generated)}</td>
                    <td className="table-cell">
                      <span className={`badge text-[10px] ${
                        log.type === 'ERROR' ? 'badge-critical'
                          : log.type === 'WARNING' ? 'badge-medium'
                          : 'badge-info'
                      }`}>
                        {log.type}
                      </span>
                    </td>
                    <td className="table-cell text-dark-400">{log.component?.replace('sfp_', '')}</td>
                    <td className="table-cell text-dark-200 break-all">{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8">
            <EmptyState
              icon={ScrollText}
              title="No log entries"
              description={logFilter || typeFilter ? 'Try adjusting your filters.' : 'Log entries will appear as the scan runs.'}
            />
          </div>
        )}
      </div>
      <p className="text-xs text-dark-600">Showing {filteredLogs.length} of {logs.length} entries</p>
    </div>
  );
}

/* ── Mini Stat Helper ─────────────────────────────────────── */
function MiniStat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="card-hover text-center py-4">
      <p className="text-xl font-bold text-white">{value}</p>
      <p className="text-xs text-dark-400 mt-1">{label}</p>
    </div>
  );
}
