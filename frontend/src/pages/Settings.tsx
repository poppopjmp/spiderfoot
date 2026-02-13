import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { configApi, type Module } from '../lib/api';
import {
  Settings as SettingsIcon, Save, RefreshCw, Search,
  ChevronDown, ChevronRight, AlertTriangle, CheckCircle, Key,
} from 'lucide-react';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [editedValues, setEditedValues] = useState<Record<string, string>>({});
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Load current config
  const { data: configData, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: configApi.get,
  });

  // Load modules (for module-specific settings)
  const { data: modulesData } = useQuery({
    queryKey: ['config-modules'],
    queryFn: configApi.modules,
  });

  // Config summary
  const { data: summaryData } = useQuery({
    queryKey: ['config-summary'],
    queryFn: configApi.summary,
  });

  const config = configData?.config ?? {};
  const version = configData?.version ?? '';
  const modules = modulesData?.modules ?? [];

  // Group settings by section prefix
  const sections: Record<string, { key: string; value: unknown }[]> = {};
  for (const [key, value] of Object.entries(config)) {
    // Settings like _socks_type, __logging, sfp_module:setting
    let section = 'General';
    if (key.startsWith('sfp_')) {
      const parts = key.split(':');
      section = parts[0]; // module name
    } else if (key.startsWith('__')) {
      section = 'Internal';
    } else if (key.startsWith('_')) {
      section = 'Global';
    }
    if (!sections[section]) sections[section] = [];
    sections[section].push({ key, value });
  }

  // Sort sections: Global first, then modules
  const sortedSections = Object.entries(sections).sort(([a], [b]) => {
    if (a === 'General') return -1;
    if (b === 'General') return 1;
    if (a === 'Global') return -1;
    if (b === 'Global') return 1;
    if (a === 'Internal') return 1;
    if (b === 'Internal') return -1;
    return a.localeCompare(b);
  });

  // Filter by search
  const filteredSections = search
    ? sortedSections
        .map(([name, items]) => [
          name,
          items.filter(
            (item) =>
              item.key.toLowerCase().includes(search.toLowerCase()) ||
              String(item.value).toLowerCase().includes(search.toLowerCase()),
          ),
        ] as [string, { key: string; value: unknown }[]])
        .filter(([, items]) => items.length > 0)
    : sortedSections;

  const toggleSection = (name: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  };

  const handleValueChange = (key: string, value: string) => {
    setEditedValues((prev) => ({ ...prev, [key]: value }));
  };

  // Save mutation
  const saveConfig = useMutation({
    mutationFn: (options: Record<string, unknown>) => configApi.update(options),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
      setEditedValues({});
      setSaveMessage({ type: 'success', text: 'Settings saved successfully.' });
      setTimeout(() => setSaveMessage(null), 3000);
    },
    onError: (err: Error) => {
      setSaveMessage({ type: 'error', text: `Failed to save: ${err.message}` });
    },
  });

  const reloadConfig = useMutation({
    mutationFn: configApi.reload,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
      queryClient.invalidateQueries({ queryKey: ['config-summary'] });
      setSaveMessage({ type: 'success', text: 'Configuration reloaded.' });
      setTimeout(() => setSaveMessage(null), 3000);
    },
  });

  const handleSave = () => {
    if (Object.keys(editedValues).length === 0) return;
    saveConfig.mutate(editedValues);
  };

  const hasChanges = Object.keys(editedValues).length > 0;

  // Find module description
  const getModuleInfo = (name: string): Module | undefined =>
    modules.find((m) => m.name === name);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          {version && <p className="text-dark-400 text-sm mt-1">Version: {version}</p>}
        </div>
        <div className="flex items-center gap-3">
          <button
            className="btn-secondary flex items-center gap-2"
            onClick={() => reloadConfig.mutate()}
            disabled={reloadConfig.isPending}
          >
            <RefreshCw className={`h-4 w-4 ${reloadConfig.isPending ? 'animate-spin' : ''}`} />
            Reload
          </button>
          <button
            className="btn-primary flex items-center gap-2"
            onClick={handleSave}
            disabled={!hasChanges || saveConfig.isPending}
          >
            <Save className="h-4 w-4" />
            {saveConfig.isPending ? 'Saving...' : `Save${hasChanges ? ` (${Object.keys(editedValues).length})` : ''}`}
          </button>
        </div>
      </div>

      {/* Save message */}
      {saveMessage && (
        <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 text-sm ${
          saveMessage.type === 'success'
            ? 'bg-green-900/30 text-green-400 border border-green-800'
            : 'bg-red-900/30 text-red-400 border border-red-800'
        }`}>
          {saveMessage.type === 'success' ? <CheckCircle className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
          {saveMessage.text}
        </div>
      )}

      {/* Summary cards */}
      {summaryData?.sections && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {Object.entries(summaryData.sections as Record<string, object>)
            .slice(0, 8)
            .map(([name]) => (
              <div
                key={name}
                className="card py-3 px-4 cursor-pointer hover:border-spider-600 transition-colors"
                onClick={() => {
                  setSearch(name);
                  setExpandedSections(new Set([name]));
                }}
              >
                <p className="text-white font-medium text-sm capitalize">{name}</p>
                <p className="text-dark-400 text-xs">
                  {sections[name]?.length ?? 0} settings
                </p>
              </div>
            ))}
        </div>
      )}

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-400" />
        <input
          className="input-field pl-10"
          placeholder="Search settings (key or value)..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Settings sections */}
      {isLoading ? (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin h-6 w-6 border-2 border-spider-500 border-t-transparent rounded-full" />
        </div>
      ) : filteredSections.length > 0 ? (
        <div className="space-y-2">
          {filteredSections.map(([sectionName, items]) => {
            const moduleInfo = sectionName.startsWith('sfp_') ? getModuleInfo(sectionName) : undefined;
            const isExpanded = expandedSections.has(sectionName);

            return (
              <div key={sectionName} className="border border-dark-700 rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleSection(sectionName)}
                  className="w-full flex items-center justify-between p-4 bg-dark-800 hover:bg-dark-700/80 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 text-dark-400" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-dark-400" />
                    )}
                    <div className="text-left">
                      <span className="text-white font-medium text-sm">
                        {sectionName.startsWith('sfp_') ? (
                          <>
                            <span className="font-mono">{sectionName}</span>
                            {moduleInfo && (
                              <span className="text-dark-400 font-normal ml-2">
                                — {moduleInfo.description || moduleInfo.descr}
                              </span>
                            )}
                          </>
                        ) : (
                          sectionName
                        )}
                      </span>
                    </div>
                  </div>
                  <span className="text-dark-400 text-xs">{items.length} setting{items.length !== 1 ? 's' : ''}</span>
                </button>

                {isExpanded && (
                  <div className="divide-y divide-dark-700/50">
                    {items.map((item) => {
                      const currentValue = editedValues[item.key] ?? String(item.value ?? '');
                      const isEdited = item.key in editedValues;
                      const isApiKey = item.key.toLowerCase().includes('api_key') ||
                                       item.key.toLowerCase().includes('apikey') ||
                                       item.key.toLowerCase().includes('password') ||
                                       item.key.toLowerCase().includes('secret');

                      return (
                        <div key={item.key} className="p-4 hover:bg-dark-700/20">
                          <div className="flex items-start gap-4">
                            <div className="flex-1 min-w-0">
                              <label className="text-sm text-dark-200 flex items-center gap-2">
                                <span className="font-mono text-xs">{item.key}</span>
                                {isApiKey && <Key className="h-3 w-3 text-yellow-500" />}
                                {isEdited && <span className="text-spider-400 text-xs">(modified)</span>}
                              </label>
                              <input
                                type={isApiKey ? 'password' : 'text'}
                                className={`input-field mt-1 text-sm ${isEdited ? 'border-spider-500' : ''}`}
                                value={currentValue}
                                onChange={(e) => handleValueChange(item.key, e.target.value)}
                                placeholder="(empty)"
                              />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="card text-center py-12">
          <SettingsIcon className="h-12 w-12 mx-auto text-dark-600 mb-3" />
          <p className="text-dark-400">
            {search ? `No settings match "${search}"` : 'No configuration loaded. Is the API running?'}
          </p>
        </div>
      )}
    </div>
  );
}
