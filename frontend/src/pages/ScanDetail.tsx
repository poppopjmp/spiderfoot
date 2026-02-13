import { useState, useMemo, useRef, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  scanApi, formatEpoch, formatDuration,
  type Scan, type ScanEvent, type ScanCorrelation, type ScanLogEntry, type EventSummaryDetail,
} from '../lib/api';
import {
  ArrowLeft, StopCircle, RotateCcw, Download, Share2,
  BarChart3, List, Settings, ScrollText,
  AlertTriangle, Shield, Info, Eye, EyeOff,
  FileText, Network, Loader2, RefreshCw,
} from 'lucide-react';
import {
  Tabs, StatusBadge, RiskPills, CopyButton, SearchInput,
  EmptyState, Skeleton, TableSkeleton, Toast,
  DropdownMenu, DropdownItem, Expandable,
  type ToastType,
} from '../components/ui';

type DetailTab = 'summary' | 'browse' | 'correlations' | 'graph' | 'settings' | 'log';

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
          <RiskPills high={scan.risk_high} medium={scan.risk_medium} low={scan.risk_low} info={scan.risk_info} />
          {scan.element_count != null && (
            <span className="text-sm text-dark-400">{scan.element_count.toLocaleString()} elements</span>
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

  const details: EventSummaryDetail[] = summaryData?.details ?? [];
  const sorted = [...details].sort((a, b) => b.total - a.total);
  const totalEvents = sorted.reduce((sum, d) => sum + d.total, 0);

  /* Simple doughnut - top 8 categories */
  const top8 = sorted.slice(0, 8);
  const colors = [
    '#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6',
    '#8b5cf6', '#ef4444', '#06b6d4',
  ];

  return (
    <div className="space-y-6">
      {/* Stat row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MiniStat label="Data Types" value={summaryData?.total_types ?? 0} />
        <MiniStat label="Total Events" value={totalEvents} />
        <MiniStat label="Unique Values" value={sorted.reduce((s, d) => s + d.unique_total, 0)} />
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
    </div>
  );
}

/* ── Browse Tab ───────────────────────────────────────────── */
function BrowseTab({ scanId }: { scanId: string }) {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewUnique, setViewUnique] = useState(false);
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
    if (!searchQuery) return events;
    const q = searchQuery.toLowerCase();
    return events.filter(
      (e: ScanEvent) => e.data?.toLowerCase().includes(q) || e.module?.toLowerCase().includes(q),
    );
  }, [events, searchQuery]);

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
            ['Elements', scan?.element_count?.toString()],
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
