import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { scanApi, engineApi } from '../lib/api';
import { useState } from 'react';

export default function NewScanPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [target, setTarget] = useState('');
  const [engine, setEngine] = useState('');
  const [useModules, setUseModules] = useState(false);
  const [selectedModules, setSelectedModules] = useState('');

  const { data: engines } = useQuery({
    queryKey: ['engines'],
    queryFn: engineApi.list,
  });

  const createScan = useMutation({
    mutationFn: (payload: {
      name: string;
      target: string;
      engine?: string;
      modules?: string[];
    }) => scanApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      navigate('/scans');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: { name: string; target: string; engine?: string; modules?: string[] } = {
      name,
      target,
    };
    if (engine) payload.engine = engine;
    if (useModules && selectedModules.trim()) {
      payload.modules = selectedModules.split(',').map((m) => m.trim());
    }
    createScan.mutate(payload);
  };

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-white mb-6">New Scan</h1>

      <form onSubmit={handleSubmit} className="card space-y-5">
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Scan Name</label>
          <input
            type="text"
            className="input-field"
            placeholder="My Scan"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Target</label>
          <input
            type="text"
            className="input-field"
            placeholder="example.com or 192.168.1.0/24"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            required
          />
          <p className="text-xs text-dark-500 mt-1">
            Domain, subdomain, IP address, CIDR, email, or username
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Scan Engine</label>
          <select
            className="input-field"
            value={engine}
            onChange={(e) => setEngine(e.target.value)}
          >
            <option value="">Default (all modules)</option>
            {engines?.map((eng) => (
              <option key={eng.id} value={eng.id}>
                {eng.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="flex items-center gap-2 text-sm text-dark-300 cursor-pointer">
            <input
              type="checkbox"
              checked={useModules}
              onChange={(e) => setUseModules(e.target.checked)}
              className="rounded bg-dark-700 border-dark-600 text-spider-500 focus:ring-spider-500"
            />
            Specify modules manually
          </label>
          {useModules && (
            <textarea
              className="input-field mt-2"
              rows={3}
              placeholder="sfp_dnsresolve, sfp_whois, sfp_shodan, ..."
              value={selectedModules}
              onChange={(e) => setSelectedModules(e.target.value)}
            />
          )}
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            className="btn-primary"
            disabled={createScan.isPending || !name || !target}
          >
            {createScan.isPending ? 'Starting...' : 'Start Scan'}
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate('/scans')}>
            Cancel
          </button>
        </div>

        {createScan.isError && (
          <p className="text-red-400 text-sm">
            Failed to start scan. Please try again.
          </p>
        )}
      </form>
    </div>
  );
}
