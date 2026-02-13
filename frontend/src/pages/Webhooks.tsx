import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { webhookApi } from '../lib/api';
import { Webhook, Plus, Trash2, Send, CheckCircle, XCircle } from 'lucide-react';
import { useState } from 'react';

export default function WebhooksPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [url, setUrl] = useState('');
  const [events, setEvents] = useState('');

  const { data, isLoading } = useQuery({ queryKey: ['webhooks'], queryFn: webhookApi.list });
  const { data: deliveries } = useQuery({ queryKey: ['webhook-deliveries'], queryFn: webhookApi.deliveryHistory });

  const createWebhook = useMutation({
    mutationFn: () => webhookApi.create({ url, events: events.split(',').map(e => e.trim()) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      setShowCreate(false);
      setUrl('');
      setEvents('');
    },
  });

  const testWebhook = useMutation({
    mutationFn: (id: string) => webhookApi.test(id),
  });

  const deleteWebhook = useMutation({
    mutationFn: (id: string) => webhookApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['webhooks'] }),
  });

  const webhooks = data?.webhooks ?? [];
  const history = deliveries?.history ?? deliveries?.deliveries ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Webhooks</h1>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> Add Webhook
        </button>
      </div>

      {showCreate && (
        <div className="card mb-4 border border-spider-600">
          <h3 className="text-white font-semibold mb-3">Create Webhook</h3>
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); createWebhook.mutate(); }}>
            <input className="input-field" placeholder="https://example.com/webhook" value={url} onChange={(e) => setUrl(e.target.value)} required />
            <input className="input-field" placeholder="Events: scan.started, scan.finished, finding.critical" value={events} onChange={(e) => setEvents(e.target.value)} />
            <div className="flex gap-2">
              <button type="submit" className="btn-primary" disabled={createWebhook.isPending}>Create</button>
              <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Active webhooks */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Active Webhooks</h2>
        {isLoading ? (
          <p className="text-dark-400">Loading...</p>
        ) : webhooks.length > 0 ? (
          <div className="space-y-3">
            {webhooks.map((w: { id: string; url: string; events: string[]; enabled: boolean }) => (
              <div key={w.id} className="flex items-center justify-between p-4 bg-dark-700/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <Webhook className="h-5 w-5 text-spider-400" />
                  <div>
                    <p className="text-white font-medium text-sm font-mono">{w.url}</p>
                    <div className="flex gap-1 mt-1">
                      {w.events?.map((e) => (
                        <span key={e} className="badge badge-info text-xs">{e}</span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button className="text-spider-400 hover:text-spider-300" onClick={() => testWebhook.mutate(w.id)} title="Test">
                    <Send className="h-4 w-4" />
                  </button>
                  <button className="text-red-400 hover:text-red-300" onClick={() => deleteWebhook.mutate(w.id)} title="Delete">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-dark-400">No webhooks configured.</p>
        )}
      </div>

      {/* Delivery history */}
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-4">Delivery History</h2>
        {history.length > 0 ? (
          <div className="space-y-2">
            {history.slice(0, 20).map((d: { id: string; url: string; status: number; event: string; timestamp: string }, i: number) => (
              <div key={d.id || i} className="flex items-center justify-between p-3 bg-dark-700/30 rounded-lg text-sm">
                <div className="flex items-center gap-2">
                  {d.status >= 200 && d.status < 300 ? (
                    <CheckCircle className="h-4 w-4 text-green-400" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-400" />
                  )}
                  <span className="text-white">{d.event}</span>
                  <span className="text-dark-400">→</span>
                  <span className="text-dark-300 font-mono text-xs">{d.url}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`badge ${d.status >= 200 && d.status < 300 ? 'badge-success' : 'badge-critical'}`}>
                    {d.status}
                  </span>
                  <span className="text-dark-500 text-xs">{d.timestamp}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-dark-400">No webhook deliveries yet.</p>
        )}
      </div>
    </div>
  );
}
