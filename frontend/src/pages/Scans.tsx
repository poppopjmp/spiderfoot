import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { scanApi } from '../lib/api';
import { Plus, Search } from 'lucide-react';
import { useState } from 'react';

export default function ScansPage() {
  const [search, setSearch] = useState('');
  const { data: scans, isLoading } = useQuery({
    queryKey: ['scans'],
    queryFn: scanApi.list,
  });

  const filtered = scans?.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.target.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Scans</h1>
        <Link to="/scans/new" className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> New Scan
        </Link>
      </div>

      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-400" />
        <input
          type="text"
          placeholder="Search scans..."
          className="input-field pl-10"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="card">
        {isLoading ? (
          <p className="text-dark-400">Loading scans...</p>
        ) : filtered && filtered.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-dark-400 border-b border-dark-700">
                  <th className="pb-3 font-medium">Name</th>
                  <th className="pb-3 font-medium">Target</th>
                  <th className="pb-3 font-medium">Engine</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Events</th>
                  <th className="pb-3 font-medium">Started</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700">
                {filtered.map((scan) => (
                  <tr key={scan.id} className="hover:bg-dark-700/50">
                    <td className="py-3">
                      <Link to={`/scans/${scan.id}`} className="text-spider-400 hover:underline">
                        {scan.name}
                      </Link>
                    </td>
                    <td className="py-3 text-dark-300">{scan.target}</td>
                    <td className="py-3 text-dark-300">{scan.engine || '—'}</td>
                    <td className="py-3">
                      <StatusBadge status={scan.status} />
                    </td>
                    <td className="py-3 text-dark-300">{scan.event_count}</td>
                    <td className="py-3 text-dark-400">{scan.started}</td>
                    <td className="py-3">
                      <Link
                        to={`/scans/${scan.id}`}
                        className="text-sm text-spider-400 hover:text-spider-300"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-dark-400">No scans found.</p>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    RUNNING: 'badge-success',
    FINISHED: 'badge-info',
    ABORTED: 'badge-high',
    FAILED: 'badge-critical',
    STARTING: 'badge-low',
  };
  return <span className={`badge ${map[status] || 'badge-info'}`}>{status}</span>;
}
