import { useQuery } from '@tanstack/react-query';
import { scanApi, healthApi } from '../lib/api';
import { Activity, Radar, ShieldAlert, Clock } from 'lucide-react';

function StatCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  color: string;
}) {
  return (
    <div className="card flex items-center gap-4">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon className="h-6 w-6" />
      </div>
      <div>
        <p className="text-sm text-dark-400">{title}</p>
        <p className="text-2xl font-bold text-white">{value}</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: scans } = useQuery({
    queryKey: ['scans'],
    queryFn: scanApi.list,
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: healthApi.check,
  });

  const runningScans = scans?.filter((s) => s.status === 'RUNNING').length ?? 0;
  const totalScans = scans?.length ?? 0;
  const completedScans = scans?.filter((s) => s.status === 'FINISHED').length ?? 0;
  const totalFindings = scans?.reduce((sum, s) => sum + (s.event_count || 0), 0) ?? 0;

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Dashboard</h1>

      {/* Stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          title="Running Scans"
          value={runningScans}
          icon={Activity}
          color="bg-spider-600/20 text-spider-400"
        />
        <StatCard
          title="Total Scans"
          value={totalScans}
          icon={Radar}
          color="bg-blue-600/20 text-blue-400"
        />
        <StatCard
          title="Completed"
          value={completedScans}
          icon={Clock}
          color="bg-purple-600/20 text-purple-400"
        />
        <StatCard
          title="Total Findings"
          value={totalFindings.toLocaleString()}
          icon={ShieldAlert}
          color="bg-orange-600/20 text-orange-400"
        />
      </div>

      {/* Recent scans */}
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-4">Recent Scans</h2>
        {scans && scans.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-dark-400 border-b border-dark-700">
                  <th className="pb-3 font-medium">Name</th>
                  <th className="pb-3 font-medium">Target</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Events</th>
                  <th className="pb-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700">
                {scans.slice(0, 10).map((scan) => (
                  <tr key={scan.id} className="hover:bg-dark-700/50">
                    <td className="py-3 text-white">{scan.name}</td>
                    <td className="py-3 text-dark-300">{scan.target}</td>
                    <td className="py-3">
                      <ScanStatus status={scan.status} />
                    </td>
                    <td className="py-3 text-dark-300">{scan.event_count}</td>
                    <td className="py-3 text-dark-400">{scan.started}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-dark-400">No scans yet. Start your first scan!</p>
        )}
      </div>

      {/* System health */}
      {health && (
        <div className="card mt-6">
          <h2 className="text-lg font-semibold text-white mb-2">System Health</h2>
          <p className="text-dark-300">
            Status:{' '}
            <span className={health.status === 'ok' ? 'text-green-400' : 'text-red-400'}>
              {health.status}
            </span>
          </p>
        </div>
      )}
    </div>
  );
}

function ScanStatus({ status }: { status: string }) {
  const styles: Record<string, string> = {
    RUNNING: 'badge-success',
    FINISHED: 'badge-info',
    ABORTED: 'badge-high',
    FAILED: 'badge-critical',
    'STARTING': 'badge-low',
  };
  return <span className={`badge ${styles[status] || 'badge-info'}`}>{status}</span>;
}
