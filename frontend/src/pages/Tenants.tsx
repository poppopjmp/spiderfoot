import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tenantApi } from '../lib/api';
import { Building2, Users, CreditCard, Plus, Settings, Trash2 } from 'lucide-react';
import { useState } from 'react';

export default function TenantsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', plan: 'free', max_users: 5, max_scans: 10 });

  const { data: tenants } = useQuery({ queryKey: ['tenants'], queryFn: tenantApi.list });
  const { data: stats } = useQuery({ queryKey: ['tenant-stats'], queryFn: tenantApi.stats });

  const createMutation = useMutation({
    mutationFn: tenantApi.create,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['tenants'] }); setShowCreate(false); },
  });

  const tenantList = tenants?.tenants ?? [];

  const planColor = (plan: string) => {
    switch (plan) {
      case 'enterprise': return 'badge-critical';
      case 'professional': return 'badge-high';
      case 'starter': return 'badge-medium';
      default: return 'badge-info';
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Tenant Management</h1>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> New Tenant
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="card flex items-center gap-3">
          <Building2 className="h-5 w-5 text-spider-400" />
          <div>
            <p className="text-sm text-dark-400">Total Tenants</p>
            <p className="text-xl font-bold text-white">{stats?.total_tenants ?? tenantList.length}</p>
          </div>
        </div>
        <div className="card flex items-center gap-3">
          <Users className="h-5 w-5 text-blue-400" />
          <div>
            <p className="text-sm text-dark-400">Total Users</p>
            <p className="text-xl font-bold text-white">{stats?.total_users ?? 0}</p>
          </div>
        </div>
        <div className="card flex items-center gap-3">
          <CreditCard className="h-5 w-5 text-green-400" />
          <div>
            <p className="text-sm text-dark-400">Paid Tenants</p>
            <p className="text-xl font-bold text-white">{stats?.paid_tenants ?? 0}</p>
          </div>
        </div>
        <div className="card flex items-center gap-3">
          <Settings className="h-5 w-5 text-purple-400" />
          <div>
            <p className="text-sm text-dark-400">Active Scans</p>
            <p className="text-xl font-bold text-white">{stats?.active_scans ?? 0}</p>
          </div>
        </div>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="card mb-6 border border-spider-600">
          <h2 className="text-lg font-semibold text-white mb-4">Create Tenant</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-300 mb-1">Tenant Name</label>
              <input className="input-field w-full" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Acme Corp" />
            </div>
            <div>
              <label className="block text-sm text-dark-300 mb-1">Plan</label>
              <select className="input-field w-full" value={form.plan} onChange={(e) => setForm({ ...form, plan: e.target.value })}>
                {['free', 'starter', 'professional', 'enterprise'].map((p) => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-dark-300 mb-1">Max Users</label>
              <input className="input-field w-full" type="number" value={form.max_users} onChange={(e) => setForm({ ...form, max_users: +e.target.value })} />
            </div>
            <div>
              <label className="block text-sm text-dark-300 mb-1">Max Scans</label>
              <input className="input-field w-full" type="number" value={form.max_scans} onChange={(e) => setForm({ ...form, max_scans: +e.target.value })} />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
            <button className="btn-primary" onClick={() => createMutation.mutate(form)} disabled={!form.name}>Create</button>
          </div>
        </div>
      )}

      {/* Tenant list */}
      <div className="space-y-3">
        {(tenantList.length > 0 ? tenantList : [
          { id: '1', name: 'Default', plan: 'enterprise', user_count: 12, scan_count: 45, max_users: 50, max_scans: 100, status: 'active' },
          { id: '2', name: 'Partner Org', plan: 'professional', user_count: 5, scan_count: 20, max_users: 20, max_scans: 50, status: 'active' },
          { id: '3', name: 'Trial Customer', plan: 'free', user_count: 1, scan_count: 2, max_users: 3, max_scans: 5, status: 'trial' },
        ]).map((t: { id: string; name: string; plan: string; user_count: number; scan_count: number; max_users: number; max_scans: number; status: string }) => (
          <div key={t.id} className="card flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-2 rounded-lg bg-spider-600/20">
                <Building2 className="h-5 w-5 text-spider-400" />
              </div>
              <div>
                <h3 className="font-medium text-white">{t.name}</h3>
                <div className="flex items-center gap-3 mt-1 text-sm text-dark-400">
                  <span className={`badge ${planColor(t.plan)}`}>{t.plan}</span>
                  <span>{t.user_count}/{t.max_users} users</span>
                  <span>{t.scan_count}/{t.max_scans} scans</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button className="text-red-400 hover:text-red-300"><Trash2 className="h-4 w-4" /></button>
              <span className={`badge ${t.status === 'active' ? 'badge-success' : 'badge-medium'}`}>{t.status}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
