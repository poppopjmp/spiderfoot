import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import {
  scanApi, formatEpoch, formatDuration, SCAN_STATUSES,
  type Scan,
} from '../lib/api';
import {
  Radar, PlusCircle, StopCircle, Trash2, RotateCcw, Copy as CopyIcon,
  Download, ChevronLeft, ChevronRight, MoreVertical, Eye, ClipboardCopy,
  Activity, CheckCircle, XCircle,
} from 'lucide-react';
import {
  PageHeader, StatCard, SearchInput, StatusBadge, CopyButton,
  EmptyState, TableSkeleton, ConfirmDialog, Toast, DropdownMenu, DropdownItem,
  type ToastType,
} from '../components/ui';

const PAGE_SIZE = 20;

export default function ScansPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<{ type: ToastType; message: string } | null>(null);
  const [confirm, setConfirm] = useState<{
    title: string; message: string; action: () => void; danger?: boolean;
  } | null>(null);

  /* Server-side search when query is present */
  const { data: searchData, isLoading: searchLoading } = useQuery({
    queryKey: ['scans-search', search, statusFilter],
    queryFn: () => scanApi.search({
      target: search || undefined,
      status: statusFilter || undefined,
      sort_by: 'created',
      sort_order: 'desc',
      limit: 200,
    }),
    enabled: !!(search || statusFilter),
    refetchInterval: 10_000,
  });

  /* Normal paginated list when no filters */
  const { data: listData, isLoading: listLoading } = useQuery({
    queryKey: ['scans', { page, page_size: PAGE_SIZE, sort_by: 'created', sort_order: 'desc' }],
    queryFn: () => scanApi.list({ page, page_size: PAGE_SIZE, sort_by: 'created', sort_order: 'desc' }),
    enabled: !search && !statusFilter,
    refetchInterval: 10_000,
  });

  const isSearchMode = !!(search || statusFilter);
  const isLoading = isSearchMode ? searchLoading : listLoading;

  const scans = isSearchMode ? (searchData?.scans ?? []) : (listData?.items ?? []);
  const totalPages = isSearchMode ? 1 : (listData?.pages ?? 1);
  const totalCount = isSearchMode ? (searchData?.total ?? scans.length) : (listData?.total ?? 0);

  /* No further client-side filtering needed — server handles it */
  const filteredScans = scans;

  /* Mutations */
  const stopMut = useMutation({
    mutationFn: scanApi.stop,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      setToast({ type: 'success', message: 'Scan stopped' });
    },
    onError: (err: Error) => {
      setToast({ type: 'error', message: 'Failed to stop scan' });
    },
  });
  const deleteMut = useMutation({
    mutationFn: scanApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      queryClient.invalidateQueries({ queryKey: ['scan-stats-all'] });
      setToast({ type: 'success', message: 'Scan deleted' });
    },
    onError: (err: Error) => {
      setToast({ type: 'error', message: err.message || 'Delete failed' });
    },
  });
  const rerunMut = useMutation({
    mutationFn: scanApi.rerun,
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      setToast({ type: 'success', message: `Rerun started: ${r?.new_scan_id?.slice(0, 8)}` });
    },
    onError: (err: Error) => {
      setToast({ type: 'error', message: 'Failed to rerun scan' });
    },
  });
  const cloneMut = useMutation({
    mutationFn: scanApi.clone,
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      setToast({ type: 'success', message: `Cloned: ${r?.new_scan_id?.slice(0, 8)}` });
    },
    onError: (err: Error) => {
      setToast({ type: 'error', message: 'Failed to clone scan' });
    },
  });
  const bulkStopMut = useMutation({
    mutationFn: (ids: string[]) => scanApi.bulkStop(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      setSelected(new Set());
      setToast({ type: 'success', message: 'Bulk stop complete' });
    },
    onError: (err: Error) => {
      setToast({ type: 'error', message: 'Bulk stop failed' });
    },
  });
  const bulkDeleteMut = useMutation({
    mutationFn: (ids: string[]) => scanApi.bulkDelete(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      setSelected(new Set());
      setToast({ type: 'success', message: 'Bulk delete complete' });
    },
    onError: (err: Error) => {
      setToast({ type: 'error', message: 'Bulk delete failed' });
    },
  });

  /* Selection helpers */
  const toggleSelect = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) { next.delete(id); } else { next.add(id); }
    setSelected(next);
  };
  const toggleAll = () => {
    if (selected.size === filteredScans.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filteredScans.map((s: Scan) => s.scan_id)));
    }
  };

  const isRunning = (s: Scan) => ['RUNNING', 'STARTING'].includes(s.status?.toUpperCase());

  /* Status stats across all scans */
  const { data: statsData } = useQuery({
    queryKey: ['scan-stats-all'],
    queryFn: () => scanApi.search({ limit: 1, offset: 0 }),
    refetchInterval: 15_000,
  });
  const facets = statsData?.facets?.status ?? {};
  const runningCount = (facets['RUNNING'] ?? 0) + (facets['STARTING'] ?? 0);
  const finishedCount = facets['FINISHED'] ?? 0;
  const failedCount = (facets['ERROR-FAILED'] ?? 0) + (facets['ABORTED'] ?? 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Scans" subtitle={`${totalCount} scans total`}>
        <Link to="/scans/new" className="btn-primary">
          <PlusCircle className="h-4 w-4" /> New Scan
        </Link>
      </PageHeader>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Total Scans" value={totalCount} icon={Radar} color="text-spider-400" loading={isLoading} delay={0} />
        <StatCard label="Running" value={runningCount} icon={Activity} color="status-text-running" loading={isLoading} delay={60} />
        <StatCard label="Completed" value={finishedCount} icon={CheckCircle} color="status-text-finished" loading={isLoading} delay={120} />
        <StatCard label="Failed" value={failedCount} icon={XCircle} color="status-text-failed" loading={isLoading} delay={180} />
      </div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex gap-3 items-center flex-1 w-full sm:w-auto">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by name, target, or ID..."
            className="flex-1 max-w-md"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field w-auto min-w-[140px] text-sm"
          >
            <option value="">All Statuses</option>
            {SCAN_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        {/* Bulk actions */}
        {selected.size > 0 && (
          <div className="flex gap-2 items-center animate-fade-in">
            <span className="text-xs text-dark-400">{selected.size} selected</span>
            <button
              className="btn-secondary text-xs"
              onClick={() => setConfirm({
                title: 'Stop Selected Scans',
                message: `Stop ${selected.size} scan(s)?`,
                action: () => { bulkStopMut.mutate([...selected]); setConfirm(null); },
              })}
            >
              <StopCircle className="h-3 w-3" /> Stop
            </button>
            <button
              className="btn-danger text-xs"
              onClick={() => setConfirm({
                title: 'Delete Selected Scans',
                message: `Permanently delete ${selected.size} scan(s)? This cannot be undone.`,
                action: () => { bulkDeleteMut.mutate([...selected]); setConfirm(null); },
                danger: true,
              })}
            >
              <Trash2 className="h-3 w-3" /> Delete
            </button>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="card overflow-visible">
        {isLoading ? (
          <TableSkeleton rows={8} cols={7} />
        ) : filteredScans.length > 0 ? (
          <div className="overflow-x-auto overflow-y-visible -mx-6 px-6">
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-700/60">
                  <th className="table-header w-10">
                    <input
                      type="checkbox"
                      checked={selected.size === filteredScans.length && filteredScans.length > 0}
                      onChange={toggleAll}
                      className="rounded border-dark-600 bg-dark-700 text-spider-500 focus:ring-spider-500/30"
                    />
                  </th>
                  <th className="table-header">Name</th>
                  <th className="table-header">Target</th>
                  <th className="table-header">Status</th>
                  <th className="table-header">Elements</th>
                  <th className="table-header">Started</th>
                  <th className="table-header">Duration</th>
                  <th className="table-header text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700/30">
                {filteredScans.map((scan: Scan, i: number) => (
                  <tr
                    key={scan.scan_id}
                    className="table-row animate-fade-in group"
                    style={{ animationDelay: `${i * 25}ms` }}
                  >
                    <td className="table-cell">
                      <input
                        type="checkbox"
                        checked={selected.has(scan.scan_id)}
                        onChange={() => toggleSelect(scan.scan_id)}
                        className="rounded border-dark-600 bg-dark-700 text-spider-500 focus:ring-spider-500/30"
                      />
                    </td>
                    <td className="table-cell">
                      <Link
                        to={`/scans/${scan.scan_id}`}
                        className="text-spider-400 hover:text-spider-300 font-medium hover:underline decoration-spider-600/50 underline-offset-2"
                      >
                        {scan.name || 'Untitled Scan'}
                      </Link>
                    </td>
                    <td className="table-cell">
                      <span className="flex items-center gap-1.5 text-dark-300 font-mono text-xs">
                        {scan.target}
                        <CopyButton text={scan.scan_id} className="opacity-0 group-hover:opacity-100" />
                      </span>
                    </td>
                    <td className="table-cell"><StatusBadge status={scan.status} /></td>
                    <td className="table-cell text-dark-400 text-xs tabular-nums">{scan.result_count ?? '—'}</td>
                    <td className="table-cell text-dark-400 text-xs whitespace-nowrap">{formatEpoch(scan.started)}</td>
                    <td className="table-cell text-dark-400 text-xs whitespace-nowrap">{formatDuration(scan.started, scan.ended)}</td>
                    <td className="table-cell">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => navigate(`/scans/${scan.scan_id}`)}
                          className="btn-icon text-dark-400 hover:text-spider-400"
                          title="View scan details"
                        >
                          <Eye className="h-4 w-4" />
                        </button>
                        {isRunning(scan) ? (
                          <button
                            onClick={() => stopMut.mutate(scan.scan_id)}
                            className="btn-icon text-dark-400 hover:text-red-400"
                            title="Stop scan"
                          >
                            <StopCircle className="h-4 w-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => rerunMut.mutate(scan.scan_id)}
                            className="btn-icon text-dark-400 hover:text-green-400"
                            title="Rerun scan"
                          >
                            <RotateCcw className="h-4 w-4" />
                          </button>
                        )}
                        <button
                          onClick={() => setConfirm({
                            title: 'Delete Scan',
                            message: `Delete "${scan.name || scan.target}"? This cannot be undone.`,
                            action: () => { deleteMut.mutate(scan.scan_id); setConfirm(null); },
                            danger: true,
                          })}
                          className="btn-icon text-dark-400 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                          title="Delete scan"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                        <DropdownMenu
                          trigger={<button className="btn-icon text-dark-400 hover:text-dark-200"><MoreVertical className="h-4 w-4" /></button>}
                        >
                          <DropdownItem icon={ClipboardCopy} onClick={() => {
                            navigator.clipboard.writeText(scan.scan_id);
                            setToast({ type: 'info', message: 'Scan ID copied' });
                          }}>Copy ID</DropdownItem>
                          <DropdownItem icon={CopyIcon} onClick={() => cloneMut.mutate(scan.scan_id)}>Clone</DropdownItem>
                          <DropdownItem
                            icon={Download}
                            onClick={() => {
                              scanApi.exportEvents(scan.scan_id, { filetype: 'csv' }).then((r) => {
                                const blob = r.data as Blob;
                                if (!blob || blob.size === 0) {
                                  setToast({ type: 'error', message: 'Export returned empty data' });
                                  return;
                                }
                                const url = URL.createObjectURL(blob);
                                const a = document.createElement('a');
                                a.href = url;
                                a.download = `${scan.name || scan.scan_id}.csv`;
                                document.body.appendChild(a);
                                a.click();
                                document.body.removeChild(a);
                                URL.revokeObjectURL(url);
                                setToast({ type: 'success', message: 'CSV exported' });
                              }).catch(() => {
                                setToast({ type: 'error', message: 'CSV export failed' });
                              });
                            }}
                          >Export CSV</DropdownItem>
                          <DropdownItem
                            icon={Trash2}
                            danger
                            onClick={() => setConfirm({
                              title: 'Delete Scan',
                              message: `Delete "${scan.name || scan.target}"? This cannot be undone.`,
                              action: () => { deleteMut.mutate(scan.scan_id); setConfirm(null); },
                              danger: true,
                            })}
                          >Delete</DropdownItem>
                        </DropdownMenu>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div>
            <EmptyState
              icon={Radar}
              title="No scans found"
              description={search || statusFilter
                ? 'Try adjusting your search or filter criteria.'
                : 'Create your first scan to begin gathering OSINT data.'}
              action={!search && !statusFilter ? (
                <Link to="/scans/new" className="btn-primary"><PlusCircle className="h-4 w-4" /> New Scan</Link>
              ) : undefined}
            />
          </div>
        )}
      </div>

      {/* Pagination */}
      {!isSearchMode && totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-dark-500">
            Page {page} of {totalPages} ({totalCount} total)
          </p>
          <div className="flex gap-2">
            <button
              className="btn-secondary text-sm"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" /> Previous
            </button>
            <button
              className="btn-secondary text-sm"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Next <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Dialogs */}
      {confirm && (
        <ConfirmDialog
          open
          title={confirm.title}
          message={confirm.message}
          danger={confirm.danger}
          confirmLabel={confirm.danger ? 'Delete' : 'Confirm'}
          onConfirm={confirm.action}
          onCancel={() => setConfirm(null)}
        />
      )}
      {toast && <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} />}
    </div>
  );
}
