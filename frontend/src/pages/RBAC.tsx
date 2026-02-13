import { useQuery } from '@tanstack/react-query';
import { rbacApi } from '../lib/api';
import { Shield, UserPlus, Lock, Users } from 'lucide-react';
import { useState } from 'react';

export default function RBACPage() {
  const [tab, setTab] = useState<'roles' | 'users' | 'permissions'>('roles');
  const { data: roles } = useQuery({ queryKey: ['rbac-roles'], queryFn: rbacApi.listRoles });
  const { data: permissions } = useQuery({ queryKey: ['rbac-perms'], queryFn: rbacApi.listPermissions });
  const { data: users } = useQuery({ queryKey: ['rbac-users'], queryFn: rbacApi.listUsers });

  const tabs = [
    { key: 'roles' as const, label: 'Roles', icon: Shield },
    { key: 'users' as const, label: 'Users', icon: Users },
    { key: 'permissions' as const, label: 'Permissions', icon: Lock },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Access Control (RBAC)</h1>
        <button className="btn-primary flex items-center gap-2">
          <UserPlus className="h-4 w-4" /> Create Role
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-dark-800 rounded-lg p-1 w-fit">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              tab === t.key
                ? 'bg-spider-600 text-white'
                : 'text-dark-300 hover:text-white hover:bg-dark-700'
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {/* Roles tab */}
      {tab === 'roles' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(roles?.roles ?? []).map((role: { name: string; description: string; permissions: string[] }) => (
            <div key={role.name} className="card hover:border-spider-600 border border-transparent transition">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-spider-600/20 rounded-lg">
                  <Shield className="h-5 w-5 text-spider-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-white capitalize">{role.name}</h3>
                  <p className="text-xs text-dark-400">{role.permissions?.length ?? 0} permissions</p>
                </div>
              </div>
              <p className="text-sm text-dark-300">{role.description}</p>
            </div>
          ))}
        </div>
      )}

      {/* Users tab */}
      {tab === 'users' && (
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">User Role Assignments</h2>
          {users?.users ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-dark-400 border-b border-dark-700">
                  <th className="pb-3 font-medium">User</th>
                  <th className="pb-3 font-medium">Role</th>
                  <th className="pb-3 font-medium">Tenant</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700">
                {users.users.map((u: { id: string; email: string; role: string; tenant?: string }) => (
                  <tr key={u.id}>
                    <td className="py-3 text-white">{u.email}</td>
                    <td className="py-3"><span className="badge badge-info">{u.role}</span></td>
                    <td className="py-3 text-dark-300">{u.tenant || 'default'}</td>
                    <td className="py-3"><button className="text-spider-400 text-sm hover:underline">Edit</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-dark-400">No users configured. Users are auto-provisioned via SSO or API key creation.</p>
          )}
        </div>
      )}

      {/* Permissions tab */}
      {tab === 'permissions' && (
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">Available Permissions</h2>
          <div className="flex flex-wrap gap-2">
            {(permissions?.permissions ?? []).map((perm: string) => (
              <span key={perm} className="badge badge-low">{perm}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
