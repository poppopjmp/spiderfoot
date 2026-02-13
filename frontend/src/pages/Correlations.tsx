import { useQuery } from '@tanstack/react-query';
import { correlationApi } from '../lib/api';
import { GitBranch, Zap, AlertTriangle, Info } from 'lucide-react';

export default function CorrelationsPage() {
  const { data, isLoading } = useQuery({ queryKey: ['correlations'], queryFn: correlationApi.list });

  const correlations = data?.correlations ?? data?.rules ?? [];

  const severityIcon = (sev: string) => {
    switch (sev) {
      case 'critical': return <AlertTriangle className="h-4 w-4 text-red-400" />;
      case 'high': return <AlertTriangle className="h-4 w-4 text-orange-400" />;
      case 'medium': return <Info className="h-4 w-4 text-yellow-400" />;
      default: return <Info className="h-4 w-4 text-blue-400" />;
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Correlations</h1>
        <div className="text-sm text-dark-400">
          {correlations.length} correlation rules loaded
        </div>
      </div>

      {isLoading ? (
        <p className="text-dark-400">Loading correlations...</p>
      ) : correlations.length > 0 ? (
        <div className="space-y-3">
          {correlations.map((c: { id: string; name: string; description: string; severity: string; category?: string; enabled?: boolean }) => (
            <div key={c.id || c.name} className="card flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-2 bg-spider-600/20 rounded-lg">
                  <GitBranch className="h-5 w-5 text-spider-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-white">{c.name}</h3>
                    {c.category && <span className="badge badge-info">{c.category}</span>}
                  </div>
                  <p className="text-sm text-dark-400 mt-1">{c.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {severityIcon(c.severity)}
                <span className={`badge ${
                  c.severity === 'critical' ? 'badge-critical' :
                  c.severity === 'high' ? 'badge-high' :
                  c.severity === 'medium' ? 'badge-medium' : 'badge-low'
                }`}>
                  {c.severity}
                </span>
                <Zap className={`h-4 w-4 ${c.enabled !== false ? 'text-green-400' : 'text-dark-500'}`} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card">
          <p className="text-dark-400">
            No correlations configured. Correlation rules are loaded from YAML files in the correlations/ directory.
          </p>
        </div>
      )}
    </div>
  );
}
