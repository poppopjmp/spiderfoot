import { useState, useMemo } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  dataApi, scanApi, type Module, type ScanCreateRequest,
} from '../lib/api';
import {
  Radar, Lock, Unlock, Zap,
  ShieldCheck, FileText, Loader2,
} from 'lucide-react';
import { PageHeader, Tabs, SearchInput, Toast, type ToastType } from '../components/ui';

type TabKey = 'usecase' | 'data' | 'module';

const USE_CASES = [
  { key: 'all', label: 'All Modules', desc: 'Run every available module for maximum coverage' },
  { key: 'footprint', label: 'Footprint', desc: 'Discover the target\'s full digital footprint' },
  { key: 'investigate', label: 'Investigate', desc: 'Deep dive into a specific target' },
  { key: 'passive', label: 'Passive Only', desc: 'Only passive/non-intrusive modules' },
];

export default function NewScanPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>('usecase');
  const [target, setTarget] = useState('');
  const [scanName, setScanName] = useState('');
  const [useCase, setUseCase] = useState('all');
  const [selectedModules, setSelectedModules] = useState<Set<string>>(new Set());
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [moduleSearch, setModuleSearch] = useState('');
  const [toast, setToast] = useState<{ type: ToastType; message: string } | null>(null);

  /* Data queries */
  const { data: modulesData } = useQuery({
    queryKey: ['modules', { page: 1, page_size: 500 }],
    queryFn: () => dataApi.modules({ page: 1, page_size: 500 }),
  });
  const { data: entityData } = useQuery({
    queryKey: ['entity-types'],
    queryFn: dataApi.entityTypes,
  });

  const modules: Module[] = modulesData?.data ?? [];
  const entityTypes: string[] = entityData?.entity_types ?? [];

  /* Target type detection */
  const detectedType = useMemo(() => {
    const t = target.trim();
    if (!t) return null;
    if (/^(\d{1,3}\.){3}\d{1,3}(\/\d+)?$/.test(t)) return 'IP Address';
    if (/^[a-f0-9:]+$/i.test(t) && t.includes(':')) return 'IPv6 Address';
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t)) return 'Email Address';
    if (/^(\+?\d[\d\s-]{6,})$/.test(t)) return 'Phone Number';
    if (/^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(t)) return 'Domain Name';
    if (/^AS\d+$/i.test(t)) return 'ASN';
    if (/\s/.test(t)) return 'Human Name';
    return 'Unknown';
  }, [target]);

  /* Filtered modules for the Module tab */
  const filteredModules = useMemo(() => {
    if (!moduleSearch) return modules;
    const q = moduleSearch.toLowerCase();
    return modules.filter(
      (m) =>
        m.name?.toLowerCase().includes(q) ||
        (m.descr || m.description || '').toLowerCase().includes(q) ||
        m.group?.toLowerCase().includes(q),
    );
  }, [modules, moduleSearch]);

  /* Group modules by category */
  const grouped = useMemo(() => {
    const map = new Map<string, Module[]>();
    filteredModules.forEach((m) => {
      const cat = m.group || m.category || 'Other';
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(m);
    });
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [filteredModules]);

  /* Determine which modules to use */
  const effectiveModules = useMemo(() => {
    if (tab === 'module') return [...selectedModules];
    if (tab === 'data') {
      // Find modules that produce any of the selected entity types
      return modules
        .filter((m) => m.provides?.some((p) => selectedTypes.has(p)))
        .map((m) => m.name);
    }
    if (tab === 'usecase') {
      if (useCase === 'all') return [];
      if (useCase === 'passive') {
        return modules.filter((m) => m.flags?.includes('passive')).map((m) => m.name);
      }
      return modules
        .filter((m) => m.group?.toLowerCase().includes(useCase))
        .map((m) => m.name);
    }
    return [];
  }, [tab, selectedModules, selectedTypes, useCase, modules]);

  /* Create scan */
  const createMut = useMutation({
    mutationFn: (data: ScanCreateRequest) => scanApi.create(data),
    onSuccess: (r) => {
      setToast({ type: 'success', message: 'Scan started!' });
      setTimeout(() => navigate(`/scans/${r.id}`), 800);
    },
    onError: () => {
      setToast({ type: 'error', message: 'Failed to create scan' });
    },
  });

  const handleSubmit = () => {
    if (!target.trim()) return;
    const payload: ScanCreateRequest = {
      name: scanName || `Scan of ${target}`,
      target: target.trim(),
    };
    if (effectiveModules.length > 0) {
      payload.modules = effectiveModules;
    }
    createMut.mutate(payload);
  };

  const toggleModule = (name: string) => {
    const next = new Set(selectedModules);
    next.has(name) ? next.delete(name) : next.add(name);
    setSelectedModules(next);
  };

  const toggleType = (type: string) => {
    const next = new Set(selectedTypes);
    next.has(type) ? next.delete(type) : next.add(type);
    setSelectedTypes(next);
  };

  const hasApiKey = (m: Module) => {
    if (!m.opts) return true;
    return !Object.entries(m.opts).some(
      ([k, v]) => (k.toLowerCase().includes('api_key') || k.toLowerCase().includes('apikey'))
        && (!v.default || v.default === ''),
    );
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <PageHeader title="New Scan" subtitle="Configure and launch an OSINT reconnaissance scan" />

      {/* Target Input */}
      <div className="card animate-fade-in-up" style={{ animationDelay: '50ms' }}>
        <label className="section-label mb-3 block">Target</label>
        <div className="relative">
          <input
            type="text"
            className="input-field text-lg"
            placeholder="Enter domain, IP, email, phone, name, or ASN..."
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            autoFocus
          />
          {detectedType && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2 badge badge-info text-xs animate-fade-in">
              {detectedType}
            </span>
          )}
        </div>

        <div className="mt-4">
          <label className="section-label mb-2 block">Scan Name (optional)</label>
          <input
            type="text"
            className="input-field"
            placeholder={target ? `Scan of ${target}` : 'Give your scan a name...'}
            value={scanName}
            onChange={(e) => setScanName(e.target.value)}
          />
        </div>
      </div>

      {/* Module Selection */}
      <div className="card animate-fade-in-up" style={{ animationDelay: '100ms' }}>
        <label className="section-label mb-4 block">Module Selection</label>

        <Tabs<TabKey>
          tabs={[
            { key: 'usecase', label: 'By Use Case', icon: Zap },
            { key: 'data', label: 'By Required Data', icon: FileText },
            { key: 'module', label: 'By Module', icon: ShieldCheck, count: tab === 'module' ? selectedModules.size : undefined },
          ]}
          active={tab}
          onChange={setTab}
        />

        <div className="mt-5">
          {/* By Use Case */}
          {tab === 'usecase' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 animate-fade-in">
              {USE_CASES.map((uc) => (
                <button
                  key={uc.key}
                  onClick={() => setUseCase(uc.key)}
                  className={`p-4 rounded-xl border text-left transition-all ${
                    useCase === uc.key
                      ? 'border-spider-500 bg-spider-600/10 ring-1 ring-spider-500/30'
                      : 'border-dark-700 hover:border-dark-600 hover:bg-dark-700/30'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full border-2 flex items-center justify-center ${
                      useCase === uc.key ? 'border-spider-500' : 'border-dark-500'
                    }`}>
                      {useCase === uc.key && <div className="w-1.5 h-1.5 rounded-full bg-spider-500" />}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{uc.label}</p>
                      <p className="text-xs text-dark-400 mt-0.5">{uc.desc}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* By Required Data */}
          {tab === 'data' && (
            <div className="animate-fade-in">
              <p className="text-sm text-dark-400 mb-3">
                Select the types of data you want to collect. Modules that produce this data will be enabled.
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-[400px] overflow-y-auto pr-2">
                {entityTypes.map((et) => (
                  <label
                    key={et}
                    className={`flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-all text-sm ${
                      selectedTypes.has(et)
                        ? 'border-spider-500/50 bg-spider-600/10 text-white'
                        : 'border-dark-700/50 text-dark-300 hover:border-dark-600'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedTypes.has(et)}
                      onChange={() => toggleType(et)}
                      className="rounded border-dark-600 bg-dark-700 text-spider-500 focus:ring-spider-500/30"
                    />
                    <span className="truncate">{et.replace(/_/g, ' ')}</span>
                  </label>
                ))}
              </div>
              {selectedTypes.size > 0 && (
                <p className="text-xs text-dark-500 mt-3">
                  {effectiveModules.length} module(s) match your selection
                </p>
              )}
            </div>
          )}

          {/* By Module */}
          {tab === 'module' && (
            <div className="animate-fade-in">
              <div className="flex gap-3 mb-4">
                <SearchInput
                  value={moduleSearch}
                  onChange={setModuleSearch}
                  placeholder="Search modules..."
                  className="flex-1"
                />
                <button
                  className="btn-ghost text-xs"
                  onClick={() => setSelectedModules(new Set(modules.map((m) => m.name)))}
                >
                  Select All
                </button>
                <button
                  className="btn-ghost text-xs"
                  onClick={() => setSelectedModules(new Set())}
                >
                  Clear
                </button>
              </div>

              <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2">
                {grouped.map(([cat, mods]) => (
                  <div key={cat}>
                    <h4 className="section-label mb-2 sticky top-0 bg-dark-800 py-1">{cat}</h4>
                    <div className="space-y-1">
                      {mods.map((m) => {
                        const apiOk = hasApiKey(m);
                        return (
                          <label
                            key={m.name}
                            className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-all ${
                              selectedModules.has(m.name)
                                ? 'border-spider-500/50 bg-spider-600/10'
                                : 'border-transparent hover:bg-dark-700/30'
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={selectedModules.has(m.name)}
                              onChange={() => toggleModule(m.name)}
                              className="rounded border-dark-600 bg-dark-700 text-spider-500 focus:ring-spider-500/30"
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-sm text-white font-medium">{m.name.replace('sfp_', '')}</span>
                                {!apiOk && (
                                  <span className="text-yellow-500" title="API key required">
                                    <Lock className="h-3 w-3" />
                                  </span>
                                )}
                                {apiOk && m.opts && Object.keys(m.opts).some(
                                  (k) => k.toLowerCase().includes('api_key'),
                                ) && (
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
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Launch */}
      <div className="card animate-fade-in-up flex items-center justify-between" style={{ animationDelay: '150ms' }}>
        <div className="text-sm text-dark-400">
          {tab === 'usecase' && useCase === 'all' ? (
            <span>All available modules will be used</span>
          ) : (
            <span>{effectiveModules.length} module(s) selected</span>
          )}
        </div>
        <button
          className="btn-primary text-base px-8 py-3"
          disabled={!target.trim() || createMut.isPending}
          onClick={handleSubmit}
        >
          {createMut.isPending ? (
            <><Loader2 className="h-5 w-5 animate-spin" /> Starting...</>
          ) : (
            <><Radar className="h-5 w-5" /> Launch Scan</>
          )}
        </button>
      </div>

      {toast && <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} />}
    </div>
  );
}
