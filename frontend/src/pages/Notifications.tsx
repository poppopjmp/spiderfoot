import { useQuery } from '@tanstack/react-query';
import { notificationApi } from '../lib/api';
import { Bell, Plus, History, BarChart3, Zap, Mail, MessageSquare } from 'lucide-react';
import { useState } from 'react';

export default function NotificationsPage() {
  const [tab, setTab] = useState<'rules' | 'history' | 'stats'>('rules');
  const { data: rules } = useQuery({ queryKey: ['notification-rules'], queryFn: notificationApi.listRules });
  const { data: history } = useQuery({ queryKey: ['notification-history'], queryFn: () => notificationApi.history({ limit: 50 }) });
  const { data: stats } = useQuery({ queryKey: ['notification-stats'], queryFn: notificationApi.stats });
  const { data: channels } = useQuery({ queryKey: ['notification-channels'], queryFn: notificationApi.channels });

  const ruleList = rules?.rules ?? [];
  const historyList = history?.history ?? [];

  const channelIcon = (type: string) => {
    switch (type) {
      case 'email': return <Mail className="h-4 w-4" />;
      case 'slack': case 'discord': case 'teams': return <MessageSquare className="h-4 w-4" />;
      default: return <Zap className="h-4 w-4" />;
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Notification Rules</h1>
        <button className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> Create Rule
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-dark-800 rounded-lg p-1 w-fit">
        {[
          { key: 'rules' as const, label: 'Rules', icon: Bell },
          { key: 'history' as const, label: 'History', icon: History },
          { key: 'stats' as const, label: 'Analytics', icon: BarChart3 },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              tab === t.key ? 'bg-spider-600 text-white' : 'text-dark-300 hover:text-white hover:bg-dark-700'
            }`}
          >
            <t.icon className="h-4 w-4" /> {t.label}
          </button>
        ))}
      </div>

      {/* Rules */}
      {tab === 'rules' && (
        <div className="space-y-3">
          {(ruleList.length > 0 ? ruleList : [
            { id: '1', name: 'Critical Finding Alert', severity: 'critical', enabled: true, channels: [{ type: 'email' }, { type: 'slack' }], conditions: [{ field: 'severity', operator: 'equals', value: 'critical' }] },
            { id: '2', name: 'Scan Completed', severity: 'info', enabled: true, channels: [{ type: 'webhook' }], conditions: [{ field: 'event_type', operator: 'equals', value: 'scan.finished' }] },
            { id: '3', name: 'Data Breach Detected', severity: 'high', enabled: true, channels: [{ type: 'email' }, { type: 'pagerduty' }], conditions: [{ field: 'event_type', operator: 'contains', value: 'breach' }] },
          ]).map((r: { id: string; name: string; severity: string; enabled: boolean; channels: { type: string }[]; conditions: { field: string; operator: string; value: string }[] }) => (
            <div key={r.id} className="card flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`p-2 rounded-lg ${r.enabled ? 'bg-green-600/20' : 'bg-dark-700'}`}>
                  <Bell className={`h-5 w-5 ${r.enabled ? 'text-green-400' : 'text-dark-500'}`} />
                </div>
                <div>
                  <h3 className="font-medium text-white">{r.name}</h3>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`badge ${
                      r.severity === 'critical' ? 'badge-critical' :
                      r.severity === 'high' ? 'badge-high' :
                      r.severity === 'medium' ? 'badge-medium' : 'badge-low'
                    }`}>{r.severity}</span>
                    {r.channels.map((ch, i) => (
                      <span key={i} className="badge badge-info flex items-center gap-1">
                        {channelIcon(ch.type)} {ch.type}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <span className={`badge ${r.enabled ? 'badge-success' : 'badge-info'}`}>
                {r.enabled ? 'Active' : 'Disabled'}
              </span>
            </div>
          ))}

          {/* Available channels */}
          {channels?.channels && (
            <div className="card mt-6">
              <h3 className="text-white font-semibold mb-3">Available Channels</h3>
              <div className="flex flex-wrap gap-2">
                {channels.channels.map((ch: { name: string; description: string }) => (
                  <span key={ch.name} className="badge badge-info">{ch.name}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* History */}
      {tab === 'history' && (
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Notifications</h2>
          {historyList.length > 0 ? (
            <div className="space-y-2">
              {historyList.map((n: { id: string; rule_name: string; channel: string; severity: string; timestamp: string; delivered: boolean }, i: number) => (
                <div key={n.id || i} className="flex items-center justify-between p-3 bg-dark-700/50 rounded-lg text-sm">
                  <div className="flex items-center gap-3">
                    {channelIcon(n.channel)}
                    <span className="text-white">{n.rule_name}</span>
                    <span className={`badge ${n.severity === 'critical' ? 'badge-critical' : n.severity === 'high' ? 'badge-high' : 'badge-info'}`}>{n.severity}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`badge ${n.delivered ? 'badge-success' : 'badge-critical'}`}>
                      {n.delivered ? 'Delivered' : 'Failed'}
                    </span>
                    <span className="text-dark-500 text-xs">{n.timestamp}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-dark-400">No notification history yet.</p>
          )}
        </div>
      )}

      {/* Stats */}
      {tab === 'stats' && stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="card">
            <p className="text-sm text-dark-400">Total Rules</p>
            <p className="text-2xl font-bold text-white">{stats.total_rules ?? 0}</p>
          </div>
          <div className="card">
            <p className="text-sm text-dark-400">Notifications Sent</p>
            <p className="text-2xl font-bold text-white">{stats.total_notifications ?? 0}</p>
          </div>
          <div className="card">
            <p className="text-sm text-dark-400">Active Rules</p>
            <p className="text-2xl font-bold text-green-400">{stats.active_rules ?? 0}</p>
          </div>
          <div className="card">
            <p className="text-sm text-dark-400">Rate Limited</p>
            <p className="text-2xl font-bold text-orange-400">{stats.rate_limited ?? 0}</p>
          </div>
        </div>
      )}
    </div>
  );
}
