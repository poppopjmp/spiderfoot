import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useState } from 'react';
import {
  scanApi, formatEpoch, formatDuration, statusBadgeClass,
  type Scan, type EventSummaryDetail, type ScanEvent, type ScanCorrelation, type ScanLogEntry,
} from '../lib/api';
import {
  ArrowLeft, StopCircle, RotateCcw, Trash2, Download,
  FileText, AlertTriangle, Shield, ScrollText, Clock,
  ChevronRight, ExternalLink, Copy, CheckCircle, XCircle,
} from 'lucide-react';

type Tab = 'overview' | 'events' | 'correlations' | 'logs';

export default function ScanDetailPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>('overview');
  const [selectedEventType, setSelectedEventType] = useState<string | null>(null);
  const [logOffset, setLogOffset] = useState(0);

  // Scan info
  const { data: scan, isLoading, error } = useQuery({
    queryKey: ['scan', scanId],
    queryFn: () => scanApi.get(scanId!),
    enabled: !!scanId,
    refetchInterval: (query) => {
      const s = query.state.data as Scan | undefined;
      return s && ['RUNNING', 'STARTING', 'CREATED'].includes(s.status?.toUpperCase()) ? 5000 : false;
    },
  });

  // Summary (event types)
  const { data: summaryData } = useQuery({
    queryKey: ['scan-summary', scanId],
    queryFn: () => scanApi.summary(scanId!, 'type'),
    enabled: !!scanId && (tab === 'overview' || tab === 'events'),
  });

  // Events for selected type
  const { data: eventsData, isLoading: eventsLoading } = useQuery({
    queryKey: ['scan-events', scanId, selectedEventType],
    queryFn: () => scanApi.events(scanId!, { event_type: selectedEventType! }),
    enabled: !!scanId && !!selectedEventType,
  });

  // Correlations
  const { data: corrData } = useQuery({
    queryKey: ['scan-correlations', scanId],
    queryFn: () => scanApi.correlations(scanId!),
    enabled: !!scanId && tab === 'correlations',
  });

  // Logs
  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ['scan-logs', scanId, logOffset],
    queryFn: () => scanApi.logs(scanId!, { limit: 100, offset: logOffset }),
    enabled: !!scanId && tab === 'logs',
  });

  // Mutations
  const stopScan = useMutation({
    mutationFn: () => scanApi.stop(scanId!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scan', scanId] }),
  });

  const rerunScan = useMutation({
    mutationFn: () => scanApi.rerun(scanId!),
    onSuccess: (data) => navigate(`/scans/${data.new_scan_id}`),
  });

  const deleteScan = useMutation({
    mutationFn: () => scanApi.delete(scanId!),
    onSuccess: () => navigate('/scans'),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-2 border-spider-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error || !scan) {
    return (
      <div className="text-center py-16">
        <XCircle className="h-12 w-12 mx-auto text-red-400 mb-3" />
        <p className="text-red-400">Failed to load scan.</p>
        <Link to="/scans" className="text-spider-400 hover:underline text-sm mt-2 inline-block">
          Back to scans
        </Link>
      </div>
    );
  }

  const isRunning = ['RUNNING', 'STARTING'].includes(scan.status?.toUpperCase());
  const isDone = ['FINISHED', 'ABORTED', 'ERROR-FAILED', 'STOPPED'].includes(scan.status?.toUpperCase());
  const summaryDetails = summaryData?.details ?? [];
  const totalTypes = summaryData?.total_types ?? 0;

  const tabs: { key: Tab; label: string; icon: typeof FileText; count?: number }[] = [
    { key: 'overview', label: 'Overview', icon: FileText },
    { key: 'events', label: 'Results', icon: Shield, count: totalTypes },
    { key: 'correlations', label: 'Correlations', icon: AlertTriangle, count: corrData?.total },
    { key: 'logs', label: 'Logs', icon: ScrollText, count: logsData?.total },
  ];

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <Link to="/scans" className="text-dark-400 hover:text-dark-200 text-sm flex items-center gap-1 mb-2">
            <ArrowLeft className="h-3 w-3" /> Back to Scans
          </Link>
          <h1 className="text-2xl font-bold text-white">{scan.name}</h1>
          <div className="flex items-center gap-3 mt-2">
            <span className={statusBadgeClass(scan.status)}>{scan.status}</span>
            <span className="text-dark-400 font-mono text-sm">{scan.target}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isRunning && (
            <button
              className="btn-secondary flex items-center gap-2"
              onClick={() => stopScan.mutate()}
              disabled={stopScan.isPending}
            >
              <StopCircle className="h-4 w-4" /> Stop
            </button>
          )}
          {isDone && (
            <button
              className="btn-secondary flex items-center gap-2"
              onClick={() => rerunScan.mutate()}
              disabled={rerunScan.isPending}
            >
              <RotateCcw className="h-4 w-4" /> Rerun
            </button>
          )}
          <button
            className="btn-danger flex items-center gap-2"
            onClick={() => {
              if (confirm('Delete this scan and all its data?')) deleteScan.mutate();
            }}
          >
            <Trash2 className="h-4 w-4" /> Delete
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-dark-800 rounded-lg p-1 w-fit">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setSelectedEventType(null); }}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              tab === t.key
                ? 'bg-spider-600 text-white'
                : 'text-dark-300 hover:text-white hover:bg-dark-700'
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
            {t.count != null && t.count > 0 && (
              <span className="text-xs bg-dark-600 px-1.5 py-0.5 rounded-full">{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'overview' && <OverviewTab scan={scan} summaryDetails={summaryDetails} />}
      {tab === 'events' && (
        <EventsTab
          scanId={scanId!}
          summaryDetails={summaryDetails}
          selectedEventType={selectedEventType}
          onSelectEventType={setSelectedEventType}
          events={eventsData?.events ?? []}
          eventsTotal={eventsData?.total ?? 0}
          loading={eventsLoading}
        />
      )}
      {tab === 'correlations' && (
        <CorrelationsTab
          scanId={scanId!}
          correlations={corrData?.correlations ?? []}
          total={corrData?.total ?? 0}
        />
      )}
      {tab === 'logs' && (
        <LogsTab
          logs={logsData?.logs ?? []}
          total={logsData?.total ?? 0}
          offset={logOffset}
          onOffsetChange={setLogOffset}
          loading={logsLoading}
          scanId={scanId!}
        />
      )}
    </div>
  );
}

/* ── Overview Tab ──────────────────────────────────────────── */
function OverviewTab({ scan, summaryDetails }: { scan: Scan; summaryDetails: EventSummaryDetail[] }) {
  const totalEvents = summaryDetails.reduce((sum, d) => sum + d.total, 0);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Scan Info */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">Scan Information</h3>
        <dl className="space-y-3 text-sm">
          {[
            ['Scan ID', scan.scan_id],
            ['Name', scan.name],
            ['Target', scan.target],
            ['Status', scan.status],
            ['Created', formatEpoch(scan.created)],
            ['Started', formatEpoch(scan.started)],
            ['Ended', formatEpoch(scan.ended)],
            ['Duration', formatDuration(scan.started, scan.ended)],
          ].map(([label, value]) => (
            <div key={label} className="flex items-start justify-between">
              <dt className="text-dark-400">{label}</dt>
              <dd className="text-white text-right font-mono text-xs max-w-[60%] break-all">{value}</dd>
            </div>
          ))}
        </dl>
      </div>

      {/* Event Summary */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">
          Results Summary ({totalEvents.toLocaleString()} events)
        </h3>

        {summaryDetails.length > 0 ? (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {summaryDetails
              .sort((a, b) => b.total - a.total)
              .map((detail) => (
                <div
                  key={detail.key}
                  className="flex items-center justify-between p-2 rounded hover:bg-dark-700/50"
                >
                  <span className="text-sm text-dark-200">{detail.key}</span>
                  <span className="text-sm font-mono text-spider-400">{detail.total}</span>
                </div>
              ))}
          </div>
        ) : (
          <p className="text-dark-400 text-sm">No event data available yet.</p>
        )}
      </div>
    </div>
  );
}

/* ── Events Tab ────────────────────────────────────────────── */
function EventsTab({
  scanId,
  summaryDetails,
  selectedEventType,
  onSelectEventType,
  events,
  eventsTotal,
  loading,
}: {
  scanId: string;
  summaryDetails: EventSummaryDetail[];
  selectedEventType: string | null;
  onSelectEventType: (t: string | null) => void;
  events: ScanEvent[];
  eventsTotal: number;
  loading: boolean;
}) {
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const copyToClipboard = (text: string, hash: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  if (!selectedEventType) {
    // Show event type summary table
    return (
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">
          Event Types ({summaryDetails.length})
        </h3>
        {summaryDetails.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-dark-400 border-b border-dark-700">
                  <th className="pb-3 font-medium">Event Type</th>
                  <th className="pb-3 font-medium text-right">Total</th>
                  <th className="pb-3 font-medium text-right">Unique</th>
                  <th className="pb-3 font-medium text-right">Last Seen</th>
                  <th className="pb-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700/50">
                {summaryDetails
                  .sort((a, b) => b.total - a.total)
                  .map((detail) => (
                    <tr
                      key={detail.key}
                      className="hover:bg-dark-700/30 cursor-pointer"
                      onClick={() => onSelectEventType(detail.key)}
                    >
                      <td className="py-3 text-white">{detail.key}</td>
                      <td className="py-3 text-right font-mono text-spider-400">{detail.total}</td>
                      <td className="py-3 text-right font-mono text-dark-300">{detail.unique_total}</td>
                      <td className="py-3 text-right text-dark-300 text-xs">
                        {detail.last_in ? formatEpoch(detail.last_in) : '\u2014'}
                      </td>
                      <td className="py-3 text-right">
                        <ChevronRight className="h-4 w-4 text-dark-400" />
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-dark-400">No results yet.</p>
        )}
      </div>
    );
  }

  // Show events for selected type
  return (
    <div>
      <button
        onClick={() => onSelectEventType(null)}
        className="text-spider-400 hover:text-spider-300 text-sm flex items-center gap-1 mb-4"
      >
        <ArrowLeft className="h-3 w-3" /> Back to event types
      </button>

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">
            {selectedEventType} ({eventsTotal})
          </h3>
          <a
            href={`/api/scans/${scanId}/events/export?event_type=${encodeURIComponent(selectedEventType)}&filetype=csv`}
            className="btn-secondary text-xs flex items-center gap-1"
            download
          >
            <Download className="h-3 w-3" /> Export CSV
          </a>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin h-6 w-6 border-2 border-spider-500 border-t-transparent rounded-full" />
          </div>
        ) : events.length > 0 ? (
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {events.map((evt, i) => (
              <div
                key={evt.hash || i}
                className="p-3 bg-dark-700/30 rounded-lg border border-dark-700/50 hover:border-dark-600"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <pre className="text-sm text-white whitespace-pre-wrap break-all font-mono bg-dark-900/50 rounded p-2 max-h-40 overflow-auto">
                      {evt.data}
                    </pre>
                    <div className="flex items-center gap-4 mt-2 text-xs text-dark-400">
                      <span>Module: <span className="text-dark-300">{evt.module}</span></span>
                      <span>Confidence: <span className="text-dark-300">{evt.confidence}%</span></span>
                      {evt.risk > 0 && (
                        <span>Risk: <span className={`font-medium ${
                          evt.risk >= 70 ? 'text-red-400' : evt.risk >= 40 ? 'text-yellow-400' : 'text-blue-400'
                        }`}>{evt.risk}</span></span>
                      )}
                      <span>{formatEpoch(evt.generated)}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => copyToClipboard(evt.data, evt.hash)}
                    className="text-dark-400 hover:text-white flex-shrink-0"
                    title="Copy data"
                  >
                    {copiedHash === evt.hash ? (
                      <CheckCircle className="h-4 w-4 text-green-400" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-dark-400">No events found.</p>
        )}
      </div>
    </div>
  );
}

/* ── Correlations Tab ──────────────────────────────────────── */
function CorrelationsTab({
  scanId,
  correlations,
  total,
}: {
  scanId: string;
  correlations: ScanCorrelation[];
  total: number;
}) {
  const queryClient = useQueryClient();

  const runCorrelations = useMutation({
    mutationFn: () => scanApi.runCorrelations(scanId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scan-correlations', scanId] }),
  });

  const riskColor = (risk: string) => {
    switch (risk?.toLowerCase()) {
      case 'high': case 'critical': return 'badge-critical';
      case 'medium': return 'badge-medium';
      case 'low': return 'badge-low';
      default: return 'badge-info';
    }
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">
          Correlations ({total})
        </h3>
        <button
          className="btn-secondary text-sm flex items-center gap-2"
          onClick={() => runCorrelations.mutate()}
          disabled={runCorrelations.isPending}
        >
          <Shield className="h-4 w-4" />
          {runCorrelations.isPending ? 'Running...' : 'Run Correlations'}
        </button>
      </div>

      {correlations.length > 0 ? (
        <div className="space-y-3">
          {correlations.map((corr) => (
            <div
              key={corr.id}
              className="p-4 bg-dark-700/30 rounded-lg border border-dark-700/50"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`badge ${riskColor(corr.rule_risk)}`}>
                      {corr.rule_risk}
                    </span>
                    <h4 className="text-white font-medium">{corr.rule_name || corr.title}</h4>
                  </div>
                  <p className="text-sm text-dark-300">{corr.rule_descr}</p>
                </div>
                <span className="text-xs text-dark-400 whitespace-nowrap">
                  {corr.event_count} event{corr.event_count !== 1 ? 's' : ''}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-dark-400">
          <Shield className="h-10 w-10 mx-auto mb-2 opacity-30" />
          <p>No correlations found.</p>
          <p className="text-xs mt-1">Click "Run Correlations" to analyze scan results against correlation rules.</p>
        </div>
      )}
    </div>
  );
}

/* ── Logs Tab ──────────────────────────────────────────────── */
function LogsTab({
  logs,
  total,
  offset,
  onOffsetChange,
  loading,
  scanId,
}: {
  logs: ScanLogEntry[];
  total: number;
  offset: number;
  onOffsetChange: (o: number) => void;
  loading: boolean;
  scanId: string;
}) {
  const logTypeColor = (type: string) => {
    switch (type?.toUpperCase()) {
      case 'ERROR': case 'CRITICAL': return 'text-red-400';
      case 'WARNING': return 'text-yellow-400';
      case 'DEBUG': return 'text-dark-500';
      default: return 'text-dark-300';
    }
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">
          Logs ({total})
        </h3>
        <a
          href={`/api/scans/${scanId}/logs/export`}
          className="btn-secondary text-xs flex items-center gap-1"
          download
        >
          <Download className="h-3 w-3" /> Export
        </a>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin h-6 w-6 border-2 border-spider-500 border-t-transparent rounded-full" />
        </div>
      ) : logs.length > 0 ? (
        <>
          <div className="bg-dark-900 rounded-lg p-3 font-mono text-xs max-h-[500px] overflow-auto">
            {logs.map((log) => (
              <div key={log.rowid} className="flex gap-3 py-1 hover:bg-dark-800/50">
                <span className="text-dark-500 whitespace-nowrap flex-shrink-0">
                  {formatEpoch(log.generated)}
                </span>
                <span className={`w-16 flex-shrink-0 uppercase font-medium ${logTypeColor(log.type)}`}>
                  {log.type}
                </span>
                <span className="text-dark-400 w-32 flex-shrink-0 truncate">{log.component}</span>
                <span className="text-dark-200 break-all">{log.message}</span>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {total > 100 && (
            <div className="flex items-center justify-between mt-4">
              <span className="text-sm text-dark-400">
                Showing {offset + 1}-{Math.min(offset + 100, total)} of {total}
              </span>
              <div className="flex gap-2">
                <button
                  className="btn-secondary text-xs py-1"
                  disabled={offset === 0}
                  onClick={() => onOffsetChange(Math.max(0, offset - 100))}
                >
                  Previous
                </button>
                <button
                  className="btn-secondary text-xs py-1"
                  disabled={offset + 100 >= total}
                  onClick={() => onOffsetChange(offset + 100)}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <p className="text-dark-400">No logs available.</p>
      )}
    </div>
  );
}
