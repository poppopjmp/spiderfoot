import { useQuery } from '@tanstack/react-query';
import { ssoApi } from '../lib/api';
import { Lock, Plus, Users, Key, Trash2, Shield } from 'lucide-react';
import { useState } from 'react';

export default function SSOPage() {
  const [tab, setTab] = useState<'providers' | 'sessions'>('providers');
  const { data: providers } = useQuery({ queryKey: ['sso-providers'], queryFn: ssoApi.listProviders });
  const { data: sessions } = useQuery({ queryKey: ['sso-sessions'], queryFn: ssoApi.sessions });
  const { data: stats } = useQuery({ queryKey: ['sso-stats'], queryFn: ssoApi.stats });

  const providerList = providers?.providers ?? [];
  const sessionList = sessions?.sessions ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Single Sign-On (SSO)</h1>
        <button className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> Add Provider
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="card flex items-center gap-3">
            <Shield className="h-5 w-5 text-spider-400" />
            <div>
              <p className="text-sm text-dark-400">Providers</p>
              <p className="text-xl font-bold text-white">{stats.total_providers ?? providerList.length}</p>
            </div>
          </div>
          <div className="card flex items-center gap-3">
            <Users className="h-5 w-5 text-blue-400" />
            <div>
              <p className="text-sm text-dark-400">Active Sessions</p>
              <p className="text-xl font-bold text-white">{stats.active_sessions ?? sessionList.length}</p>
            </div>
          </div>
          <div className="card flex items-center gap-3">
            <Key className="h-5 w-5 text-green-400" />
            <div>
              <p className="text-sm text-dark-400">JIT Provisioned</p>
              <p className="text-xl font-bold text-white">{stats.jit_provisioned ?? 0}</p>
            </div>
          </div>
          <div className="card flex items-center gap-3">
            <Lock className="h-5 w-5 text-purple-400" />
            <div>
              <p className="text-sm text-dark-400">SSO Logins (24h)</p>
              <p className="text-xl font-bold text-white">{stats.logins_24h ?? 0}</p>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-dark-800 rounded-lg p-1 w-fit">
        <button
          onClick={() => setTab('providers')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            tab === 'providers' ? 'bg-spider-600 text-white' : 'text-dark-300 hover:text-white hover:bg-dark-700'
          }`}
        >
          <Shield className="h-4 w-4" /> Identity Providers
        </button>
        <button
          onClick={() => setTab('sessions')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            tab === 'sessions' ? 'bg-spider-600 text-white' : 'text-dark-300 hover:text-white hover:bg-dark-700'
          }`}
        >
          <Users className="h-4 w-4" /> Sessions
        </button>
      </div>

      {/* Providers */}
      {tab === 'providers' && (
        <div className="space-y-3">
          {providerList.map((p: { id: string; name: string; protocol: string; entity_id: string; enabled: boolean; allowed_domains?: string[] }) => (
            <div key={p.id} className="card flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`p-2 rounded-lg ${p.enabled ? 'bg-green-600/20' : 'bg-dark-700'}`}>
                  <Lock className={`h-5 w-5 ${p.enabled ? 'text-green-400' : 'text-dark-500'}`} />
                </div>
                <div>
                  <h3 className="font-medium text-white">{p.name}</h3>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="badge badge-info uppercase">{p.protocol}</span>
                    <span className="text-xs text-dark-400 font-mono">{p.entity_id}</span>
                  </div>
                  {p.allowed_domains && p.allowed_domains.length > 0 && (
                    <div className="flex gap-1 mt-1">
                      {p.allowed_domains.map((d) => (
                        <span key={d} className="badge badge-low text-xs">{d}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button className="text-red-400 hover:text-red-300"><Trash2 className="h-4 w-4" /></button>
                <span className={`badge ${p.enabled ? 'badge-success' : 'badge-info'}`}>
                  {p.enabled ? 'Active' : 'Disabled'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Sessions */}
      {tab === 'sessions' && (
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">Active SSO Sessions</h2>
          {sessionList.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-dark-400 border-b border-dark-700">
                  <th className="pb-3 font-medium">User</th>
                  <th className="pb-3 font-medium">Provider</th>
                  <th className="pb-3 font-medium">Created</th>
                  <th className="pb-3 font-medium">Expires</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700">
                {sessionList.map((s: { id: string; user: string; provider: string; created_at: string; expires_at: string }) => (
                  <tr key={s.id}>
                    <td className="py-3 text-white">{s.user}</td>
                    <td className="py-3 text-dark-300">{s.provider}</td>
                    <td className="py-3 text-dark-400">{s.created_at}</td>
                    <td className="py-3 text-dark-400">{s.expires_at}</td>
                    <td className="py-3"><button className="text-red-400 text-sm hover:underline">Revoke</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-dark-400">No active SSO sessions.</p>
          )}
        </div>
      )}
    </div>
  );
}
