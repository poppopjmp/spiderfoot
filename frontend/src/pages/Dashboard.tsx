import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  scanApi, healthApi, formatEpoch, formatDuration, statusBadgeClass,
  type Scan,
} from '../lib/api';
import {
  Radar, PlusCircle, Activity, CheckCircle, XCircle, AlertTriangle,
  Clock, ArrowRight, Server,
} from 'lucide-react';

export default function DashboardPage() {
  const { data: scanData, isLoading: scansLoading } = useQuery({
    queryKey: ['scans', { page: 1, page_size: 10, sort_by: 'created', sort_order: 'desc' }],
    queryFn: () => scanApi.list({ page: 1, page_size: 10, sort_by: 'created', sort_order: 'desc' }),
    refetchInterval: 15000,
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: healthApi.check,
    retry: false,
    refetchInterval: 30000,
  });

  const scans = scanData?.data ?? [];
  const total = scanData?.pagination?.total ?? 0;

  const running = scans.filter((s: Scan) => ['RUNNING', 'STARTING'].includes(s.status?.toUpperCase())).length;
  const finished = scans.filter((s: Scan) => s.status?.toUpperCase() === 'FINISHED').length;
  const failed = scans.filter((s: Scan) => s.status?.toUpperCase() === 'ERROR-FAILED').length;

  const stats = [
    { label: 'Total Scans', value: total, icon: Radar, color: 'text-spider-400' },
    { label: 'Running', value: running, icon: Activity, color: 'text-blue-400' },
    { label: 'Completed', value: finished, icon: CheckCircle, color: 'text-green-400' },
    { label: 'Failed', value: failed, icon: XCircle, color: 'text-red-400' },
  ];

  const healthStatus = health?.status ?? 'unknown';
  const uptime = health?.uptime_seconds
    ? `${Math.floor(health.uptime_seconds / 3600)}h ${Math.floor((health.uptime_seconds % 3600) / 60)}m`
    : '\u2014';

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-dark-400 mt-1">SpiderFoot OSINT overview</p>
        </div>
        <Link to="/scans/new" className="btn-primary flex items-center gap-2">
          <PlusCircle className="h-4 w-4" /> New Scan
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((s) => (
          <div key={s.label} className="card flex items-center gap-4">
            <div className={`p-3 rounded-lg bg-dark-700/70 ${s.color}`}>
              <s.icon className="h-6 w-6" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{scansLoading ? '\u2014' : s.value}</p>
              <p className="text-sm text-dark-400">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Scans */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Recent Scans</h2>
            <Link to="/scans" className="text-spider-400 hover:text-spider-300 text-sm flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          {scansLoading ? (
            <div className="flex items-center justify-center h-40">
              <div className="animate-spin h-6 w-6 border-2 border-spider-500 border-t-transparent rounded-full" />
            </div>
          ) : scans.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-dark-400 border-b border-dark-700">
                    <th className="pb-3 font-medium">Name</th>
                    <th className="pb-3 font-medium">Target</th>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium">Started</th>
                    <th className="pb-3 font-medium">Duration</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700/50">
                  {scans.map((scan: Scan) => (
                    <tr key={scan.scan_id} className="hover:bg-dark-700/30">
                      <td className="py-3">
                        <Link
                          to={`/scans/${scan.scan_id}`}
                          className="text-spider-400 hover:text-spider-300 font-medium"
                        >
                          {scan.name}
                        </Link>
                      </td>
                      <td className="py-3 text-dark-200 font-mono text-xs">{scan.target}</td>
                      <td className="py-3">
                        <span className={statusBadgeClass(scan.status)}>{scan.status}</span>
                      </td>
                      <td className="py-3 text-dark-300 text-xs">{formatEpoch(scan.started)}</td>
                      <td className="py-3 text-dark-300 text-xs">
                        {formatDuration(scan.started, scan.ended)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-12 text-dark-400">
              <Radar className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p>No scans yet.</p>
              <Link to="/scans/new" className="text-spider-400 hover:underline text-sm mt-2 inline-block">
                Start your first scan
              </Link>
            </div>
          )}
        </div>

        {/* System Health */}
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Server className="h-5 w-5 text-dark-400" /> System Health
          </h2>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-dark-300">Status</span>
              <span className={`font-semibold ${
                healthStatus === 'up' ? 'text-green-400'
                  : healthStatus === 'degraded' ? 'text-yellow-400'
                    : healthStatus === 'down' ? 'text-red-400'
                      : 'text-dark-400'
              }`}>
                {healthStatus === 'up' ? (
                  <span className="flex items-center gap-1"><CheckCircle className="h-4 w-4" /> Healthy</span>
                ) : healthStatus === 'degraded' ? (
                  <span className="flex items-center gap-1"><AlertTriangle className="h-4 w-4" /> Degraded</span>
                ) : healthStatus === 'down' ? (
                  <span className="flex items-center gap-1"><XCircle className="h-4 w-4" /> Down</span>
                ) : (
                  <span className="flex items-center gap-1"><Clock className="h-4 w-4" /> Unknown</span>
                )}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-dark-300">Uptime</span>
              <span className="text-white font-mono text-sm">{uptime}</span>
            </div>

            {health?.components && (
              <div className="pt-3 border-t border-dark-700">
                <p className="text-xs text-dark-400 uppercase tracking-wider mb-2">Components</p>
                <div className="space-y-2">
                  {Object.entries(health.components).map(([name, comp]) => (
                    <div key={name} className="flex items-center justify-between text-sm">
                      <span className="text-dark-300 capitalize">{name.replace(/_/g, ' ')}</span>
                      <span className={`text-xs font-medium ${
                        comp.status === 'up' ? 'text-green-400'
                          : comp.status === 'degraded' ? 'text-yellow-400'
                            : 'text-red-400'
                      }`}>
                        {comp.status}
                        {comp.latency_ms != null && (
                          <span className="text-dark-500 ml-1">({comp.latency_ms}ms)</span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
