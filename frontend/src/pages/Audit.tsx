import { useQuery } from '@tanstack/react-query';
import { auditApi } from '../lib/api';
import { FileText, Filter, BarChart3 } from 'lucide-react';
import { useState } from 'react';

export default function AuditPage() {
  const [actionFilter, setActionFilter] = useState('');
  const { data: logs, isLoading } = useQuery({
    queryKey: ['audit-logs', actionFilter],
    queryFn: () => auditApi.list({ limit: 100, action: actionFilter || undefined }),
  });
  const { data: stats } = useQuery({ queryKey: ['audit-stats'], queryFn: auditApi.stats });

  const entries = logs?.logs ?? logs?.entries ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Audit Log</h1>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total Events', value: stats.total ?? 0, color: 'text-spider-400' },
            { label: 'Today', value: stats.today ?? 0, color: 'text-blue-400' },
            { label: 'Unique Users', value: stats.unique_users ?? 0, color: 'text-purple-400' },
            { label: 'Failed Actions', value: stats.failed ?? 0, color: 'text-red-400' },
          ].map((s) => (
            <div key={s.label} className="card flex items-center gap-3">
              <BarChart3 className={`h-5 w-5 ${s.color}`} />
              <div>
                <p className="text-sm text-dark-400">{s.label}</p>
                <p className="text-xl font-bold text-white">{s.value}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-3 mb-4">
        <Filter className="h-4 w-4 text-dark-400" />
        <select
          className="input-field w-48"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
        >
          <option value="">All Actions</option>
          <option value="scan.create">Scan Create</option>
          <option value="scan.delete">Scan Delete</option>
          <option value="config.update">Config Update</option>
          <option value="api_key.create">API Key Create</option>
          <option value="rbac.assign">Role Assignment</option>
          <option value="login">Login</option>
          <option value="export">Export</option>
        </select>
      </div>

      {/* Log entries */}
      <div className="card">
        {isLoading ? (
          <p className="text-dark-400">Loading audit log...</p>
        ) : entries.length > 0 ? (
          <div className="space-y-2">
            {entries.map((entry: { id: string; action: string; user: string; timestamp: string; details?: string; success?: boolean }, i: number) => (
              <div
                key={entry.id || i}
                className="flex items-center justify-between p-3 bg-dark-700/50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <FileText className="h-4 w-4 text-dark-400" />
                  <div>
                    <p className="text-sm text-white">
                      <span className="badge badge-info mr-2">{entry.action}</span>
                      {entry.details || ''}
                    </p>
                    <p className="text-xs text-dark-400">
                      {entry.user} · {entry.timestamp}
                    </p>
                  </div>
                </div>
                <span className={`badge ${entry.success !== false ? 'badge-success' : 'badge-critical'}`}>
                  {entry.success !== false ? 'OK' : 'FAILED'}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-dark-400">No audit log entries found.</p>
        )}
      </div>
    </div>
  );
}
