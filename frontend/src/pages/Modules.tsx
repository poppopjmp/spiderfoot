import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dataApi, type Module } from '../lib/api';
import {
  Cpu, Lock, Unlock, ToggleLeft, ToggleRight,
  ChevronDown, ChevronRight, Shield,
} from 'lucide-react';
import {
  PageHeader, SearchInput, StatCard, EmptyState, TableSkeleton,
  Toast,
  type ToastType,
} from '../components/ui';

type FilterKey = 'all' | 'enabled' | 'disabled' | 'api_key';

export default function ModulesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterKey>('all');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [toast, setToast] = useState<{ type: ToastType; message: string } | null>(null);

  const { data: modulesData, isLoading } = useQuery({
    queryKey: ['modules', { page: 1, page_size: 500 }],
    queryFn: () => dataApi.modules({ page: 1, page_size: 500 }),
  });

  const { data: statusData } = useQuery({
    queryKey: ['modules-status'],
    queryFn: dataApi.modulesStatus,
  });

  const { data: catData } = useQuery({
    queryKey: ['module-categories'],
    queryFn: dataApi.moduleCategories,
  });

  const modules: Module[] = modulesData?.items ?? [];
  const statusMap = useMemo(() => {
    const map = new Map<string, boolean>();
    statusData?.modules?.forEach((m: { module: string; enabled: boolean }) => map.set(m.module, m.enabled));
    return map;
  }, [statusData]);

  const categories = catData?.module_categories ?? [];

  const enableMut = useMutation({
    mutationFn: dataApi.enableModule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['modules-status'] });
      setToast({ type: 'success', message: 'Module enabled' });
    },
  });
  const disableMut = useMutation({
    mutationFn: dataApi.disableModule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['modules-status'] });
      setToast({ type: 'success', message: 'Module disabled' });
    },
  });

  const hasApiKeyField = (m: Module) =>
    m.opts && Object.keys(m.opts).some((k) => k.toLowerCase().includes('api_key') || k.toLowerCase().includes('apikey'));

  const hasApiKeyConfigured = (m: Module) => {
    if (!m.opts) return true;
    const apiKeys = Object.entries(m.opts).filter(
      ([k]) => k.toLowerCase().includes('api_key') || k.toLowerCase().includes('apikey'),
    );
    if (apiKeys.length === 0) return true;
    return apiKeys.every(([, v]) => v !== '' && v !== null && v !== undefined);
  };

  /* Filter & search */
  const filteredModules = useMemo(() => {
    let list = modules;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (m) =>
          m.name?.toLowerCase().includes(q) ||
          (m.descr || m.description || '').toLowerCase().includes(q) ||
          (Array.isArray(m.group) ? m.group.join(' ') : (m.group || '')).toLowerCase().includes(q) ||
          (Array.isArray(m.cats) ? m.cats.join(' ') : '').toLowerCase().includes(q),
      );
    }
    if (filter === 'enabled') list = list.filter((m) => statusMap.get(m.name) !== false);
    if (filter === 'disabled') list = list.filter((m) => statusMap.get(m.name) === false);
    if (filter === 'api_key') list = list.filter((m) => hasApiKeyField(m));
    return list;
  }, [modules, search, filter, statusMap]);

  /* Group by category */
  const grouped = useMemo(() => {
    const map = new Map<string, Module[]>();
    filteredModules.forEach((m) => {
      const cat = (Array.isArray(m.cats) && m.cats[0]) || (Array.isArray(m.group) ? m.group[0] : m.group) || m.category || 'Other';
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(m);
    });
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [filteredModules]);

  const totalEnabled = statusData?.enabled ?? 0;
  const totalDisabled = statusData?.disabled ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader title="Modules" subtitle={`${modules.length} data collection modules`} />

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Total" value={modules.length} icon={Cpu} color="text-spider-400" loading={isLoading} delay={0} />
        <StatCard label="Enabled" value={totalEnabled} icon={ToggleRight} color="text-green-400" loading={isLoading} delay={60} />
        <StatCard label="Disabled" value={totalDisabled} icon={ToggleLeft} color="text-dark-400" loading={isLoading} delay={120} />
        <StatCard label="Categories" value={categories.length} icon={Shield} color="text-blue-400" loading={isLoading} delay={180} />
      </div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search modules..."
          className="flex-1 max-w-md"
        />
        <div className="flex gap-2">
          {(['all', 'enabled', 'disabled', 'api_key'] as FilterKey[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={filter === f ? 'tab-button-active text-xs' : 'tab-button text-xs'}
            >
              {f === 'all' ? 'All' : f === 'enabled' ? 'Enabled' : f === 'disabled' ? 'Disabled' : 'API Key'}
            </button>
          ))}
        </div>
      </div>

      {/* Module list */}
      {isLoading ? (
        <div className="card"><TableSkeleton rows={10} cols={5} /></div>
      ) : grouped.length > 0 ? (
        <div className="space-y-4">
          {grouped.map(([cat, mods]) => (
            <div key={cat} className="animate-fade-in">
              <h3 className="section-label mb-3 flex items-center gap-2">
                {cat}
                <span className="text-dark-600 text-[10px] tabular-nums">{mods.length}</span>
              </h3>
              <div className="space-y-1">
                {mods.map((m) => {
                  const isEnabled = statusMap.get(m.name) !== false;
                  const apiOk = hasApiKeyConfigured(m);
                  const hasApi = hasApiKeyField(m);
                  const isExpanded = expanded === m.name;

                  return (
                    <div key={m.name} className="card-hover p-0 overflow-hidden">
                      <div className="flex items-center gap-3 px-4 py-3">
                        {/* Toggle */}
                        <button
                          onClick={() => isEnabled ? disableMut.mutate(m.name) : enableMut.mutate(m.name)}
                          className={`flex-shrink-0 transition-colors ${
                            isEnabled ? 'text-green-400 hover:text-green-300' : 'text-dark-600 hover:text-dark-400'
                          }`}
                          title={isEnabled ? 'Disable' : 'Enable'}
                        >
                          {isEnabled ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                        </button>

                        {/* Info */}
                        <div className="flex-1 min-w-0" onClick={() => setExpanded(isExpanded ? null : m.name)}>
                          <div className="flex items-center gap-2 cursor-pointer">
                            <span className="text-sm font-medium text-foreground">{m.name.replace('sfp_', '')}</span>
                            {hasApi && !apiOk && (
                              <span className="text-yellow-500" title="API key required but not configured">
                                <Lock className="h-3 w-3" />
                              </span>
                            )}
                            {hasApi && apiOk && (
                              <span className="text-green-400" title="API key configured">
                                <Unlock className="h-3 w-3" />
                              </span>
                            )}
                            {m.flags?.includes('slow') && (
                              <span className="badge bg-yellow-900/30 text-yellow-400 text-[9px] px-1 py-0">Slow</span>
                            )}
                            {m.flags?.includes('invasive') && (
                              <span className="badge bg-red-900/30 text-red-400 text-[9px] px-1 py-0">Invasive</span>
                            )}
                          </div>
                          <p className="text-xs text-dark-500 truncate">{m.descr || m.description}</p>
                        </div>

                        {/* Expand */}
                        <button
                          onClick={() => setExpanded(isExpanded ? null : m.name)}
                          className="btn-icon"
                        >
                          {isExpanded
                            ? <ChevronDown className="h-4 w-4 text-dark-400" />
                            : <ChevronRight className="h-4 w-4 text-dark-400" />}
                        </button>
                      </div>

                      {/* Expanded details */}
                      {isExpanded && (
                        <div className="px-4 pb-4 pt-1 border-t border-dark-700/30 animate-fade-in">
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                              <p className="text-xs text-dark-500 mb-1">Category</p>
                              <p className="text-sm text-dark-300">{Array.isArray(m.group) ? m.group.join(', ') : (m.group || m.category || 'N/A')}</p>
                            </div>
                            {m.provides && m.provides.length > 0 && (
                              <div>
                                <p className="text-xs text-dark-500 mb-1">Produces</p>
                                <div className="flex flex-wrap gap-1">
                                  {m.provides.map((p) => (
                                    <span key={p} className="badge badge-info text-[10px]">{p}</span>
                                  ))}
                                </div>
                              </div>
                            )}
                            {m.consumes && m.consumes.length > 0 && (
                              <div>
                                <p className="text-xs text-dark-500 mb-1">Consumes</p>
                                <div className="flex flex-wrap gap-1">
                                  {m.consumes.map((c) => (
                                    <span key={c} className="badge badge-low text-[10px]">{c}</span>
                                  ))}
                                </div>
                              </div>
                            )}
                            {m.opts && Object.keys(m.opts).length > 0 && (
                              <div className="sm:col-span-2">
                                <p className="text-xs text-dark-500 mb-2">Options ({Object.keys(m.opts).length})</p>
                                <div className="space-y-1 max-h-40 overflow-y-auto">
                                  {Object.entries(m.opts).map(([k, v]) => (
                                    <div key={k} className="flex items-center justify-between text-xs">
                                      <span className="text-dark-400 font-mono">{k}</span>
                                      <span className="text-dark-500">{m.optdescs?.[k]?.slice(0, 60) || String(v ?? '')}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
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
        <div className="card">
          <EmptyState
            icon={Cpu}
            title="No modules found"
            description={search ? 'Try adjusting your search query.' : 'No modules available.'}
          />
        </div>
      )}

      {toast && <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} />}
    </div>
  );
}
