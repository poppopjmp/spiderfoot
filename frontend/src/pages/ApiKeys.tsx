import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { keysApi } from '../lib/api';
import { Key, Plus, Trash2, Copy, Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';

export default function ApiKeysPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [createdKey, setCreatedKey] = useState('');
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());

  const { data, isLoading } = useQuery({ queryKey: ['api-keys'], queryFn: keysApi.list });

  const createKey = useMutation({
    mutationFn: (name: string) => keysApi.create({ name }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
      setCreatedKey(data.key || data.api_key || 'Created successfully');
      setNewKeyName('');
    },
  });

  const revokeKey = useMutation({
    mutationFn: (id: string) => keysApi.revoke(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['api-keys'] }),
  });

  const keys = data?.keys ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">API Keys</h1>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> Generate Key
        </button>
      </div>

      {/* Created key alert */}
      {createdKey && (
        <div className="card mb-4 border border-green-600 bg-green-900/20">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-400 font-medium text-sm">API Key Created</p>
              <p className="text-xs text-dark-400 mt-1">Copy this key now — it won't be shown again.</p>
            </div>
            <div className="flex items-center gap-2">
              <code className="bg-dark-900 px-3 py-1 rounded text-sm text-white font-mono">{createdKey}</code>
              <button
                className="text-spider-400 hover:text-spider-300"
                onClick={() => navigator.clipboard.writeText(createdKey)}
              >
                <Copy className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="card mb-4 border border-spider-600">
          <h3 className="text-white font-semibold mb-3">Generate New API Key</h3>
          <form
            className="flex gap-3"
            onSubmit={(e) => { e.preventDefault(); createKey.mutate(newKeyName); }}
          >
            <input
              className="input-field flex-1"
              placeholder="Key name (e.g. CI Pipeline, Grafana)"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              required
            />
            <button type="submit" className="btn-primary" disabled={createKey.isPending}>
              {createKey.isPending ? 'Creating...' : 'Create'}
            </button>
            <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
          </form>
        </div>
      )}

      {/* Keys list */}
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-4">Active Keys</h2>
        {isLoading ? (
          <p className="text-dark-400">Loading...</p>
        ) : keys.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-dark-400 border-b border-dark-700">
                <th className="pb-3 font-medium">Name</th>
                <th className="pb-3 font-medium">Key Prefix</th>
                <th className="pb-3 font-medium">Created</th>
                <th className="pb-3 font-medium">Last Used</th>
                <th className="pb-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-700">
              {keys.map((k: { id: string; name: string; prefix: string; created_at: string; last_used?: string }) => (
                <tr key={k.id} className="hover:bg-dark-700/50">
                  <td className="py-3 text-white flex items-center gap-2">
                    <Key className="h-4 w-4 text-spider-400" /> {k.name}
                  </td>
                  <td className="py-3">
                    <code className="text-dark-300 font-mono text-xs">
                      {visibleKeys.has(k.id) ? k.prefix + '...' : '••••••••'}
                    </code>
                    <button
                      className="ml-2 text-dark-400 hover:text-white"
                      onClick={() => {
                        const s = new Set(visibleKeys);
                        s.has(k.id) ? s.delete(k.id) : s.add(k.id);
                        setVisibleKeys(s);
                      }}
                    >
                      {visibleKeys.has(k.id) ? <EyeOff className="h-3 w-3 inline" /> : <Eye className="h-3 w-3 inline" />}
                    </button>
                  </td>
                  <td className="py-3 text-dark-400">{k.created_at}</td>
                  <td className="py-3 text-dark-400">{k.last_used || 'Never'}</td>
                  <td className="py-3">
                    <button
                      className="text-red-400 hover:text-red-300"
                      onClick={() => revokeKey.mutate(k.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-dark-400">No API keys. Generate one to access the REST API programmatically.</p>
        )}
      </div>
    </div>
  );
}
