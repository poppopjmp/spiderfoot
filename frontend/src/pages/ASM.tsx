import { useQuery } from '@tanstack/react-query';
import { asmApi } from '../lib/api';
import { Globe, Shield, AlertTriangle, Server, ExternalLink } from 'lucide-react';

export default function ASMPage() {
  const { data: dashboard } = useQuery({ queryKey: ['asm-dashboard'], queryFn: asmApi.dashboard });
  const { data: assets } = useQuery({ queryKey: ['asm-assets'], queryFn: asmApi.listAssets });
  const { data: policies } = useQuery({ queryKey: ['asm-policies'], queryFn: asmApi.policies });

  const assetList = assets?.assets ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Attack Surface Management</h1>

      {/* Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Assets', value: dashboard?.total_assets ?? assetList.length, icon: Globe, color: 'text-spider-400' },
          { label: 'Critical Exposure', value: dashboard?.critical ?? 0, icon: AlertTriangle, color: 'text-red-400' },
          { label: 'Active Policies', value: dashboard?.active_policies ?? (policies?.policies?.length ?? 0), icon: Shield, color: 'text-green-400' },
          { label: 'External Services', value: dashboard?.external_services ?? 0, icon: ExternalLink, color: 'text-blue-400' },
        ].map((s) => (
          <div key={s.label} className="card flex items-center gap-3">
            <s.icon className={`h-5 w-5 ${s.color}`} />
            <div>
              <p className="text-sm text-dark-400">{s.label}</p>
              <p className="text-xl font-bold text-white">{s.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Assets table */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Discovered Assets</h2>
        {assetList.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-dark-400 border-b border-dark-700">
                <th className="pb-3 font-medium">Asset</th>
                <th className="pb-3 font-medium">Type</th>
                <th className="pb-3 font-medium">Risk</th>
                <th className="pb-3 font-medium">Last Seen</th>
                <th className="pb-3 font-medium">Tags</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-700">
              {assetList.map((a: { id: string; name: string; type: string; risk: string; last_seen: string; tags?: string[] }) => (
                <tr key={a.id} className="hover:bg-dark-700/50">
                  <td className="py-3 text-white flex items-center gap-2">
                    <Server className="h-4 w-4 text-dark-400" /> {a.name}
                  </td>
                  <td className="py-3"><span className="badge badge-info">{a.type}</span></td>
                  <td className="py-3">
                    <span className={`badge ${
                      a.risk === 'critical' ? 'badge-critical' :
                      a.risk === 'high' ? 'badge-high' :
                      a.risk === 'medium' ? 'badge-medium' : 'badge-low'
                    }`}>{a.risk}</span>
                  </td>
                  <td className="py-3 text-dark-400">{a.last_seen}</td>
                  <td className="py-3">
                    <div className="flex gap-1">
                      {a.tags?.map((t) => <span key={t} className="badge badge-low text-xs">{t}</span>)}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-center py-8">
            <Globe className="h-12 w-12 text-dark-600 mx-auto mb-3" />
            <p className="text-dark-400">No assets discovered yet.</p>
            <p className="text-sm text-dark-500 mt-1">
              Run a scan with ASM modules enabled to discover your external attack surface.
            </p>
          </div>
        )}
      </div>

      {/* Policies */}
      {policies?.policies && policies.policies.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">Security Policies</h2>
          <div className="space-y-2">
            {policies.policies.map((p: { id: string; name: string; description: string; enabled: boolean }) => (
              <div key={p.id} className="flex items-center justify-between p-3 bg-dark-700/50 rounded-lg">
                <div>
                  <p className="text-white font-medium text-sm">{p.name}</p>
                  <p className="text-xs text-dark-400">{p.description}</p>
                </div>
                <span className={`badge ${p.enabled ? 'badge-success' : 'badge-info'}`}>
                  {p.enabled ? 'Active' : 'Disabled'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
