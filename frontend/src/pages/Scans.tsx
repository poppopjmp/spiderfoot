import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { useState, useMemo } from 'react';
import {
  scanApi, formatEpoch, formatDuration, statusBadgeClass, SCAN_STATUSES,
  type Scan,
} from '../lib/api';
import {
  Radar, PlusCircle, Search, StopCircle, Trash2, RotateCcw,
  ChevronLeft, ChevronRight, Eye, Filter,
} from 'lucide-react';

export default function ScansPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const page = Number(searchParams.get('page') ?? '1');
  const pageSize = 25;
  const statusFilter = searchParams.get('status') ?? '';
  const [targetFilter, setTargetFilter] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const { data, isLoading, error } = useQuery({
    queryKey: ['scans', { page, page_size: pageSize, sort_by: 'created', sort_order: 'desc' }],
    queryFn: () => scanApi.list({ page, page_size: pageSize, sort_by: 'created', sort_order: 'desc' }),
    refetchInterval: 10000,
  });

  const scans = data?.data ?? [];
  const pagination = data?.pagination;

  // Client-side filters on current page
  const filtered = useMemo(() => {
    let result = scans;
    if (statusFilter) result = result.filter((s: Scan) => s.status?.toUpperCase() === statusFilter);
    if (targetFilter) {
      const q = targetFilter.toLowerCase();
      result = result.filter((s: Scan) =>
        s.target?.toLowerCase().includes(q) || s.name?.toLowerCase().includes(q),
      );
    }
    return result;
  }, [scans, statusFilter, targetFilter]);

  const stopScan = useMutation({
    mutationFn: scanApi.stop,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scans'] }),
  });

  const deleteScan = useMutation({
    mutationFn: scanApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      setSelected((prev) => { const next = new Set(prev); return next; });
    },
  });

  const rerunScan = useMutation({
    mutationFn: scanApi.rerun,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scans'] }),
  });

  const bulkDelete = useMutation({
    mutationFn: (ids: string[]) => scanApi.bulkDelete(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      setSelected(new Set());
    },
  });

  const bulkStop = useMutation({
    mutationFn: (ids: string[]) => scanApi.bulkStop(ids),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scans'] }),
  });

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === filtered.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filtered.map((s: Scan) => s.scan_id)));
    }
  };

  const setPage = (p: number) => {
    searchParams.set('page', String(p));
    setSearchParams(searchParams);
  };

  const setStatus = (s: string) => {
    if (s) searchParams.set('status', s); else searchParams.delete('status');
    searchParams.set('page', '1');
    setSearchParams(searchParams);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Scans</h1>
        <Link to="/scans/new" className="btn-primary flex items-center gap-2">
          <PlusCircle className="h-4 w-4" /> New Scan
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-400" />
          <input
            className="input-field pl-10"
            placeholder="Search by name or target..."
            value={targetFilter}
            onChange={(e) => setTargetFilter(e.target.value)}
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-400" />
          <select
            className="input-field pl-10 pr-8 appearance-none cursor-pointer"
            value={statusFilter}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            {SCAN_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-4 p-3 bg-dark-800 rounded-lg border border-dark-600">
          <span className="text-sm text-dark-300">{selected.size} selected</span>
          <button
            className="btn-secondary text-xs py-1 flex items-center gap-1"
            onClick={() => bulkStop.mutate(Array.from(selected))}
          >
            <StopCircle className="h-3 w-3" /> Stop
          </button>
          <button
            className="btn-danger text-xs py-1 flex items-center gap-1"
            onClick={() => {
              if (confirm(`Delete ${selected.size} scans?`)) {
                bulkDelete.mutate(Array.from(selected));
              }
            }}
          >
            <Trash2 className="h-3 w-3" /> Delete
          </button>
        </div>
      )}

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <div className="animate-spin h-6 w-6 border-2 border-spider-500 border-t-transparent rounded-full" />
          </div>
        ) : error ? (
          <div className="p-6 text-center text-red-400">
            Failed to load scans. Is the API server running?
          </div>
        ) : filtered.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-dark-400 border-b border-dark-700 bg-dark-800/50">
                  <th className="p-3 w-8">
                    <input
                      type="checkbox"
                      checked={selected.size === filtered.length && filtered.length > 0}
                      onChange={toggleAll}
                      className="rounded bg-dark-700 border-dark-500"
                    />
                  </th>
                  <th className="p-3 font-medium">Name</th>
                  <th className="p-3 font-medium">Target</th>
                  <th className="p-3 font-medium">Status</th>
                  <th className="p-3 font-medium">Started</th>
                  <th className="p-3 font-medium">Duration</th>
                  <th className="p-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700/50">
                {filtered.map((scan: Scan) => {
                  const isRunning = ['RUNNING', 'STARTING'].includes(scan.status?.toUpperCase());
                  const isDone = ['FINISHED', 'ABORTED', 'ERROR-FAILED', 'STOPPED'].includes(scan.status?.toUpperCase());
                  return (
                    <tr key={scan.scan_id} className="hover:bg-dark-700/30">
                      <td className="p-3">
                        <input
                          type="checkbox"
                          checked={selected.has(scan.scan_id)}
                          onChange={() => toggleSelect(scan.scan_id)}
                          className="rounded bg-dark-700 border-dark-500"
                        />
                      </td>
                      <td className="p-3">
                        <Link
                          to={`/scans/${scan.scan_id}`}
                          className="text-spider-400 hover:text-spider-300 font-medium"
                        >
                          {scan.name}
                        </Link>
                      </td>
                      <td className="p-3 text-dark-200 font-mono text-xs">{scan.target}</td>
                      <td className="p-3">
                        <span className={statusBadgeClass(scan.status)}>{scan.status}</span>
                      </td>
                      <td className="p-3 text-dark-300 text-xs whitespace-nowrap">
                        {formatEpoch(scan.started)}
                      </td>
                      <td className="p-3 text-dark-300 text-xs whitespace-nowrap">
                        {formatDuration(scan.started, scan.ended)}
                      </td>
                      <td className="p-3">
                        <div className="flex items-center justify-end gap-2">
                          <Link
                            to={`/scans/${scan.scan_id}`}
                            className="text-dark-400 hover:text-spider-400"
                            title="View"
                          >
                            <Eye className="h-4 w-4" />
                          </Link>
                          {isRunning && (
                            <button
                              className="text-dark-400 hover:text-yellow-400"
                              title="Stop"
                              onClick={() => stopScan.mutate(scan.scan_id)}
                            >
                              <StopCircle className="h-4 w-4" />
                            </button>
                          )}
                          {isDone && (
                            <button
                              className="text-dark-400 hover:text-blue-400"
                              title="Rerun"
                              onClick={() => rerunScan.mutate(scan.scan_id)}
                            >
                              <RotateCcw className="h-4 w-4" />
                            </button>
                          )}
                          <button
                            className="text-dark-400 hover:text-red-400"
                            title="Delete"
                            onClick={() => {
                              if (confirm(`Delete scan "${scan.name}"?`)) {
                                deleteScan.mutate(scan.scan_id);
                              }
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center text-dark-400">
            <Radar className="h-12 w-12 mx-auto mb-3 opacity-30" />
            <p>No scans found{statusFilter ? ` with status "${statusFilter}"` : ''}.</p>
          </div>
        )}

        {/* Pagination */}
        {pagination && pagination.total_pages > 1 && (
          <div className="flex items-center justify-between p-4 border-t border-dark-700">
            <span className="text-sm text-dark-400">
              Page {pagination.page} of {pagination.total_pages} ({pagination.total} total)
            </span>
            <div className="flex gap-2">
              <button
                className="btn-secondary text-xs py-1"
                disabled={pagination.page <= 1}
                onClick={() => setPage(pagination.page - 1)}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                className="btn-secondary text-xs py-1"
                disabled={pagination.page >= pagination.total_pages}
                onClick={() => setPage(pagination.page + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
