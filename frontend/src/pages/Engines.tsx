import { useQuery } from '@tanstack/react-query';
import { engineApi } from '../lib/api';
import { Cog, Zap } from 'lucide-react';

export default function EnginesPage() {
  const { data: engines, isLoading } = useQuery({
    queryKey: ['engines'],
    queryFn: engineApi.list,
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Scan Engines</h1>
      </div>

      {isLoading ? (
        <p className="text-dark-400">Loading engines...</p>
      ) : engines && engines.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {engines.map((engine) => (
            <div key={engine.id} className="card hover:border-spider-600 border border-transparent transition">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-spider-600/20 rounded-lg">
                  <Zap className="h-5 w-5 text-spider-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-white">{engine.name}</h3>
                  <p className="text-xs text-dark-400">{engine.id}</p>
                </div>
              </div>
              {engine.description && (
                <p className="text-sm text-dark-300 mb-3">{engine.description}</p>
              )}
              <div className="flex items-center justify-between text-sm">
                <span className="text-dark-400">
                  {engine.modules?.length ?? 0} modules
                </span>
                <button className="text-spider-400 hover:text-spider-300 flex items-center gap-1">
                  <Cog className="h-3.5 w-3.5" /> Configure
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card">
          <p className="text-dark-400">
            No scan engines configured. Create YAML engine profiles to define reusable scan
            configurations.
          </p>
        </div>
      )}
    </div>
  );
}
