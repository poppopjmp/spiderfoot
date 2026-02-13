import { useQuery } from '@tanstack/react-query';
import { retentionApi } from '../lib/api';
import { Database, Clock, Trash2, ShieldCheck, Plus, Play, Eye } from 'lucide-react';
import { useState } from 'react';

export default function DataRetentionPage() {
  const { data: rules } = useQuery({ queryKey: ['retention-rules'], queryFn: retentionApi.listRules });
  const { data: stats } = useQuery({ queryKey: ['retention-stats'], queryFn: retentionApi.stats });

  const ruleList = rules?.rules ?? [];

  const actionBadge = (action: string) => {
    switch (action) {
      case 'delete': return 'badge-critical';
      case 'archive': return 'badge-medium';
      case 'export_then_delete': return 'badge-high';
      default: return 'badge-info';
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Data Retention</h1>
        <button className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> Create Rule
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="card flex items-center gap-3">
            <Database className="h-5 w-5 text-spider-400" />
            <div>
              <p className="text-sm text-dark-400">Total Rules</p>
              <p className="text-xl font-bold text-white">{stats.total_rules ?? ruleList.length}</p>
            </div>
          </div>
          <div className="card flex items-center gap-3">
            <Clock className="h-5 w-5 text-blue-400" />
            <div>
              <p className="text-sm text-dark-400">Last Enforced</p>
              <p className="text-xl font-bold text-white">{stats.last_enforced ?? 'Never'}</p>
            </div>
          </div>
          <div className="card flex items-center gap-3">
            <Trash2 className="h-5 w-5 text-red-400" />
            <div>
              <p className="text-sm text-dark-400">Resources Cleaned</p>
              <p className="text-xl font-bold text-white">{stats.total_cleaned ?? 0}</p>
            </div>
          </div>
          <div className="card flex items-center gap-3">
            <ShieldCheck className="h-5 w-5 text-green-400" />
            <div>
              <p className="text-sm text-dark-400">Space Freed</p>
              <p className="text-xl font-bold text-white">{stats.space_freed ?? '0 MB'}</p>
            </div>
          </div>
        </div>
      )}

      {/* Rules */}
      <div className="space-y-3">
        {ruleList.map((r: { id: string; name: string; criteria_type: string; criteria_value: string; action: string; resource_type: string; enabled: boolean }) => (
          <div key={r.id} className="card flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`p-2 rounded-lg ${r.enabled ? 'bg-spider-600/20' : 'bg-dark-700'}`}>
                <Database className={`h-5 w-5 ${r.enabled ? 'text-spider-400' : 'text-dark-500'}`} />
              </div>
              <div>
                <h3 className="font-medium text-white">{r.name}</h3>
                <div className="flex items-center gap-2 mt-1">
                  <span className="badge badge-info">{r.resource_type}</span>
                  <span className="badge badge-low">{r.criteria_type}: {r.criteria_value}</span>
                  <span className={`badge ${actionBadge(r.action)}`}>{r.action}</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button className="text-spider-400 hover:text-spider-300" title="Preview">
                <Eye className="h-4 w-4" />
              </button>
              <button className="text-green-400 hover:text-green-300" title="Enforce now">
                <Play className="h-4 w-4" />
              </button>
              <span className={`badge ${r.enabled ? 'badge-success' : 'badge-info'}`}>
                {r.enabled ? 'Active' : 'Disabled'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
