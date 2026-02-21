import { useQuery, useQueries } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  scanApi, healthApi, formatEpoch, formatDuration,
  type Scan, type HealthComponent,
} from '../lib/api';
import {
  Radar, PlusCircle, Activity, CheckCircle, XCircle, AlertTriangle,
  Clock, ArrowRight, Server, Zap, TrendingUp, Shield,
} from 'lucide-react';
import {
  PageHeader, StatCard, StatusBadge, RiskPills, EmptyState, TableSkeleton,
} from '../components/ui';

export default function DashboardPage() {
  const { data: scanData, isLoading: scansLoading } = useQuery({
    queryKey: ['scans', { page: 1, page_size: 10, sort_by: 'created', sort_order: 'desc' }],
    queryFn: ({ signal }) => scanApi.list({ page: 1, page_size: 10, sort_by: 'created', sort_order: 'desc' }, signal),
    refetchInterval: 15_000,
  });

  // Separate query for accurate status counts across ALL scans
  const { data: searchData } = useQuery({
    queryKey: ['scan-stats'],
    queryFn: ({ signal }) => scanApi.search({ limit: 1, offset: 0 }, signal),
    refetchInterval: 15_000,
  });

  const { data: health } = useQuery({
    queryKey: ['health-dashboard'],
    queryFn: ({ signal }) => healthApi.dashboard(signal),
    retry: 1,
    refetchInterval: 30_000,
  });

  const scans = scanData?.items ?? [];
  const total = scanData?.total ?? 0;

  // Fetch correlation risk summaries for recent scans (parallel, cached)
  const riskQueries = useQueries({
    queries: scans.map((scan: Scan) => ({
      queryKey: ['scan-risk', scan.scan_id],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        scanApi.correlationsSummary(scan.scan_id, 'risk', signal),
      enabled: scan.status === 'FINISHED' || scan.status === 'ERROR-FAILED',
      staleTime: 5 * 60_000, // Risk data rarely changes — cache 5 min
    })),
  });

  // Build a map of scan_id → { high, medium, low, info }
  const riskMap = new Map<string, { high: number; medium: number; low: number; info: number }>();
  scans.forEach((scan: Scan, i: number) => {
    const data = riskQueries[i]?.data;
    if (data?.summary) {
      const counts = { high: 0, medium: 0, low: 0, info: 0 };
      for (const row of data.summary as { risk: string; total: number }[]) {
        const key = row.risk?.toLowerCase();
        if (key === 'high') counts.high = row.total;
        else if (key === 'medium') counts.medium = row.total;
        else if (key === 'low') counts.low = row.total;
        else if (key === 'info' || key === 'informational') counts.info = row.total;
      }
      riskMap.set(scan.scan_id, counts);
    }
  });

  // Use facets from search API for accurate cross-scan status counts
  const facets = searchData?.facets?.status ?? {};
  const running = (facets['RUNNING'] ?? 0) + (facets['STARTING'] ?? 0);
  const finished = facets['FINISHED'] ?? 0;
  const failed = (facets['ERROR-FAILED'] ?? 0) + (facets['ABORTED'] ?? 0);

  const healthStatus = health?.status ?? 'unknown';
  const uptime = health?.uptime_seconds
    ? `${Math.floor(health.uptime_seconds / 3600)}h ${Math.floor((health.uptime_seconds % 3600) / 60)}m`
    : '—';

  return (
    <div className="space-y-8">
      <PageHeader title="Dashboard" subtitle="Your OSINT reconnaissance at a glance">
        <Link to="/scans/new" className="btn-primary">
          <PlusCircle className="h-4 w-4" /> New Scan
        </Link>
      </PageHeader>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Scans" value={total} icon={Radar} color="text-spider-400" loading={scansLoading} delay={0} />
        <StatCard label="Running" value={running} icon={Activity} color="status-text-running" loading={scansLoading} delay={60} />
        <StatCard label="Completed" value={finished} icon={CheckCircle} color="status-text-finished" loading={scansLoading} delay={120} />
        <StatCard label="Failed" value={failed} icon={XCircle} color="status-text-failed" loading={scansLoading} delay={180} />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Scans */}
        <div className="lg:col-span-2 card animate-fade-in-up" style={{ animationDelay: '150ms' }}>
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-dark-400" /> Recent Scans
            </h2>
            <Link to="/scans" className="text-spider-400 hover:text-spider-300 text-sm flex items-center gap-1 group">
              View all <ArrowRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </div>

          {scansLoading ? (
            <TableSkeleton rows={5} cols={5} />
          ) : scans.length > 0 ? (
            <div className="overflow-x-auto -mx-6 px-6">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-dark-700/60">
                    <th className="table-header">Name</th>
                    <th className="table-header">Target</th>
                    <th className="table-header">Status</th>
                    <th className="table-header">Risk</th>
                    <th className="table-header">Started</th>
                    <th className="table-header">Duration</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700/30">
                  {scans.map((scan: Scan, i: number) => (
                    <tr key={scan.scan_id} className="table-row animate-fade-in" style={{ animationDelay: `${i * 40}ms` }}>
                      <td className="table-cell">
                        <Link to={`/scans/${scan.scan_id}`} className="text-spider-400 hover:text-spider-300 font-medium hover:underline decoration-spider-600/50 underline-offset-2">
                          {scan.name || 'Untitled Scan'}
                        </Link>
                      </td>
                      <td className="table-cell text-dark-300 font-mono text-xs">{scan.target}</td>
                      <td className="table-cell"><StatusBadge status={scan.status} /></td>
                      <td className="table-cell">
                        <RiskPills {...(riskMap.get(scan.scan_id) ?? {})} />
                      </td>
                      <td className="table-cell text-dark-400 text-xs whitespace-nowrap">{formatEpoch(scan.started)}</td>
                      <td className="table-cell text-dark-400 text-xs whitespace-nowrap">{formatDuration(scan.started, scan.ended)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              icon={Radar}
              title="No scans yet"
              description="Launch your first OSINT scan to discover intelligence about a target domain, IP, email, or name."
              action={<Link to="/scans/new" className="btn-primary"><Zap className="h-4 w-4" /> Start Your First Scan</Link>}
            />
          )}
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* System Health */}
          <div className="card animate-fade-in-up" style={{ animationDelay: '200ms' }}>
            <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
              <Server className="h-4 w-4 text-dark-400" /> System Health
            </h2>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-dark-400 text-sm">Status</span>
                <HealthBadge status={healthStatus} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-dark-400 text-sm">Uptime</span>
                <span className="text-foreground font-mono text-sm">{uptime}</span>
              </div>
              {/* Always show core component status */}
              <div className="pt-3 border-t border-dark-700/50">
                <p className="section-label mb-3">Components</p>
                <div className="space-y-2">
                  {health?.components && Object.keys(health.components).length > 0 ? (
                    (Object.entries(health.components) as [string, HealthComponent][])
                      .sort(([, a], [, b]) => {
                        // Sort: up first, then degraded, then unknown, then down
                        const order: Record<string, number> = { up: 0, degraded: 1, unknown: 2, down: 3 };
                        return (order[a.status] ?? 2) - (order[b.status] ?? 2);
                      })
                      .map(([name, comp]) => (
                      <div key={name} className="flex items-center justify-between text-xs">
                        <span className="text-dark-300 capitalize">{name.replace(/_/g, ' ')}</span>
                        <span className="flex items-center gap-2">
                          <span className={comp.status === 'up' ? 'health-up' : comp.status === 'degraded' ? 'health-degraded' : comp.status === 'unknown' ? 'health-unknown' : 'health-down'}>
                            {comp.status === 'up' ? 'healthy' : comp.status === 'unknown' ? 'n/a' : comp.status}
                          </span>
                          {comp.latency_ms != null && <span className="text-dark-600 tabular-nums">{comp.latency_ms}ms</span>}
                        </span>
                      </div>
                    ))
                  ) : (
                    <>
                      {['API Server', 'Database', 'Redis', 'Celery Worker'].map((name) => (
                        <div key={name} className="flex items-center justify-between text-xs">
                          <span className="text-dark-300">{name}</span>
                          <span className="text-dark-500">
                            {healthStatus === 'unknown' ? 'checking...' : '—'}
                          </span>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              </div>

              {/* Summary stats from components */}
              {health?.components && (() => {
                const entries = Object.values(health.components) as HealthComponent[];
                const up = entries.filter((c: HealthComponent) => c.status === 'up').length;
                const degraded = entries.filter((c: HealthComponent) => c.status === 'degraded').length;
                const down = entries.filter((c: HealthComponent) => c.status === 'down').length;
                const total = entries.length;
                return (
                  <div className="pt-3 border-t border-dark-700/50">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-dark-400">{total} subsystems</span>
                      <span className="flex items-center gap-3">
                        {up > 0 && <span className="health-up">{up} healthy</span>}
                        {degraded > 0 && <span className="health-degraded">{degraded} degraded</span>}
                        {down > 0 && <span className="health-down">{down} down</span>}
                      </span>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="card animate-fade-in-up" style={{ animationDelay: '250ms' }}>
            <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
              <Zap className="h-4 w-4 text-dark-400" /> Quick Actions
            </h2>
            <div className="space-y-2">
              {[
                { to: '/scans/new', icon: PlusCircle, iconBg: 'bg-spider-600/10 text-spider-400 group-hover:bg-spider-600/20', label: 'New Scan', desc: 'Start a new reconnaissance' },
                { to: '/workspaces', icon: Shield, iconBg: 'bg-blue-600/10 text-blue-400 group-hover:bg-blue-600/20', label: 'Workspaces', desc: 'Manage scan workspaces' },
                { to: '/settings', icon: Clock, iconBg: 'bg-purple-600/10 text-purple-400 group-hover:bg-purple-600/20', label: 'Settings', desc: 'API keys & configuration' },
              ].map((a) => (
                <Link key={a.to} to={a.to} className="flex items-center gap-3 p-3 rounded-lg hover:bg-dark-700/50 transition-colors group">
                  <div className={`p-2 rounded-lg ${a.iconBg} transition-colors`}>
                    <a.icon className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-dark-100">{a.label}</p>
                    <p className="text-xs text-dark-500">{a.desc}</p>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function HealthBadge({ status }: { status: string }) {
  if (status === 'up') return (
    <span className="flex items-center gap-1.5 health-up text-sm font-medium">
      <span className="w-2 h-2 rounded-full health-dot-up animate-pulse" /> Healthy
    </span>
  );
  if (status === 'degraded') return (
    <span className="flex items-center gap-1.5 health-degraded text-sm font-medium">
      <AlertTriangle className="h-3.5 w-3.5" /> Degraded
    </span>
  );
  if (status === 'down') return (
    <span className="flex items-center gap-1.5 health-down text-sm font-medium">
      <XCircle className="h-3.5 w-3.5" /> Down
    </span>
  );
  return (
    <span className="flex items-center gap-1.5 health-unknown text-sm">
      <Clock className="h-3.5 w-3.5" /> Unknown
    </span>
  );
}
