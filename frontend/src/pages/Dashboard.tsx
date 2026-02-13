import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  scanApi, healthApi, formatEpoch, formatDuration,
  type Scan,
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
    queryFn: () => scanApi.list({ page: 1, page_size: 10, sort_by: 'created', sort_order: 'desc' }),
    refetchInterval: 15_000,
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: healthApi.check,
    retry: false,
    refetchInterval: 30_000,
  });

  const scans = scanData?.data ?? [];
  const total = scanData?.pagination?.total ?? 0;
  const running = scans.filter((s: Scan) => ['RUNNING', 'STARTING'].includes(s.status?.toUpperCase())).length;
  const finished = scans.filter((s: Scan) => s.status?.toUpperCase() === 'FINISHED').length;
  const failed = scans.filter((s: Scan) => s.status?.toUpperCase() === 'ERROR-FAILED').length;

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
        <StatCard label="Running" value={running} icon={Activity} color="text-blue-400" loading={scansLoading} delay={60} />
        <StatCard label="Completed" value={finished} icon={CheckCircle} color="text-green-400" loading={scansLoading} delay={120} />
        <StatCard label="Failed" value={failed} icon={XCircle} color="text-red-400" loading={scansLoading} delay={180} />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Scans */}
        <div className="lg:col-span-2 card animate-fade-in-up" style={{ animationDelay: '150ms' }}>
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
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
                        <RiskPills high={scan.risk_high} medium={scan.risk_medium} low={scan.risk_low} info={scan.risk_info} />
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
            <h2 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <Server className="h-4 w-4 text-dark-400" /> System Health
            </h2>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-dark-400 text-sm">Status</span>
                <HealthBadge status={healthStatus} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-dark-400 text-sm">Uptime</span>
                <span className="text-white font-mono text-sm">{uptime}</span>
              </div>
              {health?.components && Object.keys(health.components).length > 0 && (
                <div className="pt-3 border-t border-dark-700/50">
                  <p className="section-label mb-3">Components</p>
                  <div className="space-y-2">
                    {Object.entries(health.components).map(([name, comp]) => (
                      <div key={name} className="flex items-center justify-between text-xs">
                        <span className="text-dark-300 capitalize">{name.replace(/_/g, ' ')}</span>
                        <span className="flex items-center gap-2">
                          <span className={comp.status === 'up' ? 'text-green-400' : comp.status === 'degraded' ? 'text-yellow-400' : 'text-red-400'}>
                            {comp.status}
                          </span>
                          {comp.latency_ms != null && <span className="text-dark-600 tabular-nums">{comp.latency_ms}ms</span>}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="card animate-fade-in-up" style={{ animationDelay: '250ms' }}>
            <h2 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <Zap className="h-4 w-4 text-dark-400" /> Quick Actions
            </h2>
            <div className="space-y-2">
              {[
                { to: '/scans/new', icon: PlusCircle, iconBg: 'bg-spider-600/10 text-spider-400 group-hover:bg-spider-600/20', label: 'New Scan', desc: 'Start a new reconnaissance' },
                { to: '/modules', icon: Shield, iconBg: 'bg-blue-600/10 text-blue-400 group-hover:bg-blue-600/20', label: 'Modules', desc: 'Configure data sources' },
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
    <span className="flex items-center gap-1.5 text-green-400 text-sm font-medium">
      <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" /> Healthy
    </span>
  );
  if (status === 'degraded') return (
    <span className="flex items-center gap-1.5 text-yellow-400 text-sm font-medium">
      <AlertTriangle className="h-3.5 w-3.5" /> Degraded
    </span>
  );
  if (status === 'down') return (
    <span className="flex items-center gap-1.5 text-red-400 text-sm font-medium">
      <XCircle className="h-3.5 w-3.5" /> Down
    </span>
  );
  return (
    <span className="flex items-center gap-1.5 text-dark-500 text-sm">
      <Clock className="h-3.5 w-3.5" /> Unknown
    </span>
  );
}
