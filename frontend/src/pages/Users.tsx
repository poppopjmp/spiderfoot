/**
 * SpiderFoot User Management Page (admin only)
 *
 * Full CRUD for users: list, create, edit role/status, change password, delete.
 * Only accessible to users with user:read permission.
 */
import { useState, useEffect, useCallback } from 'react';
import {
  Users as UsersIcon,
  Plus,
  Pencil,
  Trash2,
  KeyRound,
  Shield,
  CheckCircle,
  XCircle,
  Lock,
  Clock,
  Search,
  X,
  AlertCircle,
  ChevronDown,
} from 'lucide-react';
import { clsx } from 'clsx';
import api from '../lib/api';
import { ModalShell } from '../components/ui';
import { useAuthStore } from '../lib/auth';

// ── Types ────────────────────────────────────────────────

interface UserRecord {
  id: string;
  username: string;
  email: string;
  role: string;
  display_name: string;
  auth_method: string;
  status: string;
  created_at: number;
  updated_at: number;
  last_login: number;
  sso_provider_id: string;
}

const ROLES = ['viewer', 'analyst', 'operator', 'admin'] as const;
const STATUSES = ['active', 'disabled', 'locked', 'pending'] as const;

const STATUS_ICON: Record<string, React.ReactNode> = {
  active: <CheckCircle className="h-3.5 w-3.5 text-green-400" />,
  disabled: <XCircle className="h-3.5 w-3.5 text-dark-500" />,
  locked: <Lock className="h-3.5 w-3.5 text-red-400" />,
  pending: <Clock className="h-3.5 w-3.5 text-yellow-400" />,
};

const ROLE_BADGE_COLOR: Record<string, string> = {
  admin: 'bg-red-500/15 text-red-400 border-red-500/30',
  operator: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  analyst: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  viewer: 'bg-dark-600/50 text-dark-300 border-dark-600',
};

// ── Helpers ──────────────────────────────────────────────

function formatDate(ts: number): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString();
}

// ── Component ────────────────────────────────────────────

export default function UsersPage() {
  const { user: currentUser, hasPermission } = useAuthStore();

  const canCreate = hasPermission('user:create');
  const canUpdate = hasPermission('user:update');
  const canDelete = hasPermission('user:delete');

  const [users, setUsers] = useState<UserRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  // Modals
  const [showCreate, setShowCreate] = useState(false);
  const [editUser, setEditUser] = useState<UserRecord | null>(null);
  const [passwordUser, setPasswordUser] = useState<UserRecord | null>(null);
  const [deleteUser, setDeleteUser] = useState<UserRecord | null>(null);

  // ── Data fetching ──────────────────────────────────────

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/auth/users', {
        params: { limit: 200, offset: 0 },
      });
      setUsers(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // ── Filter ─────────────────────────────────────────────

  const filtered = users.filter((u) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      u.username.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      u.display_name.toLowerCase().includes(q) ||
      u.role.toLowerCase().includes(q)
    );
  });

  // ── Render ─────────────────────────────────────────────

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-3">
            <UsersIcon className="h-7 w-7 text-spider-400" />
            User Management
          </h1>
          <p className="text-dark-400 text-sm mt-1">
            {total} user{total !== 1 ? 's' : ''} total
          </p>
        </div>
        {canCreate && (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-spider-600 hover:bg-spider-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add User
          </button>
        )}
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-500" />
        <input
          type="text"
          placeholder="Search users..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-10 py-2.5 bg-dark-800 border border-dark-700 rounded-lg text-sm text-foreground placeholder:text-dark-500 focus:outline-none focus:ring-2 focus:ring-spider-500/40 focus:border-spider-500/60"
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-500 hover:text-dark-300"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-dark-700 text-dark-400 text-left">
                <th className="px-4 py-3 font-medium">User</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Auth</th>
                <th className="px-4 py-3 font-medium">Last Login</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-dark-500">
                    <div className="flex items-center justify-center gap-2">
                      <div className="animate-spin h-5 w-5 border-2 border-spider-500 border-t-transparent rounded-full" />
                      Loading users...
                    </div>
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-dark-500">
                    {search ? 'No users match your search' : 'No users found'}
                  </td>
                </tr>
              ) : (
                filtered.map((u) => (
                  <tr
                    key={u.id}
                    className="border-b border-dark-700/50 hover:bg-dark-750 transition-colors"
                  >
                    {/* User info */}
                    <td className="px-4 py-3">
                      <div>
                        <p className="text-foreground font-medium">{u.display_name || u.username}</p>
                        <p className="text-dark-500 text-xs">{u.email || u.username}</p>
                      </div>
                    </td>
                    {/* Role badge */}
                    <td className="px-4 py-3">
                      <span
                        className={clsx(
                          'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border',
                          ROLE_BADGE_COLOR[u.role] || ROLE_BADGE_COLOR.viewer,
                        )}
                      >
                        <Shield className="h-3 w-3" />
                        {u.role}
                      </span>
                    </td>
                    {/* Status */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {STATUS_ICON[u.status] || STATUS_ICON.pending}
                        <span className="text-dark-300 capitalize">{u.status}</span>
                      </div>
                    </td>
                    {/* Auth method */}
                    <td className="px-4 py-3 text-dark-400 capitalize">{u.auth_method}</td>
                    {/* Last login */}
                    <td className="px-4 py-3 text-dark-400 text-xs">
                      {formatDate(u.last_login)}
                    </td>
                    {/* Actions */}
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        {canUpdate && (
                          <button
                            onClick={() => setEditUser(u)}
                            className="p-1.5 text-dark-500 hover:text-spider-400 hover:bg-dark-700 rounded-lg transition-colors"
                            title="Edit user"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                        )}
                        {canUpdate && (
                          <button
                            onClick={() => setPasswordUser(u)}
                            className="p-1.5 text-dark-500 hover:text-yellow-400 hover:bg-dark-700 rounded-lg transition-colors"
                            title="Change password"
                          >
                            <KeyRound className="h-3.5 w-3.5" />
                          </button>
                        )}
                        {canDelete && u.id !== currentUser?.id && (
                          <button
                            onClick={() => setDeleteUser(u)}
                            className="p-1.5 text-dark-500 hover:text-red-400 hover:bg-dark-700 rounded-lg transition-colors"
                            title="Delete user"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Create User Modal ── */}
      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            fetchUsers();
          }}
        />
      )}

      {/* ── Edit User Modal ── */}
      {editUser && (
        <EditUserModal
          user={editUser}
          onClose={() => setEditUser(null)}
          onUpdated={() => {
            setEditUser(null);
            fetchUsers();
          }}
        />
      )}

      {/* ── Change Password Modal ── */}
      {passwordUser && (
        <ChangePasswordModal
          user={passwordUser}
          onClose={() => setPasswordUser(null)}
          onChanged={() => {
            setPasswordUser(null);
          }}
        />
      )}

      {/* ── Delete Confirmation Modal ── */}
      {deleteUser && (
        <DeleteUserModal
          user={deleteUser}
          onClose={() => setDeleteUser(null)}
          onDeleted={() => {
            setDeleteUser(null);
            fetchUsers();
          }}
        />
      )}
    </div>
  );
}


// ══════════════════════════════════════════════════════════
// Modal Components
// ══════════════════════════════════════════════════════════

function FormField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-dark-300">{label}</label>
      {children}
    </div>
  );
}

const inputClass =
  'w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm text-foreground placeholder:text-dark-500 focus:outline-none focus:ring-2 focus:ring-spider-500/40 focus:border-spider-500/60';

const selectClass =
  'w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-spider-500/40 focus:border-spider-500/60 appearance-none';


// ── Create User ──────────────────────────────────────────

function CreateUserModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('viewer');
  const [displayName, setDisplayName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await api.post('/api/auth/users', {
        username,
        email,
        password,
        role,
        display_name: displayName,
      });
      onCreated();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create user');
    } finally {
      setSaving(false);
    }
  };

  return (
    <ModalShell title="Create User" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <FormField label="Username">
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            className={inputClass}
            placeholder="e.g. john.doe"
          />
        </FormField>

        <FormField label="Email">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className={inputClass}
            placeholder="john@example.com"
          />
        </FormField>

        <FormField label="Password">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className={inputClass}
            placeholder="Min 8 characters"
          />
        </FormField>

        <FormField label="Display Name">
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className={inputClass}
            placeholder="John Doe"
          />
        </FormField>

        <FormField label="Role">
          <div className="relative">
            <select value={role} onChange={(e) => setRole(e.target.value)} className={selectClass}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r.charAt(0).toUpperCase() + r.slice(1)}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-500 pointer-events-none" />
          </div>
        </FormField>

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-dark-400 hover:text-dark-200 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-spider-600 hover:bg-spider-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {saving ? 'Creating...' : 'Create User'}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}


// ── Edit User ────────────────────────────────────────────

function EditUserModal({
  user,
  onClose,
  onUpdated,
}: {
  user: UserRecord;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [email, setEmail] = useState(user.email);
  const [role, setRole] = useState(user.role);
  const [displayName, setDisplayName] = useState(user.display_name);
  const [status, setStatus] = useState(user.status);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await api.patch(`/api/auth/users/${user.id}`, {
        email,
        role,
        display_name: displayName,
        status,
      });
      onUpdated();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update user');
    } finally {
      setSaving(false);
    }
  };

  return (
    <ModalShell title={`Edit ${user.username}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <FormField label="Email">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
          />
        </FormField>

        <FormField label="Display Name">
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className={inputClass}
          />
        </FormField>

        <FormField label="Role">
          <div className="relative">
            <select value={role} onChange={(e) => setRole(e.target.value)} className={selectClass}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r.charAt(0).toUpperCase() + r.slice(1)}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-500 pointer-events-none" />
          </div>
        </FormField>

        <FormField label="Status">
          <div className="relative">
            <select value={status} onChange={(e) => setStatus(e.target.value)} className={selectClass}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-500 pointer-events-none" />
          </div>
        </FormField>

        <div className="text-xs text-dark-500 space-y-1">
          <p>Auth method: <span className="text-dark-300">{user.auth_method}</span></p>
          <p>Created: <span className="text-dark-300">{formatDate(user.created_at)}</span></p>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-dark-400 hover:text-dark-200 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-spider-600 hover:bg-spider-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}


// ── Change Password ──────────────────────────────────────

function ChangePasswordModal({
  user,
  onClose,
  onChanged,
}: {
  user: UserRecord;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirm) {
      setError('Passwords do not match');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await api.post(`/api/auth/users/${user.id}/password`, {
        new_password: newPassword,
      });
      onChanged();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to change password');
    } finally {
      setSaving(false);
    }
  };

  return (
    <ModalShell title={`Change Password — ${user.username}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <FormField label="New Password">
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={8}
            className={inputClass}
            placeholder="Min 8 characters"
          />
        </FormField>

        <FormField label="Confirm Password">
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={8}
            className={inputClass}
            placeholder="Re-enter password"
          />
        </FormField>

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-dark-400 hover:text-dark-200 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || newPassword.length < 8 || newPassword !== confirm}
            className="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {saving ? 'Changing...' : 'Change Password'}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}


// ── Delete Confirmation ──────────────────────────────────

function DeleteUserModal({
  user,
  onClose,
  onDeleted,
}: {
  user: UserRecord;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');

  const handleDelete = async () => {
    setDeleting(true);
    setError('');
    try {
      await api.delete(`/api/auth/users/${user.id}`);
      onDeleted();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete user');
      setDeleting(false);
    }
  };

  return (
    <ModalShell title="Delete User" onClose={onClose}>
      <div className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <p className="text-dark-300 text-sm">
          Are you sure you want to delete user{' '}
          <span className="text-foreground font-medium">{user.username}</span>? This
          action cannot be undone and will revoke all active sessions.
        </p>

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-dark-400 hover:text-dark-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {deleting ? 'Deleting...' : 'Delete User'}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
