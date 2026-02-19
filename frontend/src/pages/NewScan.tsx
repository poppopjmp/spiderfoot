import { useState, useMemo } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  dataApi, scanApi, type Module, type ScanCreateRequest, type ScanProfile,
} from '../lib/api';
import {
  Radar, Lock, Unlock, Zap,
  ShieldCheck, FileText, Loader2, Upload, X, Layers,
} from 'lucide-react';
import { PageHeader, Tabs, SearchInput, Toast, type ToastType } from '../components/ui';

type TabKey = 'usecase' | 'profile' | 'data' | 'module';

const USE_CASES = [
  { key: 'all', label: 'All Modules', desc: 'Run every available module for maximum coverage' },
  { key: 'quick', label: 'Quick Scan', desc: 'Fast scan with essential passive modules (~20 modules)' },
  { key: 'footprint', label: 'Footprint', desc: 'Discover the target\'s full digital footprint' },
  { key: 'investigate', label: 'Investigate', desc: 'Deep dive into a specific target' },
  { key: 'passive', label: 'Passive Only', desc: 'Only passive/non-intrusive modules' },
];

/* Curated set of fast, reliable passive modules for quick scans */
const QUICK_SCAN_MODULES = [
  'sfp_dnsresolve', 'sfp_dnsbrute', 'sfp_dnscommonsrv', 'sfp_dnstxt',
  'sfp_hackertarget', 'sfp_ipinfo', 'sfp_whois',
  'sfp_sslcert', 'sfp_webframework', 'sfp_httpheaders', 'sfp_spider',
  'sfp_crossref', 'sfp_pageinfo', 'sfp_similar', 'sfp_names',
  'sfp_email', 'sfp_geoinfo', 'sfp_portscan_tcp', 'sfp_socialprofiles',
  'sfp__stor_db',
];

export default function NewScanPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>('usecase');
  const [target, setTarget] = useState('');
  const [scanName, setScanName] = useState('');
  const [useCase, setUseCase] = useState('all');
  const [selectedProfile, setSelectedProfile] = useState<string | null>(null);
  const [selectedModules, setSelectedModules] = useState<Set<string>>(new Set());
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [moduleSearch, setModuleSearch] = useState('');
  const [toast, setToast] = useState<{ type: ToastType; message: string } | null>(null);
  const [files, setFiles] = useState<File[]>([]);

  /* Data queries */
  const { data: modulesData } = useQuery({
    queryKey: ['modules', { page: 1, page_size: 500 }],
    queryFn: () => dataApi.modules({ page: 1, page_size: 500 }),
  });
  const { data: entityData } = useQuery({
    queryKey: ['entity-types'],
    queryFn: dataApi.entityTypes,
  });
  const { data: profilesData } = useQuery({
    queryKey: ['scan-profiles'],
    queryFn: () => scanApi.profiles(),
  });

  const profiles: ScanProfile[] = profilesData?.profiles ?? [];

  const modules: Module[] = modulesData?.items ?? [];
  const entityTypes: string[] = entityData?.entity_types ?? [];

  /* Target type detection */
  const detectedType = useMemo(() => {
    const t = target.trim();
    if (!t) return null;
    if (/^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,62}$/.test(t)) return 'Bitcoin Address';
    if (/^(0x)?[0-9a-fA-F]{40}$/.test(t)) return 'Ethereum Address';
    if (/^(\d{1,3}\.){3}\d{1,3}(\/\d+)?$/.test(t)) return 'IP Address';
    if (/^[a-f0-9:]+$/i.test(t) && t.includes(':')) return 'IPv6 Address';
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t)) return 'Email Address';
    if (/^(\+?\d[\d\s-]{6,})$/.test(t)) return 'Phone Number';
    if (/^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(t)) return 'Domain Name';
    if (/^AS\d+$/i.test(t)) return 'ASN';
    if (/^"[^"]+"$/.test(t) || /^@?[a-zA-Z0-9_]{1,30}$/.test(t)) return 'Username';
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
        (Array.isArray(m.group) ? m.group.join(' ') : (m.group || '')).toLowerCase().includes(q) ||
        (Array.isArray(m.cats) ? m.cats.join(' ') : '').toLowerCase().includes(q),
    );
  }, [modules, moduleSearch]);

  /* Group modules by category */
  const grouped = useMemo(() => {
    const map = new Map<string, Module[]>();
    filteredModules.forEach((m) => {
      const cat = (Array.isArray(m.cats) && m.cats.length > 0) ? m.cats[0] : (m.category || 'Other');
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(m);
    });
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [filteredModules]);

  /* Determine which modules to use */
  const effectiveModules = useMemo(() => {
    if (tab === 'module') return [...selectedModules];
    if (tab === 'profile' && selectedProfile) {
      const p = profiles.find((pr) => pr.name === selectedProfile);
      return p?.modules ?? [];
    }
    if (tab === 'data') {
      // Find modules that produce any of the selected entity types
      return modules
        .filter((m) => m.provides?.some((p) => selectedTypes.has(p)))
        .map((m) => m.name);
    }
    if (tab === 'usecase') {
      if (useCase === 'all') return [];
      if (useCase === 'quick') return QUICK_SCAN_MODULES;
      const ucLower = useCase.toLowerCase();
      return modules
        .filter((m) => {
          const groups = Array.isArray(m.group) ? m.group : [];
          return groups.some((g) => g.toLowerCase() === ucLower);
        })
        .map((m) => m.name);
    }
    return [];
  }, [tab, selectedModules, selectedProfile, profiles, selectedTypes, useCase, modules]);

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
    if (!target.trim()) {
      setToast({ type: 'error', message: 'Please enter a target' });
      return;
    }
    const payload: ScanCreateRequest = {
      name: scanName || `Scan of ${target}`,
      target: target.trim(),
    };
    if (tab === 'module' && selectedModules.size > 0) {
      payload.modules = [...selectedModules];
    } else if (tab === 'profile' && selectedProfile) {
      payload.profile = selectedProfile;
    } else if (tab === 'data' && selectedTypes.size > 0) {
      payload.type_filter = [...selectedTypes];
    } else if (tab === 'usecase' && useCase === 'quick') {
      payload.modules = QUICK_SCAN_MODULES;
    } else if (tab === 'usecase' && useCase !== 'all') {
      payload.modules = effectiveModules;
    }
    // When useCase === 'all' or no selection, send no modules/type_filter → server uses all modules
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
    // opts is { api_key: "", daysback: 30, ... } — raw values, not objects
    return !Object.entries(m.opts).some(
      ([k, v]) => (k.toLowerCase().includes('api_key') || k.toLowerCase().includes('apikey'))
        && (v === '' || v === null || v === undefined),
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader title="New Scan" subtitle="Configure and launch an OSINT reconnaissance scan" />

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
        {/* Left Column: Target & Config */}
        <div className="xl:col-span-2 space-y-6">
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

        {/* Document Upload — matches CherryPy "Attach Documents" */}
        <div className="mt-4">
          <label className="section-label mb-2 block">Attach Documents (optional)</label>
          <p className="text-xs text-dark-500 mb-2">Upload PDF, DOCX, XLSX, TXT and 1000+ other formats for IOC extraction via Apache Tika.</p>
          <div
            className="border-2 border-dashed border-dark-600 rounded-lg p-6 text-center hover:border-dark-500 transition-colors cursor-pointer"
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              const dropped = Array.from(e.dataTransfer.files);
              setFiles((prev) => [...prev, ...dropped]);
            }}
            onClick={() => {
              const input = document.createElement('input');
              input.type = 'file';
              input.multiple = true;
              input.onchange = () => {
                if (input.files) setFiles((prev) => [...prev, ...Array.from(input.files!)]);
              };
              input.click();
            }}
          >
            <Upload className="h-6 w-6 text-dark-500 mx-auto mb-2" />
            <p className="text-sm text-dark-400">Drag & drop files here, or click to browse</p>
          </div>
          {files.length > 0 && (
            <div className="mt-2 space-y-1">
              {files.map((f, i) => (
                <div key={`${f.name}-${i}`} className="flex items-center justify-between px-3 py-1.5 bg-dark-700/50 rounded text-sm">
                  <span className="text-dark-300 truncate">{f.name} <span className="text-dark-500">({(f.size / 1024).toFixed(1)} KB)</span></span>
                  <button onClick={(e) => { e.stopPropagation(); setFiles((prev) => prev.filter((_, j) => j !== i)); }} className="text-dark-500 hover:text-red-400">
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Launch Button (also in left column) */}
      <div className="card animate-fade-in-up flex items-center justify-between" style={{ animationDelay: '150ms' }}>
        <div className="text-sm text-dark-400">
          {tab === 'usecase' && useCase === 'all' ? (
            <span>All available modules will be used</span>
          ) : tab === 'profile' && selectedProfile ? (
            <span>Profile: {profiles.find((p) => p.name === selectedProfile)?.display_name ?? selectedProfile} ({effectiveModules.length} modules)</span>
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
        </div>

        {/* Right Column: Module Selection */}
        <div className="xl:col-span-3">
      {/* Module Selection */}
      <div className="card animate-fade-in-up" style={{ animationDelay: '100ms' }}>
        <label className="section-label mb-4 block">Module Selection</label>

        <Tabs<TabKey>
          tabs={[
            { key: 'usecase', label: 'By Use Case', icon: Zap },
            { key: 'profile', label: 'By Profile', icon: Layers },
            { key: 'data', label: 'By Required Data', icon: FileText },
            { key: 'module', label: 'By Module', icon: ShieldCheck, count: tab === 'module' ? selectedModules.size : undefined },
          ]}
          active={tab}
          onChange={setTab}
        />

        <div className="mt-5">
          {/* By Profile */}
          {tab === 'profile' && (
            <div className="space-y-3 animate-fade-in">
              <p className="text-sm text-dark-400 mb-3">
                Select a pre-configured scan profile. Each profile includes a curated set of modules for a specific purpose.
              </p>
              {profiles.length === 0 ? (
                <p className="text-sm text-dark-500 italic">No scan profiles available</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {profiles.map((p) => (
                    <button
                      key={p.name}
                      onClick={() => setSelectedProfile(p.name)}
                      className={`p-4 rounded-xl border text-left transition-all ${
                        selectedProfile === p.name
                          ? 'border-spider-500 bg-spider-600/10 ring-1 ring-spider-500/30'
                          : 'border-dark-700 hover:border-dark-600 hover:bg-dark-700/30'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full border-2 flex items-center justify-center ${
                          selectedProfile === p.name ? 'border-spider-500' : 'border-dark-500'
                        }`}>
                          {selectedProfile === p.name && <div className="w-1.5 h-1.5 rounded-full bg-spider-500" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-foreground">{p.display_name}</p>
                          <p className="text-xs text-dark-400 mt-0.5">{p.description}</p>
                          <div className="flex items-center gap-2 mt-1.5">
                            <span className="badge bg-dark-700 text-dark-300 text-[10px] px-1.5 py-0">{p.module_count} modules</span>
                            {p.category && (
                              <span className="badge bg-spider-900/30 text-spider-400 text-[10px] px-1.5 py-0">{p.category}</span>
                            )}
                            {p.tags?.slice(0, 2).map((t) => (
                              <span key={t} className="badge bg-dark-700/50 text-dark-400 text-[10px] px-1.5 py-0">{t}</span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

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
                      <p className="text-sm font-medium text-foreground">{uc.label}</p>
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
                        ? 'border-spider-500/50 bg-spider-600/10 text-foreground'
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
                                <span className="text-sm text-foreground font-medium">{m.name.replace('sfp_', '')}</span>
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
                                {(m.labels?.includes('slow') || m.flags?.includes('slow')) && (
                                  <span className="badge bg-yellow-900/30 text-yellow-400 text-[9px] px-1 py-0">Slow</span>
                                )}
                                {(m.labels?.includes('invasive') || m.flags?.includes('invasive')) && (
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
        </div>
      </div>

      {toast && <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} />}
    </div>
  );
}
