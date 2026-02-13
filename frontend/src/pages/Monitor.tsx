import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { monitorApi } from '../lib/api';
import { Globe, RefreshCw, Trash2, Plus, AlertTriangle, CheckCircle } from 'lucide-react';
import { useState } from 'react';

export default function MonitorPage() {
  const queryClient = useQueryClient();
  const [newDomain, setNewDomain] = useState('');

  const { data: domains, isLoading } = useQuery({
    queryKey: ['monitor-domains'],
    queryFn: monitorApi.listDomains,
  });

  const addDomain = useMutation({
    mutationFn: (domain: string) => monitorApi.addDomain({ domain }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitor-domains'] });
      setNewDomain('');
    },
  });

  const checkDomain = useMutation({
    mutationFn: (domain: string) => monitorApi.checkDomain(domain),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['monitor-domains'] }),
  });

  const deleteDomain = useMutation({
    mutationFn: (domain: string) => monitorApi.deleteDomain(domain),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['monitor-domains'] }),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Subdomain Monitor</h1>
      </div>

      {/* Add domain */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-white mb-3">Add Domain</h2>
        <form
          className="flex gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (newDomain.trim()) addDomain.mutate(newDomain.trim());
          }}
        >
          <input
            className="input-field flex-1"
            placeholder="example.com"
            value={newDomain}
            onChange={(e) => setNewDomain(e.target.value)}
          />
          <button type="submit" className="btn-primary flex items-center gap-2" disabled={addDomain.isPending}>
            <Plus className="h-4 w-4" /> Add
          </button>
        </form>
      </div>

      {/* Monitored domains */}
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-4">Monitored Domains</h2>
        {isLoading ? (
          <p className="text-dark-400">Loading...</p>
        ) : domains && domains.length > 0 ? (
          <div className="space-y-3">
            {domains.map((domain) => (
              <div
                key={domain.domain}
                className="flex items-center justify-between p-4 bg-dark-700/50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <Globe className="h-5 w-5 text-spider-400" />
                  <div>
                    <p className="text-white font-medium">{domain.domain}</p>
                    <p className="text-xs text-dark-400">
                      {domain.subdomain_count ?? 0} subdomains tracked
                      {domain.last_checked && ` · Last checked: ${domain.last_checked}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {domain.has_changes ? (
                    <span className="badge badge-high flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3" /> Changes
                    </span>
                  ) : (
                    <span className="badge badge-success flex items-center gap-1">
                      <CheckCircle className="h-3 w-3" /> Stable
                    </span>
                  )}
                  <button
                    className="text-spider-400 hover:text-spider-300"
                    onClick={() => checkDomain.mutate(domain.domain)}
                    title="Check now"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </button>
                  <button
                    className="text-red-400 hover:text-red-300"
                    onClick={() => deleteDomain.mutate(domain.domain)}
                    title="Remove"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-dark-400">
            No domains being monitored. Add a domain above to start tracking subdomain changes.
          </p>
        )}
      </div>
    </div>
  );
}
