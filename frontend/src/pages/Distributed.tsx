import { useQuery } from '@tanstack/react-query';
import { distributedApi } from '../lib/api';
import { Server, Activity, Wifi, WifiOff, BarChart3 } from 'lucide-react';

export default function DistributedPage() {
  const { data: workers } = useQuery({ queryKey: ['dist-workers'], queryFn: distributedApi.listWorkers });
  const { data: poolStats } = useQuery({ queryKey: ['dist-pool'], queryFn: distributedApi.poolStats });
  const { data: strategies } = useQuery({ queryKey: ['dist-strategies'], queryFn: distributedApi.strategies });

  const workerList = workers?.workers ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Distributed Scanning</h1>

      {/* Pool stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Workers', value: poolStats?.total_workers ?? workerList.length, icon: Server, color: 'text-spider-400' },
          { label: 'Healthy', value: poolStats?.healthy ?? 0, icon: Wifi, color: 'text-green-400' },
          { label: 'Unhealthy', value: poolStats?.unhealthy ?? 0, icon: WifiOff, color: 'text-red-400' },
          { label: 'Active Chunks', value: poolStats?.active_chunks ?? 0, icon: Activity, color: 'text-blue-400' },
        ].map((s) => (
          <div key={s.label} className="card flex items-center gap-3">
            <s.icon className={`h-5 w-5 ${s.color}`} />
            <div>
              <p className="text-sm text-dark-400">{s.label}</p>
              <p className="text-xl font-bold text-white">{s.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Balancing strategies */}
      {strategies?.strategies && (
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-white mb-3">Load Balancing Strategies</h2>
          <div className="flex flex-wrap gap-2">
            {(strategies.strategies as { name: string; description: string }[]).map((s) => (
              <div key={s.name} className="p-3 bg-dark-700/50 rounded-lg">
                <p className="text-white font-medium text-sm">{s.name}</p>
                <p className="text-xs text-dark-400">{s.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Workers */}
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-4">Worker Nodes</h2>
        {workerList.length > 0 ? (
          <div className="space-y-3">
            {workerList.map((w: { id: string; hostname: string; status: string; capabilities: string[]; active_chunks: number; max_concurrent: number; last_heartbeat?: string }) => (
              <div key={w.id} className="flex items-center justify-between p-4 bg-dark-700/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <Server className={`h-5 w-5 ${w.status === 'healthy' ? 'text-green-400' : 'text-red-400'}`} />
                  <div>
                    <p className="text-white font-medium">{w.hostname}</p>
                    <div className="flex gap-1 mt-1">
                      {w.capabilities?.map((c) => (
                        <span key={c} className="badge badge-info text-xs">{c}</span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-dark-300">{w.active_chunks}/{w.max_concurrent} chunks</span>
                  <span className={`badge ${w.status === 'healthy' ? 'badge-success' : 'badge-critical'}`}>
                    {w.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <Server className="h-12 w-12 text-dark-600 mx-auto mb-3" />
            <p className="text-dark-400">No worker nodes registered.</p>
            <p className="text-sm text-dark-500 mt-1">
              Workers auto-register when they come online. Deploy workers with the distributed scanning configuration.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
