import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scheduleApi } from '../lib/api';
import { Calendar, Play, Trash2, ToggleLeft, ToggleRight } from 'lucide-react';
import { useState } from 'react';

export default function SchedulesPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const { data: schedules, isLoading } = useQuery({
    queryKey: ['schedules'],
    queryFn: scheduleApi.list,
  });

  const triggerSchedule = useMutation({
    mutationFn: (id: string) => scheduleApi.trigger(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schedules'] }),
  });

  const deleteSchedule = useMutation({
    mutationFn: (id: string) => scheduleApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schedules'] }),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Schedules</h1>
        <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <Calendar className="h-4 w-4 inline mr-2" />
          New Schedule
        </button>
      </div>

      {showCreate && <CreateScheduleForm onClose={() => setShowCreate(false)} />}

      <div className="card">
        {isLoading ? (
          <p className="text-dark-400">Loading schedules...</p>
        ) : schedules && schedules.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-dark-400 border-b border-dark-700">
                  <th className="pb-3 font-medium">Name</th>
                  <th className="pb-3 font-medium">Target</th>
                  <th className="pb-3 font-medium">Interval</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Runs</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700">
                {schedules.map((sched) => (
                  <tr key={sched.id} className="hover:bg-dark-700/50">
                    <td className="py-3 text-white">{sched.name}</td>
                    <td className="py-3 text-dark-300">{sched.target}</td>
                    <td className="py-3 text-dark-300">{sched.interval_hours}h</td>
                    <td className="py-3">
                      {sched.enabled ? (
                        <span className="badge badge-success flex items-center gap-1 w-fit">
                          <ToggleRight className="h-3 w-3" /> Active
                        </span>
                      ) : (
                        <span className="badge badge-low flex items-center gap-1 w-fit">
                          <ToggleLeft className="h-3 w-3" /> Paused
                        </span>
                      )}
                    </td>
                    <td className="py-3 text-dark-300">
                      {sched.run_count ?? 0}
                      {sched.max_runs ? ` / ${sched.max_runs}` : ''}
                    </td>
                    <td className="py-3 flex gap-2">
                      <button
                        className="text-spider-400 hover:text-spider-300"
                        onClick={() => triggerSchedule.mutate(sched.id)}
                        title="Trigger now"
                      >
                        <Play className="h-4 w-4" />
                      </button>
                      <button
                        className="text-red-400 hover:text-red-300"
                        onClick={() => deleteSchedule.mutate(sched.id)}
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-dark-400">No schedules configured.</p>
        )}
      </div>
    </div>
  );
}

function CreateScheduleForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [target, setTarget] = useState('');
  const [interval, setInterval] = useState(24);

  const create = useMutation({
    mutationFn: (payload: { name: string; target: string; interval_hours: number }) =>
      scheduleApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      onClose();
    },
  });

  return (
    <div className="card mb-4 border border-spider-600">
      <h3 className="text-white font-semibold mb-3">Create Schedule</h3>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate({ name, target, interval_hours: interval });
        }}
      >
        <input
          className="input-field"
          placeholder="Schedule name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          className="input-field"
          placeholder="Target (e.g. example.com)"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          required
        />
        <div>
          <label className="text-sm text-dark-300">Interval (hours)</label>
          <input
            type="number"
            className="input-field"
            min={1}
            value={interval}
            onChange={(e) => setInterval(Number(e.target.value))}
          />
        </div>
        <div className="flex gap-2">
          <button type="submit" className="btn-primary" disabled={create.isPending}>
            {create.isPending ? 'Creating...' : 'Create'}
          </button>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
