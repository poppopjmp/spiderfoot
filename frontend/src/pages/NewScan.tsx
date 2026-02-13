import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useState, useMemo } from 'react';
import { scanApi, dataApi, type Module } from '../lib/api';
import { Radar, Search, ChevronDown, ChevronRight, Check } from 'lucide-react';

type UseCase = 'all' | 'passive' | 'investigate' | 'footprint' | 'custom';

const USE_CASE_INFO: Record<UseCase, { label: string; description: string }> = {
  all: { label: 'All Modules', description: 'Run every available module (slowest, most thorough)' },
  passive: { label: 'Passive Only', description: 'Only modules that do not touch the target directly' },
  investigate: { label: 'Investigate', description: 'Modules focused on discovering related entities' },
  footprint: { label: 'Footprint', description: 'Modules for mapping the target\'s digital footprint' },
  custom: { label: 'Custom', description: 'Manually select which modules to run' },
};

export default function NewScanPage() {
  const navigate = useNavigate();
  const [target, setTarget] = useState('');
  const [scanName, setScanName] = useState('');
  const [useCase, setUseCase] = useState<UseCase>('all');
  const [selectedModules, setSelectedModules] = useState<Set<string>>(new Set());
  const [moduleSearch, setModuleSearch] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  // Load modules from the real API
  const { data: modulesData, isLoading: modulesLoading } = useQuery({
    queryKey: ['modules', { page: 1, page_size: 500 }],
    queryFn: () => dataApi.modules({ page: 1, page_size: 500 }),
  });

  const { data: categoriesData } = useQuery({
    queryKey: ['module-categories'],
    queryFn: () => dataApi.moduleCategories(),
  });

  const modules = modulesData?.data ?? [];
  const categories = categoriesData?.module_categories ?? [];

  // Group modules by category
  const grouped = useMemo(() => {
    const groups: Record<string, Module[]> = {};
    for (const mod of modules) {
      const cat = mod.category || mod.group || 'Uncategorized';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(mod);
    }
    // Sort categories, put Uncategorized last
    const sortedKeys = Object.keys(groups).sort((a, b) => {
      if (a === 'Uncategorized') return 1;
      if (b === 'Uncategorized') return -1;
      return a.localeCompare(b);
    });
    return sortedKeys.map((key) => ({ category: key, modules: groups[key] }));
  }, [modules]);

  // Filter modules by search
  const filteredGrouped = useMemo(() => {
    if (!moduleSearch) return grouped;
    const q = moduleSearch.toLowerCase();
    return grouped
      .map((g) => ({
        category: g.category,
        modules: g.modules.filter(
          (m) =>
            m.name.toLowerCase().includes(q) ||
            (m.description || m.descr || '').toLowerCase().includes(q),
        ),
      }))
      .filter((g) => g.modules.length > 0);
  }, [grouped, moduleSearch]);

  // Use case module filtering
  const getModulesForUseCase = (uc: UseCase): string[] => {
    if (uc === 'all') return modules.map((m) => m.name);
    if (uc === 'custom') return Array.from(selectedModules);
    // Filter by flags/meta
    return modules
      .filter((m) => {
        const flags = m.flags ?? [];
        const meta = m.meta as Record<string, unknown> ?? {};
        const useCases = (meta.useCases ?? []) as string[];
        if (uc === 'passive') return flags.includes('passive') || !flags.includes('active');
        if (uc === 'investigate') return useCases.includes('Investigate') || flags.includes('investigate');
        if (uc === 'footprint') return useCases.includes('Footprint') || flags.includes('footprint');
        return true;
      })
      .map((m) => m.name);
  };

  const createScan = useMutation({
    mutationFn: (data: { name: string; target: string; modules?: string[] }) =>
      scanApi.create(data),
    onSuccess: (result) => {
      navigate(`/scans/${result.id}`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!target.trim()) return;

    const name = scanName.trim() || `Scan of ${target.trim()}`;
    const mods = useCase === 'all' ? undefined : getModulesForUseCase(useCase);

    createScan.mutate({
      name,
      target: target.trim(),
      modules: mods,
    });
  };

  const toggleCategory = (cat: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat); else next.add(cat);
      return next;
    });
  };

  const toggleModule = (name: string) => {
    setSelectedModules((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  };

  const selectAllInCategory = (catModules: Module[]) => {
    setSelectedModules((prev) => {
      const next = new Set(prev);
      const allSelected = catModules.every((m) => next.has(m.name));
      catModules.forEach((m) => {
        if (allSelected) next.delete(m.name); else next.add(m.name);
      });
      return next;
    });
  };

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-white mb-6">New Scan</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Target */}
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">Target</h2>
          <input
            className="input-field"
            placeholder="Enter target (domain, IP, email, username, etc.)"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            required
            autoFocus
          />
          <p className="text-xs text-dark-400 mt-2">
            Supported: domain names, IP addresses, email addresses, phone numbers, usernames, subnets, Bitcoin addresses
          </p>
        </div>

        {/* Scan Name */}
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">Scan Name (optional)</h2>
          <input
            className="input-field"
            placeholder={target ? `Scan of ${target}` : 'Auto-generated from target'}
            value={scanName}
            onChange={(e) => setScanName(e.target.value)}
          />
        </div>

        {/* Use Case */}
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">Scan Mode</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(Object.entries(USE_CASE_INFO) as [UseCase, { label: string; description: string }][]).map(
              ([key, info]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setUseCase(key)}
                  className={`text-left p-3 rounded-lg border transition-colors ${
                    useCase === key
                      ? 'border-spider-500 bg-spider-600/10'
                      : 'border-dark-600 hover:border-dark-500 bg-dark-700/30'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <div className={`w-3 h-3 rounded-full border-2 flex items-center justify-center ${
                      useCase === key ? 'border-spider-500' : 'border-dark-500'
                    }`}>
                      {useCase === key && <div className="w-1.5 h-1.5 rounded-full bg-spider-500" />}
                    </div>
                    <span className="font-medium text-white text-sm">{info.label}</span>
                  </div>
                  <p className="text-xs text-dark-400 pl-5">{info.description}</p>
                </button>
              ),
            )}
          </div>

          {useCase !== 'custom' && (
            <p className="text-sm text-dark-400 mt-3">
              {useCase === 'all'
                ? `${modules.length} modules will be used`
                : `${getModulesForUseCase(useCase).length} of ${modules.length} modules selected`}
            </p>
          )}
        </div>

        {/* Custom Module Selection */}
        {useCase === 'custom' && (
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">
                Select Modules ({selectedModules.size} selected)
              </h2>
            </div>

            {/* Module search */}
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-400" />
              <input
                className="input-field pl-10"
                placeholder="Search modules..."
                value={moduleSearch}
                onChange={(e) => setModuleSearch(e.target.value)}
              />
            </div>

            {modulesLoading ? (
              <div className="flex items-center justify-center h-32">
                <div className="animate-spin h-6 w-6 border-2 border-spider-500 border-t-transparent rounded-full" />
              </div>
            ) : (
              <div className="max-h-96 overflow-y-auto space-y-1">
                {filteredGrouped.map((group) => (
                  <div key={group.category} className="border border-dark-700 rounded-lg overflow-hidden">
                    <button
                      type="button"
                      onClick={() => toggleCategory(group.category)}
                      className="w-full flex items-center justify-between p-3 bg-dark-700/50 hover:bg-dark-700 text-sm"
                    >
                      <div className="flex items-center gap-2">
                        {expandedCategories.has(group.category) ? (
                          <ChevronDown className="h-4 w-4 text-dark-400" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-dark-400" />
                        )}
                        <span className="text-white font-medium">{group.category}</span>
                        <span className="text-dark-400 text-xs">({group.modules.length})</span>
                      </div>
                      <button
                        type="button"
                        className="text-xs text-spider-400 hover:text-spider-300"
                        onClick={(e) => {
                          e.stopPropagation();
                          selectAllInCategory(group.modules);
                        }}
                      >
                        Toggle all
                      </button>
                    </button>

                    {expandedCategories.has(group.category) && (
                      <div className="divide-y divide-dark-700/50">
                        {group.modules.map((mod) => (
                          <label
                            key={mod.name}
                            className="flex items-start gap-3 p-3 hover:bg-dark-700/30 cursor-pointer"
                          >
                            <div className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                              selectedModules.has(mod.name)
                                ? 'bg-spider-600 border-spider-500'
                                : 'border-dark-500'
                            }`}>
                              {selectedModules.has(mod.name) && <Check className="h-3 w-3 text-white" />}
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm text-white font-mono">{mod.name}</p>
                              <p className="text-xs text-dark-400 mt-0.5">
                                {mod.description || mod.descr || 'No description'}
                              </p>
                            </div>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Submit */}
        <div className="flex items-center gap-4">
          <button
            type="submit"
            className="btn-primary flex items-center gap-2"
            disabled={!target.trim() || createScan.isPending || (useCase === 'custom' && selectedModules.size === 0)}
          >
            <Radar className="h-4 w-4" />
            {createScan.isPending ? 'Starting...' : 'Start Scan'}
          </button>

          {createScan.isError && (
            <p className="text-red-400 text-sm">
              Failed to start scan: {(createScan.error as Error)?.message || 'Unknown error'}
            </p>
          )}
        </div>
      </form>
    </div>
  );
}
