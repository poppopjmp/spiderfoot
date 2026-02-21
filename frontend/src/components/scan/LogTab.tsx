import { memo, useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { scanApi, formatEpoch, type ScanLogEntry } from '../../lib/api';
import { ScrollText, Download } from 'lucide-react';
import { SearchInput, EmptyState, TableSkeleton } from '../ui';

function LogTab({ scanId }: { scanId: string }) {
  const [logFilter, setLogFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['scan-logs', scanId],
    queryFn: ({ signal }) => scanApi.logs(scanId, { limit: 1000 }, signal),
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
    } catch (e) {
      console.error('Log export failed:', e);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex gap-3 items-center flex-1">
          <SearchInput value={logFilter} onChange={setLogFilter} placeholder="Filter log messages..." className="flex-1 max-w-md" debounceMs={250} />
          <select aria-label="Filter by log type" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="input-field w-auto min-w-[120px] text-sm">
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

export default memo(LogTab);
