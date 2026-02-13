import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useMemo } from 'react';
import { dataApi, type Module } from '../lib/api';
import {
  Cpu, Search, ChevronDown, ChevronRight, Check, X,
  ArrowRight, ArrowLeft, ToggleLeft, ToggleRight,
} from 'lucide-react';

export default function ModulesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [expandedModule, setExpandedModule] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>('');

  // Load modules
  const { data: modulesData, isLoading } = useQuery({
    queryKey: ['modules-list', { page: 1, page_size: 500 }],
    queryFn: () => dataApi.modules({ page: 1, page_size: 500 }),
  });

  // Load categories
  const { data: categoriesData } = useQuery({
    queryKey: ['module-categories'],
    queryFn: () => dataApi.moduleCategories(),
  });

  // Load status
  const { data: statusData } = useQuery({
    queryKey: ['modules-status'],
    queryFn: () => dataApi.modulesStatus(),
  });

  const modules = modulesData?.data ?? [];
  const categories = categoriesData?.module_categories ?? [];
  const moduleStatusMap = useMemo(() => {
    const map: Record<string, boolean> = {};
    if (statusData?.modules) {
      for (const ms of statusData.modules) {
        map[ms.module] = ms.enabled;
      }
    }
    return map;
  }, [statusData]);

  // Filter and group
  const filtered = useMemo(() => {
    let result = modules;
    if (categoryFilter) {
      result = result.filter((m) => (m.category || m.group) === categoryFilter);
    }
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (m) =>
          m.name.toLowerCase().includes(q) ||
          (m.description || m.descr || '').toLowerCase().includes(q) ||
          (m.provides ?? []).some((p) => p.toLowerCase().includes(q)) ||
          (m.consumes ?? []).some((c) => c.toLowerCase().includes(q)),
      );
    }
    return result;
  }, [modules, categoryFilter, search]);

  // Group by category
  const grouped = useMemo(() => {
    const groups: Record<string, Module[]> = {};
    for (const mod of filtered) {
      const cat = mod.category || mod.group || 'Uncategorized';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(mod);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  // Toggle module
  const enableModule = useMutation({
    mutationFn: (name: string) => dataApi.enableModule(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['modules-status'] }),
  });

  const disableModule = useMutation({
    mutationFn: (name: string) => dataApi.disableModule(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['modules-status'] }),
  });

  const toggleModule = (name: string) => {
    if (moduleStatusMap[name] === false) {
      enableModule.mutate(name);
    } else {
      disableModule.mutate(name);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Modules</h1>
          <p className="text-dark-400 mt-1">
            {modules.length} modules available
            {statusData && ` \u2022 ${statusData.enabled ?? modules.length} enabled`}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="relative flex-1 min-w-[250px] max-w-lg">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-400" />
          <input
            className="input-field pl-10"
            placeholder="Search modules, event types..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="input-field max-w-xs"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
        >
          <option value="">All categories</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      </div>

      {/* Module list */}
      {isLoading ? (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin h-6 w-6 border-2 border-spider-500 border-t-transparent rounded-full" />
        </div>
      ) : filtered.length > 0 ? (
        <div className="space-y-4">
          {grouped.map(([category, mods]) => (
            <div key={category}>
              <h3 className="text-sm font-semibold text-dark-400 uppercase tracking-wider mb-2">
                {category} ({mods.length})
              </h3>
              <div className="space-y-1">
                {mods.map((mod) => {
                  const isExpanded = expandedModule === mod.name;
                  const isEnabled = moduleStatusMap[mod.name] !== false;

                  return (
                    <div
                      key={mod.name}
                      className="border border-dark-700 rounded-lg overflow-hidden"
                    >
                      <div
                        className="flex items-center justify-between p-3 hover:bg-dark-700/30 cursor-pointer"
                        onClick={() => setExpandedModule(isExpanded ? null : mod.name)}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-dark-400 flex-shrink-0" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-dark-400 flex-shrink-0" />
                          )}
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-white font-mono text-sm">{mod.name}</span>
                              {mod.flags?.map((flag) => (
                                <span key={flag} className="badge badge-info text-[10px]">{flag}</span>
                              ))}
                            </div>
                            <p className="text-xs text-dark-400 truncate">
                              {mod.description || mod.descr || 'No description'}
                            </p>
                          </div>
                        </div>

                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleModule(mod.name);
                          }}
                          className={`flex-shrink-0 ml-4 ${isEnabled ? 'text-green-400' : 'text-dark-500'}`}
                          title={isEnabled ? 'Disable' : 'Enable'}
                        >
                          {isEnabled ? (
                            <ToggleRight className="h-6 w-6" />
                          ) : (
                            <ToggleLeft className="h-6 w-6" />
                          )}
                        </button>
                      </div>

                      {isExpanded && (
                        <div className="p-4 bg-dark-800/50 border-t border-dark-700">
                          <p className="text-sm text-dark-200 mb-4">
                            {mod.description || mod.descr || 'No description available.'}
                          </p>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {/* Produces */}
                            <div>
                              <h4 className="text-xs text-dark-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                                <ArrowRight className="h-3 w-3" /> Produces
                              </h4>
                              <div className="flex flex-wrap gap-1">
                                {(mod.provides ?? []).length > 0 ? (
                                  mod.provides!.map((et) => (
                                    <span key={et} className="badge badge-success text-xs">{et}</span>
                                  ))
                                ) : (
                                  <span className="text-dark-500 text-xs">None</span>
                                )}
                              </div>
                            </div>

                            {/* Consumes */}
                            <div>
                              <h4 className="text-xs text-dark-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                                <ArrowLeft className="h-3 w-3" /> Consumes
                              </h4>
                              <div className="flex flex-wrap gap-1">
                                {(mod.consumes ?? []).length > 0 ? (
                                  mod.consumes!.map((et) => (
                                    <span key={et} className="badge badge-low text-xs">{et}</span>
                                  ))
                                ) : (
                                  <span className="text-dark-500 text-xs">None</span>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Dependencies */}
                          {mod.dependencies && mod.dependencies.length > 0 && (
                            <div className="mt-4">
                              <h4 className="text-xs text-dark-400 uppercase tracking-wider mb-2">
                                Dependencies
                              </h4>
                              <div className="flex flex-wrap gap-1">
                                {mod.dependencies.map((dep) => (
                                  <span key={dep} className="badge badge-medium text-xs">{dep}</span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card text-center py-12">
          <Cpu className="h-12 w-12 mx-auto text-dark-600 mb-3" />
          <p className="text-dark-400">
            {search || categoryFilter
              ? 'No modules match your filters.'
              : 'No modules loaded. Is the API server running?'}
          </p>
        </div>
      )}
    </div>
  );
}
