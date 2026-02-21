/**
 * Schedules page — manage recurring scan schedules.
 *
 * Full CRUD backed by /api/schedules endpoints.
 * Supports create, edit, toggle, delete, and manual trigger.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import {
  scheduleApi, formatEpoch,
  type Schedule, type ScheduleCreate,
} from '../lib/api';
import {
  Clock, PlusCircle, Play, Pause, Trash2, Zap,
  RotateCcw, Edit3, Calendar,
} from 'lucide-react';
import {
  PageHeader, EmptyState, TableSkeleton, StatusBadge,
  ConfirmDialog, Toast, ModalShell, Tooltip,
  type ToastType,
} from '../components/ui';

export default function SchedulesPage() {
  useDocumentTitle('Schedules');
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<{ type: ToastType; message: string } | null>(null);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['schedules'],
    queryFn: ({ signal }) => scheduleApi.list(signal),
  });

  const schedules = data?.schedules ?? [];

  const createMut = useMutation({
    mutationFn: (data: ScheduleCreate) => scheduleApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      setCreating(false);
      setToast({ type: 'success', message: 'Schedule created' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to create schedule' }),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ScheduleCreate> }) =>
      scheduleApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      setEditing(null);
      setToast({ type: 'success', message: 'Schedule updated' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to update schedule' }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => scheduleApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      setDeleting(null);
      setToast({ type: 'success', message: 'Schedule deleted' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to delete schedule' }),
  });

  const triggerMut = useMutation({
    mutationFn: (id: string) => scheduleApi.trigger(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      setToast({ type: 'success', message: 'Schedule triggered — scan started' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to trigger schedule' }),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      scheduleApi.update(id, { enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schedules'] }),
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Schedules" subtitle="Recurring scan schedules powered by Celery Beat">
        <button className="btn-primary" onClick={() => setCreating(true)}>
          <PlusCircle className="h-4 w-4" /> New Schedule
        </button>
      </PageHeader>

      {isLoading ? (
        <TableSkeleton rows={5} cols={6} />
      ) : schedules.length > 0 ? (
        <div className="card overflow-x-auto animate-fade-in-up">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700/60">
                <th className="table-header">Name</th>
                <th className="table-header">Target</th>
                <th className="table-header">Interval</th>
                <th className="table-header">Status</th>
                <th className="table-header">Last Run</th>
                <th className="table-header">Runs</th>
                <th className="table-header text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-700/30">
              {schedules.map((sched, i) => (
                <tr key={sched.id} className="table-row animate-fade-in" style={{ animationDelay: `${i * 30}ms` }}>
                  <td className="table-cell font-medium text-foreground">{sched.name}</td>
                  <td className="table-cell text-dark-300 font-mono text-xs">{sched.target}</td>
                  <td className="table-cell text-dark-400 text-xs">
                    <Tooltip content={`Every ${sched.interval_hours}h`}>
                      <span className="flex items-center gap-1">
                        <RotateCcw className="h-3 w-3" />
                        {sched.interval_hours >= 24
                          ? `${Math.round(sched.interval_hours / 24)}d`
                          : `${sched.interval_hours}h`}
                      </span>
                    </Tooltip>
                  </td>
                  <td className="table-cell">
                    <StatusBadge status={sched.enabled ? 'RUNNING' : 'STOPPED'} />
                  </td>
                  <td className="table-cell text-dark-400 text-xs whitespace-nowrap">
                    {sched.last_run_at ? formatEpoch(sched.last_run_at) : '—'}
                  </td>
                  <td className="table-cell text-dark-400 text-xs tabular-nums">
                    {sched.runs_completed}{sched.max_runs > 0 ? ` / ${sched.max_runs}` : ''}
                  </td>
                  <td className="table-cell text-right">
                    <div className="flex items-center gap-1 justify-end">
                      <Tooltip content={sched.enabled ? 'Pause' : 'Resume'}>
                        <button
                          className="btn-icon"
                          onClick={() => toggleMut.mutate({ id: sched.id, enabled: !sched.enabled })}
                        >
                          {sched.enabled ?
                            <Pause className="h-3.5 w-3.5" /> :
                            <Play className="h-3.5 w-3.5" />
                          }
                        </button>
                      </Tooltip>
                      <Tooltip content="Trigger now">
                        <button
                          className="btn-icon"
                          onClick={() => triggerMut.mutate(sched.id)}
                          disabled={triggerMut.isPending}
                        >
                          <Zap className="h-3.5 w-3.5" />
                        </button>
                      </Tooltip>
                      <Tooltip content="Edit">
                        <button className="btn-icon" onClick={() => setEditing(sched)}>
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                      </Tooltip>
                      <Tooltip content="Delete">
                        <button
                          className="btn-icon text-red-400 hover:text-red-300"
                          onClick={() => setDeleting(sched.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </Tooltip>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          icon={Calendar}
          title="No schedules"
          description="Create a recurring scan schedule to automatically monitor targets."
          action={
            <button className="btn-primary" onClick={() => setCreating(true)}>
              <PlusCircle className="h-4 w-4" /> Create Schedule
            </button>
          }
        />
      )}

      {/* Create/Edit Modal */}
      {(creating || editing) && (
        <ScheduleFormModal
          schedule={editing ?? undefined}
          onSubmit={(data) => {
            if (editing) {
              updateMut.mutate({ id: editing.id, data });
            } else {
              createMut.mutate(data);
            }
          }}
          onClose={() => { setCreating(false); setEditing(null); }}
          isPending={createMut.isPending || updateMut.isPending}
        />
      )}

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleting}
        title="Delete Schedule"
        message="This will permanently delete this schedule. Existing scan results will not be affected."
        confirmLabel="Delete"
        danger
        onConfirm={() => deleting && deleteMut.mutate(deleting)}
        onCancel={() => setDeleting(null)}
      />

      {toast && <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} />}
    </div>
  );
}

/* ── Schedule Form Modal ──────────────────────────────────── */
function ScheduleFormModal({
  schedule, onSubmit, onClose, isPending,
}: {
  schedule?: Schedule;
  onSubmit: (data: ScheduleCreate) => void;
  onClose: () => void;
  isPending: boolean;
}) {
  const [name, setName] = useState(schedule?.name ?? '');
  const [target, setTarget] = useState(schedule?.target ?? '');
  const [intervalHours, setIntervalHours] = useState(schedule?.interval_hours ?? 24);
  const [enabled, setEnabled] = useState(schedule?.enabled ?? true);
  const [description, setDescription] = useState(schedule?.description ?? '');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      name: name.trim(),
      target: target.trim(),
      interval_hours: intervalHours,
      enabled,
      description: description.trim(),
    });
  };

  return (
    <ModalShell title={schedule ? 'Edit Schedule' : 'Create Schedule'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Name</label>
          <input
            className="input w-full"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Weekly domain scan"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Target</label>
          <input
            className="input w-full"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="example.com"
            required
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">Interval (hours)</label>
            <input
              type="number"
              className="input w-full"
              value={intervalHours}
              onChange={(e) => setIntervalHours(Number(e.target.value))}
              min={0.25}
              max={8760}
              step={0.25}
            />
          </div>
          <div className="flex items-end pb-1">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="rounded border-dark-600 bg-dark-700 text-spider-500 focus:ring-spider-600"
              />
              <span className="text-sm text-dark-300">Enabled</span>
            </label>
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Description</label>
          <textarea
            className="input w-full"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="Optional description..."
          />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={isPending || !name.trim() || !target.trim()}>
            <Clock className="h-4 w-4" />
            {isPending ? 'Saving...' : schedule ? 'Update' : 'Create'}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
