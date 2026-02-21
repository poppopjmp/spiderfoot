/**
 * SpiderFoot API Key Management Page
 *
 * Create, list, revoke, and delete API keys.
 * Users can manage their own keys; admins can manage all keys.
 * Supports fine-grained permissions: allowed modules/endpoints, rate limits.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Key,
  Plus,
  Trash2,
  Shield,
  CheckCircle,
  Search,
  X,
  AlertCircle,
  ChevronDown,
  Clock,
  Copy,
  Eye,
  EyeOff,
  Ban,
} from 'lucide-react';
import { clsx } from 'clsx';
import api from '../lib/api';
import { getErrorMessage } from '../lib/errors';
import { ModalShell } from '../components/ui';
import { useAuthStore } from '../lib/auth';

// ── Types ────────────────────────────────────────────────

interface ApiKeyRecord {
  id: string;
  user_id: string;
  name: string;
  key_prefix: string;
  role: string;
  status: string;
  expires_at: number;
  allowed_modules: string;
  allowed_endpoints: string;
  rate_limit: number;
  last_used: number;
  created_at: number;
  updated_at: number;
  // Only present on creation
  key?: string;
}

const ROLES = ['viewer', 'analyst', 'operator', 'admin'] as const;

const ROLE_BADGE_COLOR: Record<string, string> = {
  admin: 'bg-red-500/15 text-red-400 border-red-500/30',
  operator: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  analyst: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  viewer: 'bg-dark-600/50 text-dark-300 border-dark-600',
};

const STATUS_STYLES: Record<string, { icon: React.ReactNode; color: string }> = {
  active: { icon: <CheckCircle className="h-3.5 w-3.5 text-green-400" />, color: 'text-green-400' },
  revoked: { icon: <Ban className="h-3.5 w-3.5 text-red-400" />, color: 'text-red-400' },
  expired: { icon: <Clock className="h-3.5 w-3.5 text-yellow-400" />, color: 'text-yellow-400' },
};

// ── Helpers ──────────────────────────────────────────────

function formatDate(ts: number): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString();
}

function relativeTime(ts: number): string {
  if (!ts) return 'Never';
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function expiresLabel(ts: number): string {
  if (!ts) return 'Never';
  const diff = ts - Date.now() / 1000;
  if (diff < 0) return 'Expired';
  if (diff < 86400) return `${Math.floor(diff / 3600)}h left`;
  return `${Math.floor(diff / 86400)}d left`;
}

// ── Component ────────────────────────────────────────────

export default function ApiKeysPage() {
  const { user: currentUser, hasPermission } = useAuthStore();
  const isAdmin = hasPermission('user:read');

  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');

  // Modals
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyResult, setNewKeyResult] = useState<ApiKeyRecord | null>(null);
  const [deleteKey, setDeleteKey] = useState<ApiKeyRecord | null>(null);
  const [revokeKey, setRevokeKey] = useState<ApiKeyRecord | null>(null);

  // ── Data fetching ──────────────────────────────────────

  const { data: keys = [], isLoading: loading, error: queryError } = useQuery<ApiKeyRecord[]>({
    queryKey: ['api-keys', isAdmin],
    queryFn: ({ signal }) => {
      const url = isAdmin ? '/api/auth/api-keys' : '/api/auth/api-keys/mine';
      return api.get(url, { signal }).then(r => r.data.items || []);
    },
  });

  // ── Revoke handler ─────────────────────────────────────

  const revokeMutation = useMutation({
    mutationFn: (k: ApiKeyRecord) => api.post(`/api/auth/api-keys/${k.id}/revoke`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
      setRevokeKey(null);
    },
  });

  // ── Delete handler ─────────────────────────────────────

  const deleteMutation = useMutation({
    mutationFn: (k: ApiKeyRecord) => api.delete(`/api/auth/api-keys/${k.id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
      setDeleteKey(null);
    },
  });

  const error = queryError
    ? getErrorMessage(queryError, 'Failed to load API keys')
    : revokeMutation.error
      ? getErrorMessage(revokeMutation.error, 'Failed to revoke key')
      : deleteMutation.error
        ? getErrorMessage(deleteMutation.error, 'Failed to delete key')
        : '';

  // ── Filter ─────────────────────────────────────────────

  const filtered = keys.filter((k) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      k.name.toLowerCase().includes(q) ||
      k.key_prefix.toLowerCase().includes(q) ||
      k.role.toLowerCase().includes(q) ||
      k.status.toLowerCase().includes(q)
    );
  });

  // ── Render ─────────────────────────────────────────────

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-3">
            <Key className="h-7 w-7 text-spider-400" />
            API Keys
          </h1>
          <p className="text-dark-400 text-sm mt-1">
            Generate API keys for programmatic access with fine-grained permissions
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-spider-600 hover:bg-spider-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus className="h-4 w-4" />
          Generate Key
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-500" />
        <input
          type="text"
          placeholder="Search keys..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-10 py-2.5 bg-dark-800 border border-dark-700 rounded-lg text-sm text-foreground placeholder:text-dark-500 focus:outline-none focus:ring-2 focus:ring-spider-500/40 focus:border-spider-500/60"
        />
        {search && (
          <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-500 hover:text-dark-300">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
          <button onClick={() => { revokeMutation.reset(); deleteMutation.reset(); }} className="ml-auto text-red-500 hover:text-red-300">
            <X className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* Table */}
      <div className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-dark-700 text-dark-400 text-left">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Key Prefix</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Permissions</th>
                <th className="px-4 py-3 font-medium">Last Used</th>
                <th className="px-4 py-3 font-medium">Expires</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-dark-500">
                    <div className="flex items-center justify-center gap-2">
                      <div className="animate-spin h-5 w-5 border-2 border-spider-500 border-t-transparent rounded-full" />
                      Loading API keys...
                    </div>
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-dark-500">
                    {search ? 'No keys match your search' : 'No API keys yet. Click "Generate Key" to create one.'}
                  </td>
                </tr>
              ) : (
                filtered.map((k) => {
                  const statusStyle = STATUS_STYLES[k.status] || STATUS_STYLES.active;
                  let modules: string[] = [];
                  if (k.allowed_modules) {
                    try { modules = JSON.parse(k.allowed_modules); } catch { /* malformed */ }
                  }
                  const isExpired = k.expires_at > 0 && k.expires_at < Date.now() / 1000;

                  return (
                    <tr key={k.id} className="border-b border-dark-700/50 hover:bg-dark-750 transition-colors">
                      <td className="px-4 py-3">
                        <p className="text-foreground font-medium">{k.name}</p>
                        <p className="text-dark-500 text-xs">{formatDate(k.created_at)}</p>
                      </td>
                      <td className="px-4 py-3">
                        <code className="text-dark-300 font-mono text-xs bg-dark-900 px-2 py-0.5 rounded">
                          {k.key_prefix}...
                        </code>
                      </td>
                      <td className="px-4 py-3">
                        <span className={clsx(
                          'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border',
                          ROLE_BADGE_COLOR[k.role] || ROLE_BADGE_COLOR.viewer,
                        )}>
                          <Shield className="h-3 w-3" />
                          {k.role}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          {isExpired ? STATUS_STYLES.expired.icon : statusStyle.icon}
                          <span className={clsx('capitalize', isExpired ? 'text-yellow-400' : statusStyle.color)}>
                            {isExpired ? 'expired' : k.status}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="space-y-0.5">
                          {modules.length > 0 ? (
                            <p className="text-xs text-dark-400">
                              {modules.length} module{modules.length !== 1 ? 's' : ''}
                            </p>
                          ) : (
                            <p className="text-xs text-dark-500">All modules</p>
                          )}
                          {k.rate_limit > 0 && (
                            <p className="text-xs text-dark-500">{k.rate_limit} req/min</p>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-dark-400 text-xs">
                        {relativeTime(k.last_used)}
                      </td>
                      <td className="px-4 py-3 text-dark-400 text-xs">
                        {expiresLabel(k.expires_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          {k.status === 'active' && (
                            <button
                              onClick={() => setRevokeKey(k)}
                              className="p-1.5 text-dark-500 hover:text-yellow-400 hover:bg-dark-700 rounded-lg transition-colors"
                              title="Revoke key"
                            >
                              <Ban className="h-3.5 w-3.5" />
                            </button>
                          )}
                          <button
                            onClick={() => setDeleteKey(k)}
                            className="p-1.5 text-dark-500 hover:text-red-400 hover:bg-dark-700 rounded-lg transition-colors"
                            title="Delete key"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modals */}
      {showCreate && (
        <CreateKeyModal
          userRole={currentUser?.role || 'viewer'}
          onClose={() => setShowCreate(false)}
          onCreated={(result) => {
            setShowCreate(false);
            setNewKeyResult(result);
            queryClient.invalidateQueries({ queryKey: ['api-keys'] });
          }}
        />
      )}
      {newKeyResult && (
        <KeyCreatedModal
          apiKey={newKeyResult}
          onClose={() => setNewKeyResult(null)}
        />
      )}
      {revokeKey && (
        <ConfirmModal
          title="Revoke API Key"
          message={<>Are you sure you want to revoke <span className="text-foreground font-medium">{revokeKey.name}</span>? The key will immediately stop working.</>}
          confirmLabel="Revoke"
          confirmClass="bg-yellow-600 hover:bg-yellow-500"
          onConfirm={() => revokeMutation.mutate(revokeKey)}
          onClose={() => setRevokeKey(null)}
        />
      )}
      {deleteKey && (
        <ConfirmModal
          title="Delete API Key"
          message={<>Are you sure you want to permanently delete <span className="text-foreground font-medium">{deleteKey.name}</span>? This cannot be undone.</>}
          confirmLabel="Delete"
          confirmClass="bg-red-600 hover:bg-red-500"
          onConfirm={() => deleteMutation.mutate(deleteKey)}
          onClose={() => setDeleteKey(null)}
        />
      )}
    </div>
  );
}


// ══════════════════════════════════════════════════════════
// Shared UI
// ══════════════════════════════════════════════════════════

function FormField({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-dark-300">{label}</label>
      {children}
      {hint && <p className="text-xs text-dark-500">{hint}</p>}
    </div>
  );
}

const inputClass =
  'w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm text-foreground placeholder:text-dark-500 focus:outline-none focus:ring-2 focus:ring-spider-500/40 focus:border-spider-500/60';

const selectClass =
  'w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-spider-500/40 focus:border-spider-500/60 appearance-none';


// ══════════════════════════════════════════════════════════
// Create API Key Modal
// ══════════════════════════════════════════════════════════

function CreateKeyModal({
  userRole,
  onClose,
  onCreated,
}: {
  userRole: string;
  onClose: () => void;
  onCreated: (key: ApiKeyRecord) => void;
}) {
  const [name, setName] = useState('');
  const [role, setRole] = useState(userRole);
  const [expiresInDays, setExpiresInDays] = useState(90);
  const [rateLimit, setRateLimit] = useState(0);
  const [allowedModules, setAllowedModules] = useState('');
  const [allowedEndpoints, setAllowedEndpoints] = useState('');
  const [error, setError] = useState('');

  // Only show roles up to user's current role
  const roleIndex = ROLES.indexOf(userRole as typeof ROLES[number]);
  const availableRoles = ROLES.slice(0, roleIndex >= 0 ? roleIndex + 1 : 1);

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.post('/api/auth/api-keys', data).then(r => r.data),
    onSuccess: (result: ApiKeyRecord) => onCreated(result),
    onError: (err: unknown) => setError(getErrorMessage(err, 'Failed to create API key')),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Parse module list
    let modulesJson = '';
    if (allowedModules.trim()) {
      try {
        // Accept comma-separated or JSON array
        const mods = allowedModules.includes('[')
          ? JSON.parse(allowedModules)
          : allowedModules.split(',').map((m) => m.trim()).filter(Boolean);
        modulesJson = JSON.stringify(mods);
      } catch {
        setError('Allowed modules must be comma-separated names or a JSON array');
        return;
      }
    }

    let endpointsJson = '';
    if (allowedEndpoints.trim()) {
      try {
        const eps = allowedEndpoints.includes('[')
          ? JSON.parse(allowedEndpoints)
          : allowedEndpoints.split(',').map((e) => e.trim()).filter(Boolean);
        endpointsJson = JSON.stringify(eps);
      } catch {
        setError('Allowed endpoints must be comma-separated patterns or a JSON array');
        return;
      }
    }

    createMutation.mutate({
      name,
      role,
      expires_in_days: expiresInDays,
      rate_limit: rateLimit,
      allowed_modules: modulesJson,
      allowed_endpoints: endpointsJson,
    });
  };

  return (
    <ModalShell title="Generate API Key" onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <FormField label="Key Name" hint="A descriptive name for this key (e.g. 'CI/CD Pipeline', 'Monitoring Script')">
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} required className={inputClass} placeholder="My API Key" />
        </FormField>

        <div className="grid grid-cols-2 gap-4">
          <FormField label="Role" hint="Maximum permission level for this key">
            <div className="relative">
              <select value={role} onChange={(e) => setRole(e.target.value)} className={selectClass}>
                {availableRoles.map((r) => (
                  <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-500 pointer-events-none" />
            </div>
          </FormField>
          <FormField label="Expires In (days)" hint="0 = never expires">
            <input type="number" value={expiresInDays} onChange={(e) => setExpiresInDays(parseInt(e.target.value) || 0)} min={0} className={inputClass} />
          </FormField>
        </div>

        <FormField label="Rate Limit (requests/min)" hint="0 = unlimited">
          <input type="number" value={rateLimit} onChange={(e) => setRateLimit(parseInt(e.target.value) || 0)} min={0} className={inputClass} />
        </FormField>

        <div className="pt-2 border-t border-dark-700/50">
          <p className="text-xs text-dark-500 font-medium uppercase tracking-wider mb-3">Fine-Grained Access Control</p>

          <FormField label="Allowed Modules" hint="Comma-separated module names (empty = all modules accessible). e.g. sfp_dns,sfp_whois,sfp_shodan">
            <textarea
              value={allowedModules}
              onChange={(e) => setAllowedModules(e.target.value)}
              rows={2}
              className={clsx(inputClass, 'font-mono text-xs')}
              placeholder="sfp_dns, sfp_whois, sfp_shodan"
            />
          </FormField>

          <div className="mt-3">
            <FormField label="Allowed API Endpoints" hint="Comma-separated URL patterns (empty = all endpoints). e.g. /api/scans/*, /api/data/*">
              <textarea
                value={allowedEndpoints}
                onChange={(e) => setAllowedEndpoints(e.target.value)}
                rows={2}
                className={clsx(inputClass, 'font-mono text-xs')}
                placeholder="/api/scans/*, /api/data/*"
              />
            </FormField>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-dark-400 hover:text-dark-200 transition-colors">
            Cancel
          </button>
          <button type="submit" disabled={createMutation.isPending || !name.trim()} className="px-4 py-2 bg-spider-600 hover:bg-spider-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">
            {createMutation.isPending ? 'Generating...' : 'Generate Key'}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}


// ══════════════════════════════════════════════════════════
// Key Created Modal (shows the raw key once)
// ══════════════════════════════════════════════════════════

function KeyCreatedModal({ apiKey, onClose }: { apiKey: ApiKeyRecord; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const [revealed, setRevealed] = useState(false);

  const copyKey = () => {
    if (apiKey.key) {
      navigator.clipboard.writeText(apiKey.key).catch(() => {});
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <ModalShell title="API Key Created" onClose={onClose}>
      <div className="space-y-4">
        <div className="px-4 py-3 bg-green-500/5 border border-green-500/20 rounded-lg">
          <div className="flex items-center gap-2 text-green-400 text-sm font-medium mb-2">
            <CheckCircle className="h-4 w-4" />
            Key generated successfully
          </div>
          <p className="text-xs text-dark-400 mb-3">
            Copy this key now — it will <span className="text-foreground font-medium">not be shown again</span>.
          </p>
          <div className="flex items-center gap-2">
            <code className={clsx(
              'flex-1 text-xs font-mono px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg',
              revealed ? 'text-green-300' : 'text-dark-500',
            )}>
              {revealed ? apiKey.key : '••••••••••••••••••••••••••••••••'}
            </code>
            <button
              onClick={() => setRevealed(!revealed)}
              className="p-2 text-dark-500 hover:text-dark-300 transition-colors"
              title={revealed ? 'Hide' : 'Reveal'}
            >
              {revealed ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
            <button
              onClick={copyKey}
              className={clsx(
                'p-2 rounded-lg transition-colors',
                copied ? 'text-green-400 bg-green-500/10' : 'text-dark-500 hover:text-dark-300 hover:bg-dark-700',
              )}
              title="Copy to clipboard"
            >
              <Copy className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-dark-400">Name</span>
            <span className="text-foreground">{apiKey.name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-dark-400">Role</span>
            <span className="text-foreground capitalize">{apiKey.role}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-dark-400">Prefix</span>
            <code className="text-dark-300 font-mono text-xs">{apiKey.key_prefix}</code>
          </div>
          <div className="flex justify-between">
            <span className="text-dark-400">Expires</span>
            <span className="text-foreground">{expiresLabel(apiKey.expires_at)}</span>
          </div>
        </div>

        <div className="bg-dark-900/50 border border-dark-700 rounded-lg p-3 text-xs text-dark-400">
          <p className="font-medium text-dark-300 mb-1">Usage Example:</p>
          <code className="block text-dark-500 whitespace-pre-wrap">
{`curl -H "Authorization: Bearer ${apiKey.key || 'sf_xxxx_...'}" \\
     ${window.location.origin}/api/scans`}
          </code>
        </div>

        <div className="flex justify-end pt-2">
          <button onClick={onClose} className="px-4 py-2 bg-spider-600 hover:bg-spider-500 text-white rounded-lg text-sm font-medium transition-colors">
            Done
          </button>
        </div>
      </div>
    </ModalShell>
  );
}


// ══════════════════════════════════════════════════════════
// Generic Confirm Modal
// ══════════════════════════════════════════════════════════

function ConfirmModal({
  title,
  message,
  confirmLabel,
  confirmClass,
  onConfirm,
  onClose,
}: {
  title: string;
  message: React.ReactNode;
  confirmLabel: string;
  confirmClass: string;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(false);

  const handleConfirm = async () => {
    setLoading(true);
    await onConfirm();
    setLoading(false);
  };

  return (
    <ModalShell title={title} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-dark-300 text-sm">{message}</p>
        <div className="flex justify-end gap-3 pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-dark-400 hover:text-dark-200 transition-colors">
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={loading}
            className={clsx('px-4 py-2 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors', confirmClass)}
          >
            {loading ? 'Processing...' : confirmLabel}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
