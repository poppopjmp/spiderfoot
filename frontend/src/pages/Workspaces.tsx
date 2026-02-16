import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { workspaceApi, scanApi, agentsApi, formatEpoch, type Workspace, type WorkspaceTarget, type Scan } from '../lib/api';
import { Briefcase, Plus, Trash2, Target, Copy, CheckCircle2, FolderOpen, Clock, Edit2, Radar, Link2, Unlink, Brain, FileText, Sparkles, Edit3, Save, Loader2, AlertTriangle, BarChart3, Shield, MapPin } from 'lucide-react';
import { useState, useRef, useEffect, useCallback } from 'react';
import { StatusBadge, Toast, Tabs, ConfirmDialog, ModalShell, type ToastType } from '../components/ui';
import { Link } from 'react-router-dom';

type WorkspaceTab = 'overview' | 'targets' | 'scans' | 'correlations' | 'geomap' | 'report';

/* Map user-friendly labels to SpiderFoot internal type names */
const TARGET_TYPES = [
  { label: 'Auto-detect', value: '' },
  { label: 'Domain', value: 'INTERNET_NAME' },
  { label: 'IP Address', value: 'IP_ADDRESS' },
  { label: 'IPv6 Address', value: 'IPV6_ADDRESS' },
  { label: 'Subnet', value: 'NETBLOCK_OWNER' },
  { label: 'Email', value: 'EMAILADDR' },
  { label: 'Phone', value: 'PHONE_NUMBER' },
  { label: 'Username', value: 'USERNAME' },
  { label: 'Human Name', value: 'HUMAN_NAME' },
  { label: 'Bitcoin Address', value: 'BITCOIN_ADDRESS' },
  { label: 'ASN', value: 'BGP_AS_OWNER' },
];

function detectTargetType(target: string): string {
  const t = target.trim();
  if (!t) return '';
  if (/^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,62}$/.test(t)) return 'BITCOIN_ADDRESS';
  if (/^(0x)?[0-9a-fA-F]{40}$/.test(t)) return 'BITCOIN_ADDRESS';
  if (/^(\d{1,3}\.){3}\d{1,3}(\/\d+)?$/.test(t)) {
    return t.includes('/') ? 'NETBLOCK_OWNER' : 'IP_ADDRESS';
  }
  if (/^[a-f0-9:]+$/i.test(t) && t.includes(':')) return 'IPV6_ADDRESS';
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t)) return 'EMAILADDR';
  if (/^(\+?\d[\d\s-]{6,})$/.test(t)) return 'PHONE_NUMBER';
  if (/^AS\d+$/i.test(t)) return 'BGP_AS_OWNER';
  if (/^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(t)) return 'INTERNET_NAME';
  if (/^"[^"]+"$/.test(t) || /^@?[a-zA-Z0-9_]{1,30}$/.test(t)) return 'USERNAME';
  if (/\s/.test(t)) return 'HUMAN_NAME';
  return 'INTERNET_NAME';
}

export default function WorkspacesPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [showImportScans, setShowImportScans] = useState(false);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({ name: '', description: '' });
  const [editForm, setEditForm] = useState({ name: '', description: '' });
  const [targetForm, setTargetForm] = useState({ target: '', target_type: '' });
  const [toast, setToast] = useState<{ type: ToastType; message: string } | null>(null);
  const [confirm, setConfirm] = useState<{
    title: string; message: string; action: () => void; danger?: boolean;
  } | null>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('overview');

  const workspaceTabs = [
    { key: 'overview' as const, label: 'Overview', icon: BarChart3 },
    { key: 'targets' as const, label: 'Targets', icon: Target },
    { key: 'scans' as const, label: 'Scans', icon: Radar },
    { key: 'correlations' as const, label: 'Correlations', icon: Shield },
    { key: 'geomap' as const, label: 'GeoMap', icon: MapPin },
    { key: 'report' as const, label: 'AI Report', icon: Brain },
  ];

  const { data: workspacesData, isLoading } = useQuery({
    queryKey: ['workspaces'],
    queryFn: () => workspaceApi.list(),
  });

  const workspaces: Workspace[] = workspacesData?.items ?? [];

  const { data: workspaceDetail } = useQuery({
    queryKey: ['workspace', selectedWorkspace],
    queryFn: () => workspaceApi.get(selectedWorkspace!),
    enabled: !!selectedWorkspace,
  });

  const { data: targets } = useQuery({
    queryKey: ['workspace-targets', selectedWorkspace],
    queryFn: () => workspaceApi.targets(selectedWorkspace!),
    enabled: !!selectedWorkspace,
  });

  const { data: summary } = useQuery({
    queryKey: ['workspace-summary', selectedWorkspace],
    queryFn: () => workspaceApi.summary(selectedWorkspace!),
    enabled: !!selectedWorkspace,
  });

  /* Fetch scans list to show workspace-associated scans */
  const { data: scansData } = useQuery({
    queryKey: ['scans', { page: 1, page_size: 200 }],
    queryFn: () => scanApi.list({ page: 1, page_size: 200 }),
  });
  const allScans: Scan[] = scansData?.items ?? [];

  const createMutation = useMutation({
    mutationFn: workspaceApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      setShowCreate(false);
      setCreateForm({ name: '', description: '' });
      setToast({ type: 'success', message: 'Workspace created' });
    },
    onError: () => {
      setToast({ type: 'error', message: 'Failed to create workspace' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => workspaceApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      if (selectedWorkspace) setSelectedWorkspace(null);
      setToast({ type: 'success', message: 'Workspace deleted' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to delete workspace' }),
  });

  const cloneMutation = useMutation({
    mutationFn: (id: string) => workspaceApi.clone(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      setToast({ type: 'success', message: 'Workspace cloned' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to clone workspace' }),
  });

  const setActiveMutation = useMutation({
    mutationFn: (id: string) => workspaceApi.setActive(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      setToast({ type: 'success', message: 'Workspace set as active' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to set active workspace' }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; description?: string } }) =>
      workspaceApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      queryClient.invalidateQueries({ queryKey: ['workspace', selectedWorkspace] });
      setShowEdit(false);
      setToast({ type: 'success', message: 'Workspace updated' });
    },
  });

  const addTargetMutation = useMutation({
    mutationFn: (data: { target: string; target_type: string }) =>
      workspaceApi.addTarget(selectedWorkspace!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-targets', selectedWorkspace] });
      queryClient.invalidateQueries({ queryKey: ['workspace-summary', selectedWorkspace] });
      setTargetForm({ target: '', target_type: '' });
      setToast({ type: 'success', message: 'Target added' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to add target. Check the target value and type.' }),
  });

  const deleteTargetMutation = useMutation({
    mutationFn: (targetId: string) =>
      workspaceApi.deleteTarget(selectedWorkspace!, targetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-targets', selectedWorkspace] });
      queryClient.invalidateQueries({ queryKey: ['workspace-summary', selectedWorkspace] });
      setToast({ type: 'success', message: 'Target removed' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to remove target' }),
  });

  const multiScanMutation = useMutation({
    mutationFn: (modules: string[]) =>
      workspaceApi.multiScan(selectedWorkspace!, modules),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-summary', selectedWorkspace] });
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      setShowImportScans(false);
      setToast({ type: 'success', message: 'Workspace scan launched! Scans will appear below once started.' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to launch workspace scan' }),
  });

  const linkScanMutation = useMutation({
    mutationFn: (scanId: string) =>
      workspaceApi.linkScan(selectedWorkspace!, scanId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace', selectedWorkspace] });
      queryClient.invalidateQueries({ queryKey: ['workspace-summary', selectedWorkspace] });
      setToast({ type: 'success', message: 'Scan linked to workspace' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to link scan' }),
  });

  const unlinkScanMutation = useMutation({
    mutationFn: (scanId: string) =>
      workspaceApi.unlinkScan(selectedWorkspace!, scanId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace', selectedWorkspace] });
      queryClient.invalidateQueries({ queryKey: ['workspace-summary', selectedWorkspace] });
      setToast({ type: 'success', message: 'Scan unlinked from workspace' });
    },
    onError: () => setToast({ type: 'error', message: 'Failed to unlink scan' }),
  });

  const targetList: WorkspaceTarget[] = targets?.items ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-foreground">Workspaces</h1>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> New Workspace
        </button>
      </div>

      {/* Create Dialog */}
      {showCreate && (
        <ModalShell title="Create Workspace" onClose={() => setShowCreate(false)}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-dark-300 mb-1">Workspace Name</label>
              <input className="input-field w-full" value={createForm.name} onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })} placeholder="e.g. Project Alpha" />
            </div>
            <div>
              <label className="block text-sm text-dark-300 mb-1">Description</label>
              <textarea className="input-field w-full h-20" value={createForm.description} onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })} placeholder="Describe this workspace..." />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
              <button className="btn-primary" disabled={!createForm.name || createMutation.isPending} onClick={() => createMutation.mutate(createForm)}>
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </ModalShell>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Workspace List */}
        <div className="lg:col-span-1 space-y-3">
          {isLoading && <p className="text-dark-400">Loading workspaces...</p>}
          {workspaces.map((w) => (
            <div
              key={w.workspace_id}
              className={`card cursor-pointer transition-colors border ${
                selectedWorkspace === w.workspace_id
                  ? 'border-spider-600 bg-dark-800/80'
                  : 'border-transparent hover:border-dark-600'
              }`}
              onClick={() => setSelectedWorkspace(w.workspace_id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-spider-600/20 rounded-lg">
                    <Briefcase className="h-5 w-5 text-spider-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">{w.name}</h3>
                    <p className="text-xs text-dark-400">{w.description || 'No description'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    className="text-dark-400 hover:text-dark-200 p-1"
                    title="Edit"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedWorkspace(w.workspace_id);
                      setEditForm({ name: w.name, description: w.description || '' });
                      setShowEdit(true);
                    }}
                  >
                    <Edit2 className="h-4 w-4" />
                  </button>
                  <button
                    className="text-green-400 hover:text-green-300 p-1"
                    title="Set as active"
                    onClick={(e) => { e.stopPropagation(); setActiveMutation.mutate(w.workspace_id); }}
                  >
                    <CheckCircle2 className="h-4 w-4" />
                  </button>
                  <button
                    className="text-blue-400 hover:text-blue-300 p-1"
                    title="Clone"
                    onClick={(e) => { e.stopPropagation(); cloneMutation.mutate(w.workspace_id); }}
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                  <button
                    className="text-red-400 hover:text-red-300 p-1"
                    title="Delete"
                    onClick={(e) => { e.stopPropagation(); setConfirm({ title: 'Delete Workspace', message: `Permanently delete "${w.name}"? This cannot be undone.`, action: () => { deleteMutation.mutate(w.workspace_id); setConfirm(null); }, danger: true }); }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
              <div className="flex gap-3 mt-2 text-xs text-dark-500">
                <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {formatEpoch(w.created_time)}</span>
                {w.target_count != null && (
                  <span>{w.target_count} targets</span>
                )}
                {w.scan_count != null && (
                  <span>{w.scan_count} scans</span>
                )}
              </div>
            </div>
          ))}
          {!isLoading && workspaces.length === 0 && (
            <div className="card text-center py-8">
              <FolderOpen className="h-12 w-12 text-dark-600 mx-auto mb-3" />
              <p className="text-dark-400">No workspaces yet. Create one to get started.</p>
            </div>
          )}
        </div>

        {/* Workspace Detail */}
        <div className="lg:col-span-2">
          {selectedWorkspace ? (
            <div className="space-y-6">
              {/* Workspace Header + Actions */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h2 className="text-xl font-bold text-foreground">
                    {workspaces.find((w) => w.workspace_id === selectedWorkspace)?.name || 'Workspace'}
                  </h2>
                  <p className="text-sm text-dark-400 mt-0.5">
                    {workspaces.find((w) => w.workspace_id === selectedWorkspace)?.description || 'No description'}
                  </p>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <button className="btn-secondary text-sm" onClick={() => {
                    const w = workspaces.find((ws) => ws.workspace_id === selectedWorkspace);
                    if (w) { setEditForm({ name: w.name, description: w.description || '' }); setShowEdit(true); }
                  }}>
                    <Edit2 className="h-3.5 w-3.5" /> Edit
                  </button>
                  <button className="btn-secondary text-sm" onClick={() => {
                    if (targetList.length === 0) {
                      setToast({ type: 'error', message: 'Add targets first' });
                      return;
                    }
                    const mods: string[] = [];
                    multiScanMutation.mutate(mods);
                  }} disabled={targetList.length === 0 || multiScanMutation.isPending}>
                    <Radar className="h-3.5 w-3.5" /> {multiScanMutation.isPending ? 'Launching...' : 'Launch Scan'}
                  </button>
                </div>
              </div>

              {/* Summary Stats - always visible */}
              {summary && (() => {
                const stats = summary?.summary?.statistics ?? summary;
                return (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="card">
                    <p className="text-sm text-dark-400">Targets</p>
                    <p className="text-2xl font-bold text-foreground">{stats.target_count ?? targetList.length}</p>
                  </div>
                  <div className="card">
                    <p className="text-sm text-dark-400">Scans</p>
                    <p className="text-2xl font-bold text-foreground">{stats.scan_count ?? 0}</p>
                  </div>
                  <div className="card">
                    <p className="text-sm text-dark-400">Events</p>
                    <p className="text-2xl font-bold text-foreground">{stats.total_events ?? 0}</p>
                  </div>
                  <div className="card">
                    <p className="text-sm text-dark-400">Correlations</p>
                    <p className="text-2xl font-bold text-foreground">{stats.correlation_count ?? 0}</p>
                  </div>
                </div>
                );
              })()}

              {/* Tab Bar */}
              <Tabs<WorkspaceTab>
                tabs={workspaceTabs}
                active={activeTab}
                onChange={setActiveTab}
              />

              {/* Tab Content */}
              {activeTab === 'overview' && (
                <div className="space-y-6 animate-fade-in">
                  {/* Workspace Info */}
                  {workspaceDetail && (
                    <div className="card">
                      <h2 className="text-lg font-semibold text-foreground mb-3">Workspace Details</h2>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-dark-400">ID</p>
                          <p className="text-foreground font-mono text-xs">{workspaceDetail.workspace_id}</p>
                        </div>
                        <div>
                          <p className="text-dark-400">Created</p>
                          <p className="text-foreground">{formatEpoch(workspaceDetail.created_time)}</p>
                        </div>
                        {workspaceDetail.modified_time && (
                          <div>
                            <p className="text-dark-400">Last Modified</p>
                            <p className="text-foreground">{formatEpoch(workspaceDetail.modified_time)}</p>
                          </div>
                        )}
                        <div>
                          <p className="text-dark-400">Targets</p>
                          <p className="text-foreground">{targetList.length}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Quick target overview */}
                  {targetList.length > 0 && (
                    <div className="card">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold text-foreground">Targets ({targetList.length})</h3>
                        <button className="text-spider-400 hover:text-spider-300 text-xs" onClick={() => setActiveTab('targets')}>Manage &rarr;</button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {targetList.slice(0, 10).map((t) => (
                          <span key={t.target_id} className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-dark-700/50 rounded-lg text-xs text-dark-300 font-mono">
                            <Target className="h-3 w-3 text-spider-400" />
                            {t.value}
                          </span>
                        ))}
                        {targetList.length > 10 && <span className="text-xs text-dark-500 py-1">+{targetList.length - 10} more</span>}
                      </div>
                    </div>
                  )}

                  {/* Quick linked scans overview */}
                  {(() => {
                    const linkedScanIds = new Set(
                      (workspaceDetail?.scans as Array<{ scan_id: string }> ?? []).map((s) => s.scan_id)
                    );
                    const implicitScans = allScans.filter(
                      (s) => !linkedScanIds.has(s.scan_id) && targetList.some((t) => s.target === t.value)
                    );
                    const linkedScans = allScans.filter((s) => linkedScanIds.has(s.scan_id));
                    const displayScans = [...linkedScans, ...implicitScans];
                    if (displayScans.length === 0) return null;
                    return (
                      <div className="card">
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-sm font-semibold text-foreground">Recent Scans ({displayScans.length})</h3>
                          <button className="text-spider-400 hover:text-spider-300 text-xs" onClick={() => setActiveTab('scans')}>View all &rarr;</button>
                        </div>
                        <div className="space-y-2">
                          {displayScans.slice(0, 5).map((s) => (
                            <Link key={s.scan_id} to={`/scans/${s.scan_id}`} className="flex items-center justify-between p-2.5 bg-dark-700/50 rounded-lg hover:bg-dark-700 transition-colors">
                              <div className="flex items-center gap-2 min-w-0">
                                <Radar className="h-3.5 w-3.5 text-spider-400 flex-shrink-0" />
                                <span className="text-sm text-foreground truncate">{s.name || 'Untitled'}</span>
                              </div>
                              <StatusBadge status={s.status ?? ''} />
                            </Link>
                          ))}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              )}

              {activeTab === 'targets' && (
                <div className="card animate-fade-in">
                  <h2 className="text-lg font-semibold text-foreground mb-4">Targets</h2>

                  {/* Add Target */}
                  <div className="flex flex-col sm:flex-row gap-3 mb-4">
                    <input
                      className="input-field flex-1 min-w-0"
                      value={targetForm.target}
                      onChange={(e) => setTargetForm({ ...targetForm, target: e.target.value })}
                      placeholder="e.g. example.com, 192.168.1.0/24"
                    />
                    <select
                      className="input-field sm:w-48"
                      value={targetForm.target_type}
                      onChange={(e) => setTargetForm({ ...targetForm, target_type: e.target.value })}
                    >
                      {TARGET_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                    <button
                      className="btn-primary flex items-center gap-2"
                      disabled={!targetForm.target || addTargetMutation.isPending}
                      onClick={() => {
                        const resolvedType = targetForm.target_type || detectTargetType(targetForm.target);
                        if (!resolvedType) {
                          setToast({ type: 'error', message: 'Cannot detect target type. Please select one.' });
                          return;
                        }
                        addTargetMutation.mutate({ target: targetForm.target.trim(), target_type: resolvedType });
                      }}
                    >
                      <Plus className="h-4 w-4" /> Add
                    </button>
                  </div>

                  {/* Target list */}
                  {targetList.length > 0 ? (
                    <div className="space-y-2">
                      {targetList.map((t) => (
                        <div key={t.target_id} className="flex items-center justify-between p-3 bg-dark-700/50 rounded-lg">
                          <div className="flex items-center gap-3">
                            <Target className="h-4 w-4 text-spider-400" />
                            <span className="text-foreground text-sm font-mono">{t.value}</span>
                            <span className="badge badge-info text-xs">{t.type}</span>
                          </div>
                          <button
                            className="text-red-400 hover:text-red-300"
                            onClick={() => deleteTargetMutation.mutate(t.target_id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-dark-400 text-sm">No targets in this workspace.</p>
                  )}
                </div>
              )}

              {activeTab === 'scans' && (
                <div className="card animate-fade-in">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-foreground">Linked Scans</h2>
                    <button
                      className="btn-secondary text-sm flex items-center gap-2"
                      onClick={() => setShowImportScans(true)}
                    >
                      <Link2 className="h-3.5 w-3.5" /> Link Scan
                    </button>
                  </div>

                  {(() => {
                    const linkedScanIds = new Set(
                      (workspaceDetail?.scans as Array<{ scan_id: string }> ?? []).map((s) => s.scan_id)
                    );
                    const implicitScans = allScans.filter(
                      (s) => !linkedScanIds.has(s.scan_id) && targetList.some((t) => s.target === t.value)
                    );
                    const linkedScans = allScans.filter((s) => linkedScanIds.has(s.scan_id));
                    const displayScans = [...linkedScans, ...implicitScans];

                    if (displayScans.length === 0) {
                      return (
                        <p className="text-dark-400 text-sm">
                          No scans linked. Use "Link Scan" to associate existing scans for cross-scan correlation.
                        </p>
                      );
                    }

                    return (
                      <div className="space-y-2 max-h-[500px] overflow-y-auto">
                        {displayScans.map((s) => (
                          <div
                            key={s.scan_id}
                            className="flex items-center justify-between p-3 bg-dark-700/50 rounded-lg hover:bg-dark-700 transition-colors"
                          >
                            <Link
                              to={`/scans/${s.scan_id}`}
                              className="flex items-center gap-3 min-w-0 flex-1"
                            >
                              <Radar className="h-4 w-4 text-spider-400 flex-shrink-0" />
                              <div className="min-w-0">
                                <p className="text-sm text-foreground truncate">{s.name || 'Untitled'}</p>
                                <p className="text-xs text-dark-500 font-mono">{s.target}</p>
                              </div>
                            </Link>
                            <div className="flex items-center gap-3">
                              <StatusBadge status={s.status ?? ''} />
                              <span className="text-xs text-dark-500 whitespace-nowrap">{formatEpoch(s.started ?? 0)}</span>
                              {linkedScanIds.has(s.scan_id) ? (
                                <button
                                  className="text-red-400 hover:text-red-300 p-1"
                                  title="Unlink scan from workspace"
                                  onClick={(e) => {
                                    e.preventDefault();
                                    unlinkScanMutation.mutate(s.scan_id);
                                  }}
                                >
                                  <Unlink className="h-3.5 w-3.5" />
                                </button>
                              ) : (
                                <button
                                  className="text-spider-400 hover:text-spider-300 p-1"
                                  title="Link scan to workspace"
                                  onClick={(e) => {
                                    e.preventDefault();
                                    linkScanMutation.mutate(s.scan_id);
                                  }}
                                >
                                  <Link2 className="h-3.5 w-3.5" />
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                </div>
              )}

              {activeTab === 'correlations' && (
                <div className="card animate-fade-in">
                  <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Shield className="h-5 w-5 text-spider-400" /> Cross-Scan Correlations
                  </h2>
                  <p className="text-sm text-dark-400 mb-4">
                    Aggregate correlation findings across all linked scans in this workspace.
                  </p>
                  {(() => {
                    const stats = summary?.summary?.statistics ?? summary;
                    const correlationCount = stats?.correlation_count ?? 0;
                    const correlations = summary?.summary?.correlations ?? [];
                    if (correlationCount === 0 && correlations.length === 0) {
                      return (
                        <div className="text-center py-12">
                          <Shield className="h-12 w-12 text-dark-600 mx-auto mb-3" />
                          <p className="text-dark-400">No correlations found yet.</p>
                          <p className="text-dark-500 text-sm mt-1">Run scans and enable correlation rules to discover cross-scan insights.</p>
                        </div>
                      );
                    }
                    const riskColor: Record<string, string> = {
                      CRITICAL: 'corr-text-critical',
                      HIGH: 'corr-text-high',
                      MEDIUM: 'corr-text-medium',
                      LOW: 'corr-text-low',
                      INFO: 'corr-text-info',
                    };
                    const riskBg: Record<string, string> = {
                      CRITICAL: 'corr-card-high',
                      HIGH: 'corr-card-high',
                      MEDIUM: 'corr-card-medium',
                      LOW: 'corr-card-low',
                      INFO: 'corr-card-info',
                    };
                    return (
                      <div className="space-y-4">
                        {/* Severity cards */}
                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                          <div className="p-3 bg-dark-700/50 rounded-lg text-center">
                            <p className="text-xl font-bold text-foreground">{correlationCount || correlations.length}</p>
                            <p className="text-xs text-dark-400">Total</p>
                          </div>
                          <div className="p-3 corr-card-high rounded-lg text-center">
                            <p className="text-xl font-bold corr-text-critical">{stats?.critical_count ?? 0}</p>
                            <p className="text-xs text-dark-400">Critical</p>
                          </div>
                          <div className="p-3 corr-card-high rounded-lg text-center">
                            <p className="text-xl font-bold corr-text-high">{stats?.high_count ?? 0}</p>
                            <p className="text-xs text-dark-400">High</p>
                          </div>
                          <div className="p-3 corr-card-medium rounded-lg text-center">
                            <p className="text-xl font-bold corr-text-medium">{stats?.medium_count ?? 0}</p>
                            <p className="text-xs text-dark-400">Medium</p>
                          </div>
                          <div className="p-3 corr-card-low rounded-lg text-center">
                            <p className="text-xl font-bold corr-text-low">{(stats?.low_count ?? 0) + (stats?.info_count ?? 0)}</p>
                            <p className="text-xs text-dark-400">Low/Info</p>
                          </div>
                        </div>

                        {/* Correlation list */}
                        {correlations.length > 0 && (
                          <div className="space-y-2 max-h-[500px] overflow-y-auto">
                            {correlations.map((c: any, i: number) => (
                              <Link
                                key={c.id || i}
                                to={`/scans/${c.scan_id}`}
                                className={`flex items-center justify-between p-3 ${riskBg[c.rule_risk] || 'bg-dark-700/50'} rounded-lg hover:brightness-110 transition-all`}
                              >
                                <div className="flex items-center gap-3 min-w-0">
                                  <Shield className={`h-4 w-4 flex-shrink-0 ${riskColor[c.rule_risk] || 'text-dark-400'}`} />
                                  <div className="min-w-0">
                                    <p className="text-sm text-foreground truncate">{c.title || c.rule_name}</p>
                                    <p className="text-xs text-dark-500">{c.rule_id} &middot; {c.event_count ?? 0} events</p>
                                  </div>
                                </div>
                                <span className={`text-xs font-medium ${riskColor[c.rule_risk] || 'text-dark-400'} flex-shrink-0 ml-2`}>
                                  {c.rule_risk}
                                </span>
                              </Link>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              )}

              {activeTab === 'geomap' && (
                <div className="card animate-fade-in">
                  <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                    <MapPin className="h-5 w-5 text-spider-400" /> Geographic Distribution
                  </h2>
                  <p className="text-sm text-dark-400 mb-4">
                    Aggregate geographic data from all linked scans.
                  </p>
                  {(() => {
                    const stats = summary?.summary?.statistics ?? summary;
                    const geoCount = stats?.geo_count ?? stats?.country_count ?? 0;
                    if (geoCount === 0) {
                      return (
                        <div className="text-center py-12">
                          <MapPin className="h-12 w-12 text-dark-600 mx-auto mb-3" />
                          <p className="text-dark-400">No geographic data available yet.</p>
                          <p className="text-dark-500 text-sm mt-1">Run scans to discover geographic intelligence about your targets.</p>
                        </div>
                      );
                    }
                    return (
                      <div className="space-y-3">
                        <div className="p-4 bg-dark-700/50 rounded-lg">
                          <p className="text-lg font-bold text-foreground">{geoCount} locations</p>
                          <p className="text-xs text-dark-400">discovered across workspace scans</p>
                        </div>
                        <p className="text-xs text-dark-500">
                          Open individual scans to view the interactive GeoMap.
                        </p>
                      </div>
                    );
                  })()}
                </div>
              )}

              {activeTab === 'report' && selectedWorkspace && (
                <div className="animate-fade-in">
                  <WorkspaceReportCard workspaceId={selectedWorkspace} workspace={workspaces.find((w) => w.workspace_id === selectedWorkspace)} summary={summary} scanIds={(workspaceDetail?.scans as Array<{ scan_id: string }> ?? []).map((s) => s.scan_id)} />
                </div>
              )}
            </div>
          ) : (
            <div className="card text-center py-16">
              <Briefcase className="h-16 w-16 text-dark-600 mx-auto mb-4" />
              <p className="text-dark-400 text-lg">Select a workspace to view details</p>
              <p className="text-dark-500 text-sm mt-1">Or create a new one to get started</p>
            </div>
          )}
        </div>
      </div>

      {/* Edit Workspace Dialog */}
      {showEdit && selectedWorkspace && (
        <ModalShell title="Edit Workspace" onClose={() => setShowEdit(false)}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-dark-300 mb-1">Workspace Name</label>
              <input className="input-field w-full" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm text-dark-300 mb-1">Description</label>
              <textarea className="input-field w-full h-20" value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button className="btn-secondary" onClick={() => setShowEdit(false)}>Cancel</button>
              <button className="btn-primary" disabled={!editForm.name || updateMutation.isPending} onClick={() => updateMutation.mutate({ id: selectedWorkspace, data: editForm })}>
                {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </ModalShell>
      )}

      {/* Link Existing Scan / Launch Workspace Scan Dialog */}
      {showImportScans && selectedWorkspace && (
        <ModalShell title="Link Scans to Workspace" onClose={() => setShowImportScans(false)}>
          <p className="text-sm text-dark-400 mb-4">
            Select existing scans to link for cross-scan correlation analysis.
          </p>

          {/* Available scans to link */}
          <div className="space-y-2 max-h-[350px] overflow-y-auto mb-4">
            {allScans.length > 0 ? (
              (() => {
                const linkedIds = new Set(
                  (workspaceDetail?.scans as Array<{ scan_id: string }> ?? []).map((s) => s.scan_id)
                );
                const unlinkable = allScans.filter((s) => !linkedIds.has(s.scan_id));
                if (unlinkable.length === 0) {
                  return <p className="text-dark-400 text-sm py-4 text-center">All scans are already linked.</p>;
                }
                return unlinkable.map((s) => (
                  <div key={s.scan_id} className="flex items-center justify-between p-3 bg-dark-700/50 rounded-lg">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <Radar className="h-4 w-4 text-spider-400 flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm text-foreground truncate">{s.name || 'Untitled'}</p>
                        <p className="text-xs text-dark-500 font-mono">{s.target}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={s.status ?? ''} />
                      <button
                        className="btn-secondary text-xs px-2 py-1 flex items-center gap-1"
                        onClick={() => linkScanMutation.mutate(s.scan_id)}
                        disabled={linkScanMutation.isPending}
                      >
                        <Link2 className="h-3 w-3" /> Link
                      </button>
                    </div>
                  </div>
                ));
              })()
            ) : (
              <p className="text-dark-400 text-sm py-4 text-center">No scans available. Run a scan first.</p>
            )}
          </div>

          <div className="flex justify-end">
            <button className="btn-secondary" onClick={() => setShowImportScans(false)}>Done</button>
          </div>
        </ModalShell>
      )}

      {/* Confirm Dialog */}
      {confirm && (
        <ConfirmDialog
          open
          title={confirm.title}
          message={confirm.message}
          danger={confirm.danger}
          confirmLabel={confirm.danger ? 'Delete' : 'Confirm'}
          onConfirm={confirm.action}
          onCancel={() => setConfirm(null)}
        />
      )}

      {toast && <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} />}
    </div>
  );
}

/* ── Workspace AI Report Card ─────────────────────────────── */
function WorkspaceReportCard({ workspaceId, workspace, summary, scanIds }: {
  workspaceId: string;
  workspace?: Workspace;
  summary?: Record<string, unknown>;
  scanIds?: string[];
}) {
  const [reportContent, setReportContent] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const editorRef = useRef<HTMLTextAreaElement>(null);

  const storageKey = `sf_ws_report_${workspaceId}`;
  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) setReportContent(saved);
    else setReportContent('');
  }, [storageKey]);

  const generateMut = useMutation({
    mutationFn: async () => {
      return agentsApi.report({
        scan_ids: scanIds ?? [],
        target: workspace?.name ?? 'Workspace',
        scan_name: workspace?.name ?? 'Workspace Report',
        stats: {
          workspace_id: workspaceId,
          workspace_name: workspace?.name,
          ...((summary as Record<string, unknown>) ?? {}),
        },
      });
    },
    onSuccess: (data) => {
      // Response: { agent, result_type, data: { report: "markdown..." }, confidence, ... }
      const reportData = data?.data ?? data;
      const md = reportData?.report ?? reportData?.content ?? reportData?.markdown ?? JSON.stringify(data, null, 2);
      setReportContent(md);
      localStorage.setItem(storageKey, md);
    },
  });

  const generateClientReport = useCallback(() => {
    const stats = (summary as Record<string, unknown>)?.summary as Record<string, unknown> ?? summary ?? {};
    const statsObj = (stats?.statistics ?? stats) as Record<string, number>;
    const lines = [
      `# Workspace Report: ${workspace?.name ?? 'Unknown'}`,
      '',
      `**Workspace ID:** \`${workspaceId}\``,
      `**Description:** ${workspace?.description || 'N/A'}`,
      `**Generated:** ${new Date().toLocaleString()}`,
      '',
      '---',
      '',
      '## Overview',
      '',
      `- **Targets:** ${statsObj?.target_count ?? 'N/A'}`,
      `- **Scans:** ${statsObj?.scan_count ?? 'N/A'}`,
      `- **Total Events:** ${statsObj?.total_events ?? 'N/A'}`,
      `- **Correlations:** ${statsObj?.correlation_count ?? 'N/A'}`,
      '',
      '## Analysis',
      '',
      '> *Edit this section to add your cross-scan threat analysis and insights.*',
      '',
      '## Recommendations',
      '',
      '1. Review all high-risk correlation findings across linked scans.',
      '2. Identify patterns across multiple targets in this workspace.',
      '3. Escalate critical findings to the security team.',
      '',
      '---',
      '*Report generated by SpiderFoot Workspace Analyzer*',
    ];
    const md = lines.join('\n');
    setReportContent(md);
    localStorage.setItem(storageKey, md);
  }, [workspace, workspaceId, summary, storageKey]);

  const startEditing = () => {
    setEditContent(reportContent);
    setIsEditing(true);
    setTimeout(() => editorRef.current?.focus(), 50);
  };

  const saveEdit = () => {
    setReportContent(editContent);
    localStorage.setItem(storageKey, editContent);
    setIsEditing(false);
  };

  /* Simple inline markdown renderer — supports h1-h3, hr, blockquote, lists, tables, code blocks, paragraphs */
  const renderSimpleMd = (md: string) => {
    const lines = md.split('\n');
    const elements: React.ReactNode[] = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];

      // Code blocks (``` ... ```)
      if (line.trim().startsWith('```')) {
        const codeLines: string[] = [];
        i++;
        while (i < lines.length && !lines[i].trim().startsWith('```')) {
          codeLines.push(lines[i]);
          i++;
        }
        i++; // skip closing ```
        elements.push(
          <pre key={elements.length} className="bg-dark-900 border border-dark-700 rounded-lg p-3 my-2 overflow-x-auto text-xs font-mono text-dark-300 whitespace-pre-wrap">
            {codeLines.join('\n')}
          </pre>
        );
        continue;
      }

      // Tables (| ... |)
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        const tableLines: string[] = [];
        while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
          tableLines.push(lines[i]);
          i++;
        }
        if (tableLines.length >= 2) {
          const headerCells = tableLines[0].split('|').filter(c => c.trim() !== '').map(c => c.trim());
          // skip separator row (row 1) and parse data rows
          const dataRows = tableLines.slice(2).map(row =>
            row.split('|').filter(c => c.trim() !== '').map(c => c.trim())
          );
          elements.push(
            <div key={elements.length} className="overflow-x-auto my-2">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-dark-700">
                    {headerCells.map((cell, ci) => (
                      <th key={ci} className="px-3 py-1.5 text-left text-dark-300 font-semibold" dangerouslySetInnerHTML={{ __html: inlineFmt(cell) }} />
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dataRows.map((row, ri) => (
                    <tr key={ri} className="border-b border-dark-700/50">
                      {row.map((cell, ci) => (
                        <td key={ci} className="px-3 py-1.5 text-dark-400" dangerouslySetInnerHTML={{ __html: inlineFmt(cell) }} />
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
          continue;
        }
      }

      // Headings
      const hMatch = line.match(/^(#{1,3})\s+(.*)/);
      if (hMatch) {
        const lvl = hMatch[1].length;
        const cls = lvl === 1 ? 'text-xl font-bold text-foreground mt-6 mb-2 border-b border-dark-700 pb-2' : lvl === 2 ? 'text-lg font-bold text-foreground mt-5 mb-2' : 'text-base font-semibold text-foreground mt-4 mb-1';
        elements.push(<div key={elements.length} className={cls} dangerouslySetInnerHTML={{ __html: inlineFmt(hMatch[2]) }} />);
        i++;
        continue;
      }

      // Horizontal rule
      if (/^---+$/.test(line.trim())) {
        elements.push(<hr key={elements.length} className="border-dark-700/50 my-4" />);
        i++;
        continue;
      }

      // Blockquote
      if (line.trim().startsWith('>')) {
        elements.push(<blockquote key={elements.length} className="border-l-2 border-spider-500 pl-3 text-dark-400 italic text-sm my-1" dangerouslySetInnerHTML={{ __html: inlineFmt(line.replace(/^>\s*/, '')) }} />);
        i++;
        continue;
      }

      // List items
      const liMatch = line.match(/^(\d+\.|[-*])\s+(.*)/);
      if (liMatch) {
        elements.push(<li key={elements.length} className="text-sm text-dark-300 ml-4 list-disc" dangerouslySetInnerHTML={{ __html: inlineFmt(liMatch[2]) }} />);
        i++;
        continue;
      }

      // Empty line
      if (line.trim() === '') {
        elements.push(<div key={elements.length} className="h-2" />);
        i++;
        continue;
      }

      // Paragraph
      elements.push(<p key={elements.length} className="text-sm text-dark-300 leading-relaxed" dangerouslySetInnerHTML={{ __html: inlineFmt(line) }} />);
      i++;
    }

    return elements;
  };

  const inlineFmt = (t: string) => t
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-foreground font-semibold">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="bg-dark-700 px-1 py-0.5 rounded text-spider-400 text-xs font-mono">$1</code>');

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <Brain className="h-5 w-5 text-spider-400" /> AI Report
        </h2>
        <div className="flex items-center gap-2">
          {reportContent && !isEditing && (
            <button className="btn-secondary text-xs" onClick={startEditing}>
              <Edit3 className="h-3 w-3" /> Edit
            </button>
          )}
          {isEditing && (
            <>
              <button className="btn-secondary text-xs" onClick={() => setIsEditing(false)}>Cancel</button>
              <button className="btn-primary text-xs" onClick={saveEdit}><Save className="h-3 w-3" /> Save</button>
            </>
          )}
          <button className="btn-primary text-xs" onClick={() => generateMut.mutate()} disabled={generateMut.isPending}>
            {generateMut.isPending ? <><Loader2 className="h-3 w-3 animate-spin" /> Generating CTI Report...</> : <><Sparkles className="h-3 w-3" /> AI Report</>}
          </button>
          {!reportContent && (
            <button className="btn-secondary text-xs" onClick={generateClientReport}>
              <FileText className="h-3 w-3" /> Quick
            </button>
          )}
        </div>
      </div>

      {generateMut.isError && (
        <div className="flex items-center gap-2 mb-3 p-2 bg-yellow-900/10 border border-yellow-700/30 rounded-lg text-xs text-yellow-300">
          <AlertTriangle className="h-3.5 w-3.5" />
          <span>AI report generation failed: {(generateMut.error as Error)?.message ?? 'Unknown error'}. <button className="underline" onClick={generateClientReport}>Use quick report</button></span>
        </div>
      )}

      {isEditing ? (
        <textarea
          ref={editorRef}
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
          className="w-full bg-dark-900 text-dark-200 font-mono text-xs p-3 focus:outline-none rounded-lg resize-y border border-dark-700"
          style={{ minHeight: '400px' }}
          spellCheck={false}
        />
      ) : reportContent ? (
        <div className="max-h-[80vh] overflow-y-auto pr-2">
          {renderSimpleMd(reportContent)}
        </div>
      ) : (
        <div className="text-center py-8 text-dark-500">
          <Brain className="h-10 w-10 mx-auto mb-2 opacity-30" />
          <p className="text-sm">No report yet. Generate one to get started.</p>
        </div>
      )}
    </div>
  );
}