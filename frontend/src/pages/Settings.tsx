import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  configApi, dataApi, type Module,
} from '../lib/api';
import {
  Settings as SettingsIcon, Globe, Key, Upload, Download,
  RotateCcw, Save, Eye, EyeOff, AlertTriangle,
  Loader2,
} from 'lucide-react';
import {
  PageHeader, SearchInput, Toast, ConfirmDialog, EmptyState,
  Skeleton,
  type ToastType,
} from '../components/ui';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [activeSection, setActiveSection] = useState('__global__');
  const [search, setSearch] = useState('');
  const [toast, setToast] = useState<{ type: ToastType; message: string } | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, string>>({});
  const [showPasswords, setShowPasswords] = useState<Set<string>>(new Set());

  /* Queries */
  const { data: configData, isLoading: configLoading } = useQuery({
    queryKey: ['config'],
    queryFn: ({ signal }) => configApi.get(signal),
  });
  const { data: modulesData } = useQuery({
    queryKey: ['modules', { page: 1, page_size: 500 }],
    queryFn: ({ signal }) => dataApi.modules({ page: 1, page_size: 500 }, signal),
  });

  const config = configData?.config ?? {};
  const modules: Module[] = modulesData?.items ?? [];

  /* Global options: config keys that are not internal */
  const globalOptions = useMemo(() => {
    return Object.entries(config).filter(([k]) => !k.startsWith('__'));
  }, [config]);

  /* Sidebar sections: global + one per module that has opts */
  const sections = useMemo(() => {
    const items: { key: string; label: string; count: number; hasApiKey: boolean }[] = [
      { key: '__global__', label: 'Global Settings', count: globalOptions.length, hasApiKey: false },
    ];
    const sortedModules = [...modules]
      .filter((m) => m.opts && Object.keys(m.opts).length > 0)
      .sort((a, b) => a.name.localeCompare(b.name));

    for (const mod of sortedModules) {
      const optKeys = Object.keys(mod.opts ?? {});
      const hasApiKey = optKeys.some(
        (k) => k.toLowerCase().includes('api_key') || k.toLowerCase().includes('apikey'),
      );
      items.push({
        key: mod.name,
        label: mod.name.replace(/^sfp_/, ''),
        count: optKeys.length,
        hasApiKey,
      });
    }
    if (search) {
      const q = search.toLowerCase();
      return items.filter((i) => i.label.toLowerCase().includes(q) || i.key.toLowerCase().includes(q));
    }
    return items;
  }, [globalOptions, modules, search]);

  const activeModule = modules.find((m) => m.name === activeSection);

  /* Current section options */
  const currentOptions = useMemo(() => {
    if (activeSection === '__global__') {
      return globalOptions.map(([k, v]) => ({ key: k, value: v, description: '' }));
    }
    if (!activeModule?.opts) return [];
    const descs = activeModule.optdescs ?? {};
    return Object.entries(activeModule.opts).map(([k, v]) => ({
      key: `${activeModule.name}:${k}`,
      value: v,
      description: descs[k] || '',
    }));
  }, [activeSection, globalOptions, activeModule]);

  /* Save — global options via PATCH /config, module opts via PATCH /modules/{name}/options */
  const saveMut = useMutation({
    mutationFn: async (edited: Record<string, string>) => {
      const globalOpts: Record<string, unknown> = {};
      const moduleOpts = new Map<string, Record<string, unknown>>();

      for (const [key, val] of Object.entries(edited)) {
        if (key.includes(':')) {
          const [mod, ...rest] = key.split(':');
          const optKey = rest.join(':');
          if (!moduleOpts.has(mod)) moduleOpts.set(mod, {});
          moduleOpts.get(mod)![optKey] = val;
        } else {
          globalOpts[key] = val;
        }
      }

      const promises: Promise<unknown>[] = [];
      if (Object.keys(globalOpts).length > 0) {
        promises.push(configApi.update(globalOpts));
      }
      for (const [mod, opts] of moduleOpts) {
        promises.push(configApi.updateModuleOptions(mod, opts));
      }
      await Promise.all(promises);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
      queryClient.invalidateQueries({ queryKey: ['modules'] });
      setEditedValues({});
      setToast({ type: 'success', message: 'Settings saved' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to save settings' }),
  });

  /* Import/Export */
  const handleExport = async () => {
    try {
      const data = await configApi.exportConfig();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'spiderfoot-config.json';
      a.click();
      URL.revokeObjectURL(url);
      setToast({ type: 'success', message: 'Configuration exported' });
    } catch {
      setToast({ type: 'error', message: 'Export failed' });
    }
  };

  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        const parsed = JSON.parse(text);
        await configApi.importConfig(parsed);
        queryClient.invalidateQueries({ queryKey: ['config'] });
        setToast({ type: 'success', message: 'Configuration imported' });
      } catch {
        setToast({ type: 'error', message: 'Import failed — invalid JSON' });
      }
    };
    input.click();
  };

  /* Reset */
  const handleReset = async () => {
    try {
      await configApi.reload();
      queryClient.invalidateQueries({ queryKey: ['config'] });
      queryClient.invalidateQueries({ queryKey: ['modules'] });
      setConfirmReset(false);
      setEditedValues({});
      setToast({ type: 'success', message: 'Reset to factory defaults' });
    } catch {
      setToast({ type: 'error', message: 'Reset failed' });
    }
  };

  const handleSave = () => {
    if (Object.keys(editedValues).length === 0) return;
    saveMut.mutate(editedValues);
  };

  const togglePassword = (key: string) => {
    const next = new Set(showPasswords);
    next.has(key) ? next.delete(key) : next.add(key);
    setShowPasswords(next);
  };

  const isApiKey = (key: string) => {
    const k = key.toLowerCase();
    return k.includes('api_key') || k.includes('apikey') || k.includes('password') || k.includes('secret');
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Configure SpiderFoot options and API keys">
        <div className="flex gap-2">
          <button className="btn-secondary text-sm" onClick={handleImport}>
            <Upload className="h-3.5 w-3.5" /> Import
          </button>
          <button className="btn-secondary text-sm" onClick={handleExport}>
            <Download className="h-3.5 w-3.5" /> Export
          </button>
          <button className="btn-ghost text-sm text-red-400" onClick={() => setConfirmReset(true)}>
            <RotateCcw className="h-3.5 w-3.5" /> Reset
          </button>
        </div>
      </PageHeader>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar */}
        <div className="card p-0 overflow-hidden h-fit lg:sticky lg:top-4">
          <div className="p-3 border-b border-dark-700/50">
            <SearchInput value={search} onChange={setSearch} placeholder="Find section..." className="w-full" />
          </div>
          <div className="overflow-y-auto max-h-[600px]">
            {sections.map((s) => (
              <button
                key={s.key}
                onClick={() => setActiveSection(s.key)}
                className={`w-full flex items-center justify-between px-3 py-2.5 text-left text-sm transition-colors ${
                  activeSection === s.key
                    ? 'bg-spider-600/10 text-spider-400 border-l-2 border-spider-500'
                    : 'text-dark-300 hover:bg-dark-700/30 border-l-2 border-transparent'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  {s.key === '__global__' ? (
                    <Globe className="h-3.5 w-3.5 flex-shrink-0 text-dark-500" />
                  ) : s.hasApiKey ? (
                    <Key className="h-3.5 w-3.5 flex-shrink-0 text-yellow-500" />
                  ) : (
                    <SettingsIcon className="h-3.5 w-3.5 flex-shrink-0 text-dark-600" />
                  )}
                  <span className="truncate">{s.label}</span>
                </div>
                <span className="text-xs text-dark-600 tabular-nums">{s.count}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Options Panel */}
        <div className="lg:col-span-3 space-y-4">
          {/* Module info header */}
          {activeSection !== '__global__' && activeModule && (
            <div className="card animate-fade-in">
              <h3 className="text-sm font-semibold text-foreground">{activeModule.name}</h3>
              <p className="text-xs text-dark-400 mt-1">
                {activeModule.descr || activeModule.description || 'No description available.'}
              </p>
              {activeModule.provides && activeModule.provides.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {activeModule.provides.slice(0, 6).map((p) => (
                    <span key={p} className="badge badge-info text-[10px]">{p}</span>
                  ))}
                  {activeModule.provides.length > 6 && (
                    <span className="text-xs text-dark-500">+{activeModule.provides.length - 6} more</span>
                  )}
                </div>
              )}
              {activeModule.group && activeModule.group.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {activeModule.group.map((g) => (
                    <span key={g} className="badge bg-dark-600 text-dark-200 text-[10px]">{g}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Options */}
          <div className="card animate-fade-in">
            {configLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="space-y-2">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-10 w-full" />
                  </div>
                ))}
              </div>
            ) : currentOptions.length > 0 ? (
              <div className="space-y-5">
                {currentOptions.map((opt) => {
                  const optKey = opt.key;
                  const val = opt.value;
                  const optDesc = opt.description;
                  const editedVal = editedValues[optKey];
                  const currentVal = editedVal ?? String(val ?? '');
                  const shortKey = optKey.includes(':') ? optKey.split(':').slice(1).join(':') : optKey;
                  const isSensitive = isApiKey(shortKey);
                  const isHidden = isSensitive && !showPasswords.has(optKey);

                  // Detect value type for appropriate control
                  const rawVal = val as unknown;
                  const isBool = rawVal === true || rawVal === false || currentVal === 'true' || currentVal === 'false' || currentVal === 'True' || currentVal === 'False';
                  const isNumber = !isBool && !isSensitive && /^\d+(\.\d+)?$/.test(String(rawVal ?? ''));
                  const isMultiLine = !isBool && !isNumber && String(val ?? '').includes(',') && String(val ?? '').length > 40;

                  return (
                    <div key={optKey}>
                      <div className="flex items-center gap-2 mb-1">
                        <label className="text-sm text-dark-300 font-medium">{shortKey}</label>
                        {isSensitive && (
                          <button
                            onClick={() => togglePassword(optKey)}
                            className="text-dark-500 hover:text-dark-300 transition-colors"
                          >
                            {isHidden ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                          </button>
                        )}
                        {isSensitive && !currentVal && (
                          <span className="text-yellow-500 text-[10px] flex items-center gap-0.5">
                            <AlertTriangle className="h-3 w-3" /> Not set
                          </span>
                        )}
                        {editedVal !== undefined && (
                          <span className="text-spider-400 text-[10px]">Modified</span>
                        )}
                      </div>
                      {optDesc && (
                        <p className="text-xs text-dark-500 mb-1.5">{optDesc}</p>
                      )}

                      {/* Boolean toggle */}
                      {isBool ? (
                        <button
                          onClick={() => {
                            const boolVal = currentVal === 'true' || currentVal === 'True';
                            setEditedValues((prev) => ({ ...prev, [optKey]: boolVal ? 'false' : 'true' }));
                          }}
                          className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${
                            (currentVal === 'true' || currentVal === 'True') ? 'bg-spider-500' : 'bg-dark-600'
                          }`}
                        >
                          <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform ${
                            (currentVal === 'true' || currentVal === 'True') ? 'translate-x-6' : 'translate-x-1'
                          }`} />
                        </button>
                      ) : isNumber ? (
                        <input
                          type="number"
                          className="input-field text-sm font-mono w-40"
                          value={currentVal}
                          onChange={(e) => {
                            setEditedValues((prev) => ({ ...prev, [optKey]: e.target.value }));
                          }}
                        />
                      ) : isMultiLine ? (
                        <textarea
                          className="input-field text-sm font-mono h-24 resize-y"
                          value={currentVal}
                          onChange={(e) => {
                            setEditedValues((prev) => ({ ...prev, [optKey]: e.target.value }));
                          }}
                          placeholder="Comma-separated values..."
                        />
                      ) : (
                        <input
                          type={isHidden ? 'password' : 'text'}
                          className="input-field text-sm font-mono"
                          value={currentVal}
                          onChange={(e) => {
                            setEditedValues((prev) => ({ ...prev, [optKey]: e.target.value }));
                          }}
                          placeholder={isSensitive ? 'Enter API key...' : ''}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                icon={SettingsIcon}
                title="No options"
                description="This section has no configurable options."
              />
            )}
          </div>

          {/* Save Bar */}
          {Object.keys(editedValues).length > 0 && (
            <div className="sticky bottom-4 card flex items-center justify-between animate-fade-in-up border border-spider-600/30">
              <p className="text-sm text-dark-300">
                {Object.keys(editedValues).length} unsaved change(s)
              </p>
              <div className="flex gap-2">
                <button className="btn-secondary" onClick={() => setEditedValues({})}>Discard</button>
                <button className="btn-primary" onClick={handleSave} disabled={saveMut.isPending}>
                  {saveMut.isPending ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Saving...</>
                  ) : (
                    <><Save className="h-4 w-4" /> Save Changes</>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Dialogs */}
      <ConfirmDialog
        open={confirmReset}
        title="Reset to Factory Defaults"
        message="This will reset ALL settings to their factory defaults. API keys and custom configurations will be lost."
        confirmLabel="Reset Everything"
        danger
        onConfirm={handleReset}
        onCancel={() => setConfirmReset(false)}
      />

      {toast && <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} />}
    </div>
  );
}
