/**
 * SpiderFoot SSO Settings Page (admin only)
 *
 * Full CRUD for SSO providers: OAuth2/OIDC (Keycloak, Azure AD, etc.),
 * LDAP, and SAML. Includes group→role mapping configuration.
 * Only accessible to users with config:write permission.
 */
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import {
  Shield,
  Plus,
  Pencil,
  Trash2,
  CheckCircle,
  XCircle,
  Search,
  X,
  AlertCircle,
  ChevronDown,
  Globe,
  Lock,
  Server,
  ToggleLeft,
  ToggleRight,
  ExternalLink,
} from 'lucide-react';
import { clsx } from 'clsx';
import api from '../lib/api';
import { getErrorMessage } from '../lib/errors';
import { ModalShell } from '../components/ui';

// ── Types ────────────────────────────────────────────────

interface SSOProviderRecord {
  id: string;
  name: string;
  protocol: string;
  enabled: boolean;
  default_role: string;
  allowed_domains: string;
  auto_create_users: boolean;
  attribute_mapping: string;
  group_attribute: string;
  admin_group: string;
  created_at: number;
  updated_at: number;
  // OAuth2 fields
  client_id?: string;
  client_secret?: string;
  authorization_url?: string;
  token_url?: string;
  userinfo_url?: string;
  scopes?: string;
  jwks_uri?: string;
  // LDAP fields
  ldap_url?: string;
  ldap_base_dn?: string;
  ldap_user_filter?: string;
  ldap_group_filter?: string;
  ldap_tls?: boolean;
  ldap_bind_dn?: string;
  ldap_bind_password?: string;
  // SAML fields
  idp_entity_id?: string;
  idp_sso_url?: string;
  sp_entity_id?: string;
  sp_acs_url?: string;
}

const PROTOCOLS = ['oauth2', 'ldap', 'saml'] as const;
const ROLES = ['viewer', 'analyst', 'operator', 'admin'] as const;

const PROTOCOL_LABELS: Record<string, string> = {
  oauth2: 'OAuth2 / OIDC',
  ldap: 'LDAP',
  saml: 'SAML 2.0',
};

const PROTOCOL_ICON: Record<string, React.ReactNode> = {
  oauth2: <Globe className="h-4 w-4 text-blue-400" />,
  ldap: <Server className="h-4 w-4 text-green-400" />,
  saml: <Lock className="h-4 w-4 text-purple-400" />,
};

const PROTOCOL_COLOR: Record<string, string> = {
  oauth2: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  ldap: 'bg-green-500/15 text-green-400 border-green-500/30',
  saml: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
};

// ── Helpers ──────────────────────────────────────────────

// Keycloak default template
const KEYCLOAK_DEFAULTS = {
  authorization_url: 'https://keycloak.example.com/realms/master/protocol/openid-connect/auth',
  token_url: 'https://keycloak.example.com/realms/master/protocol/openid-connect/token',
  userinfo_url: 'https://keycloak.example.com/realms/master/protocol/openid-connect/userinfo',
  jwks_uri: 'https://keycloak.example.com/realms/master/protocol/openid-connect/certs',
  scopes: 'openid email profile groups',
  group_attribute: 'groups',
  admin_group: '/spiderfoot-admins',
};

// ── Component ────────────────────────────────────────────

export default function SSOSettingsPage() {
  useDocumentTitle('SSO Settings');
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');

  // Modals
  const [showCreate, setShowCreate] = useState(false);
  const [editProvider, setEditProvider] = useState<SSOProviderRecord | null>(null);
  const [deleteProvider, setDeleteProvider] = useState<SSOProviderRecord | null>(null);

  // ── Data fetching ──────────────────────────────────────

  const { data: providers = [], isLoading: loading, error: queryError } = useQuery<SSOProviderRecord[]>({
    queryKey: ['sso-providers'],
    queryFn: ({ signal }) => api.get('/api/auth/sso/providers/all', { signal }).then(r => r.data.items || []),
  });

  // Toggle enabled state
  const toggleMutation = useMutation({
    mutationFn: (p: SSOProviderRecord) => api.patch(`/api/auth/sso/providers/${p.id}`, { enabled: !p.enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sso-providers'] }),
  });

  const error = queryError
    ? getErrorMessage(queryError, 'Failed to load SSO providers')
    : toggleMutation.error
      ? getErrorMessage(toggleMutation.error, 'Failed to toggle provider')
      : '';

  // ── Filter ─────────────────────────────────────────────

  const filtered = providers.filter((p) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      p.name.toLowerCase().includes(q) ||
      p.protocol.toLowerCase().includes(q)
    );
  });

  // ── Render ─────────────────────────────────────────────

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-3">
            <Shield className="h-7 w-7 text-spider-400" />
            SSO Settings
          </h1>
          <p className="text-dark-400 text-sm mt-1">
            Configure Single Sign-On providers — OAuth2/OIDC (Keycloak), LDAP, SAML
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-spider-600 hover:bg-spider-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add Provider
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-500" />
        <input
          type="text"
          placeholder="Search providers..."
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
        </div>
      )}

      {/* Info about callback URLs */}
      <div className="mb-4 px-4 py-3 bg-blue-500/5 border border-blue-500/20 rounded-lg text-sm text-dark-300">
        <p className="font-medium text-blue-400 mb-1">Callback URLs for IDP configuration</p>
        <p className="text-xs text-dark-400">
          OAuth2 Redirect: <code className="text-blue-300 bg-dark-800 px-1 rounded">{window.location.origin}/api/auth/sso/callback/{'<provider_id>'}</code>
          <br />
          SAML ACS: <code className="text-purple-300 bg-dark-800 px-1 rounded">{window.location.origin}/api/auth/sso/saml/acs/{'<provider_id>'}</code>
        </p>
      </div>

      {/* Provider Cards */}
      <div className="space-y-4">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-dark-500">
            <div className="animate-spin h-5 w-5 border-2 border-spider-500 border-t-transparent rounded-full mr-3" />
            Loading providers...
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-dark-500">
            {search ? 'No providers match your search' : 'No SSO providers configured. Click "Add Provider" to get started.'}
          </div>
        ) : (
          filtered.map((p) => (
            <div
              key={p.id}
              className={clsx(
                'bg-dark-800 border rounded-xl p-5 transition-colors',
                p.enabled ? 'border-dark-700' : 'border-dark-700/50 opacity-60',
              )}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  {PROTOCOL_ICON[p.protocol]}
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-foreground font-medium">{p.name}</h3>
                      <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border', PROTOCOL_COLOR[p.protocol] || 'bg-dark-600 text-dark-300 border-dark-600')}>
                        {PROTOCOL_LABELS[p.protocol] || p.protocol}
                      </span>
                      {p.enabled ? (
                        <span className="inline-flex items-center gap-1 text-xs text-green-400">
                          <CheckCircle className="h-3 w-3" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-dark-500">
                          <XCircle className="h-3 w-3" /> Disabled
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-xs text-dark-500">
                      <span>Default role: <span className="text-dark-300 capitalize">{p.default_role}</span></span>
                      {p.admin_group && (
                        <span>Admin group: <span className="text-dark-300">{p.admin_group}</span></span>
                      )}
                      {p.auto_create_users && (
                        <span className="text-green-500/70">Auto-create users</span>
                      )}
                      {p.allowed_domains && (
                        <span>Domains: <span className="text-dark-300">{p.allowed_domains}</span></span>
                      )}
                    </div>
                    {p.protocol === 'oauth2' && p.client_id && (
                      <div className="mt-1 text-xs text-dark-500">
                        Client ID: <span className="text-dark-400 font-mono">{p.client_id}</span>
                        {p.userinfo_url && (
                          <span className="ml-3">
                            Userinfo: <span className="text-dark-400">{p.userinfo_url}</span>
                          </span>
                        )}
                      </div>
                    )}
                    {p.protocol === 'ldap' && p.ldap_url && (
                      <div className="mt-1 text-xs text-dark-500">
                        URL: <span className="text-dark-400 font-mono">{p.ldap_url}</span>
                        <span className="ml-3">Base DN: <span className="text-dark-400">{p.ldap_base_dn}</span></span>
                      </div>
                    )}
                    {p.protocol === 'saml' && p.idp_sso_url && (
                      <div className="mt-1 text-xs text-dark-500">
                        IDP SSO URL: <span className="text-dark-400">{p.idp_sso_url}</span>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => toggleMutation.mutate(p)}
                    className="p-1.5 text-dark-500 hover:text-spider-400 hover:bg-dark-700 rounded-lg transition-colors"
                    title={p.enabled ? 'Disable' : 'Enable'}
                  >
                    {p.enabled ? <ToggleRight className="h-5 w-5 text-green-400" /> : <ToggleLeft className="h-5 w-5" />}
                  </button>
                  <button
                    onClick={() => setEditProvider(p)}
                    className="p-1.5 text-dark-500 hover:text-spider-400 hover:bg-dark-700 rounded-lg transition-colors"
                    title="Edit provider"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => setDeleteProvider(p)}
                    className="p-1.5 text-dark-500 hover:text-red-400 hover:bg-dark-700 rounded-lg transition-colors"
                    title="Delete provider"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modals */}
      {showCreate && (
        <ProviderFormModal
          onClose={() => setShowCreate(false)}
          onSaved={() => { setShowCreate(false); queryClient.invalidateQueries({ queryKey: ['sso-providers'] }); }}
        />
      )}
      {editProvider && (
        <ProviderFormModal
          provider={editProvider}
          onClose={() => setEditProvider(null)}
          onSaved={() => { setEditProvider(null); queryClient.invalidateQueries({ queryKey: ['sso-providers'] }); }}
        />
      )}
      {deleteProvider && (
        <DeleteProviderModal
          provider={deleteProvider}
          onClose={() => setDeleteProvider(null)}
          onDeleted={() => { setDeleteProvider(null); queryClient.invalidateQueries({ queryKey: ['sso-providers'] }); }}
        />
      )}
    </div>
  );
}


// ══════════════════════════════════════════════════════════
// Shared UI Helpers
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
// Create / Edit Provider Modal
// ══════════════════════════════════════════════════════════

function ProviderFormModal({
  provider,
  onClose,
  onSaved,
}: {
  provider?: SSOProviderRecord;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!provider;
  const [protocol, setProtocol] = useState(provider?.protocol || 'oauth2');
  const [name, setName] = useState(provider?.name || '');
  const [enabled, setEnabled] = useState(provider?.enabled ?? true);
  const [defaultRole, setDefaultRole] = useState(provider?.default_role || 'viewer');
  const [allowedDomains, setAllowedDomains] = useState(provider?.allowed_domains || '');
  const [autoCreateUsers, setAutoCreateUsers] = useState(provider?.auto_create_users ?? true);
  const [groupAttribute, setGroupAttribute] = useState(provider?.group_attribute || 'groups');
  const [adminGroup, setAdminGroup] = useState(provider?.admin_group || '');
  const [groupRoleMap, setGroupRoleMap] = useState('');

  // OAuth2
  const [clientId, setClientId] = useState(provider?.client_id || '');
  const [clientSecret, setClientSecret] = useState(provider?.client_secret || '');
  const [authorizationUrl, setAuthorizationUrl] = useState(provider?.authorization_url || '');
  const [tokenUrl, setTokenUrl] = useState(provider?.token_url || '');
  const [userinfoUrl, setUserinfoUrl] = useState(provider?.userinfo_url || '');
  const [jwksUri, setJwksUri] = useState(provider?.jwks_uri || '');
  const [scopes, setScopes] = useState(provider?.scopes || 'openid email profile');

  // LDAP
  const [ldapUrl, setLdapUrl] = useState(provider?.ldap_url || '');
  const [ldapBindDn, setLdapBindDn] = useState(provider?.ldap_bind_dn || '');
  const [ldapBindPassword, setLdapBindPassword] = useState(provider?.ldap_bind_password || '');
  const [ldapBaseDn, setLdapBaseDn] = useState(provider?.ldap_base_dn || '');
  const [ldapUserFilter, setLdapUserFilter] = useState(provider?.ldap_user_filter || '(uid={username})');
  const [ldapGroupFilter, setLdapGroupFilter] = useState(provider?.ldap_group_filter || '(member={dn})');
  const [ldapTls, setLdapTls] = useState(provider?.ldap_tls ?? true);

  // SAML
  const [idpEntityId, setIdpEntityId] = useState(provider?.idp_entity_id || '');
  const [idpSsoUrl, setIdpSsoUrl] = useState(provider?.idp_sso_url || '');
  const [spEntityId, setSpEntityId] = useState(provider?.sp_entity_id || '');
  const [spAcsUrl, setSpAcsUrl] = useState(provider?.sp_acs_url || '');

  const [error, setError] = useState('');

  const saveMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => {
      if (isEdit) {
        return api.patch(`/api/auth/sso/providers/${provider!.id}`, body).then(r => r.data);
      }
      return api.post('/api/auth/sso/providers', body).then(r => r.data);
    },
    onSuccess: () => onSaved(),
    onError: (err: unknown) => setError(getErrorMessage(err, 'Failed to save provider')),
  });

  // Parse existing group_role_map from attribute_mapping
  useEffect(() => {
    if (provider?.attribute_mapping) {
      try {
        const mapping = JSON.parse(provider.attribute_mapping);
        if (mapping.group_role_map) {
          setGroupRoleMap(JSON.stringify(mapping.group_role_map, null, 2));
        }
      } catch {
        // ignore
      }
    }
  }, [provider]);

  const applyKeycloakDefaults = () => {
    setAuthorizationUrl(KEYCLOAK_DEFAULTS.authorization_url);
    setTokenUrl(KEYCLOAK_DEFAULTS.token_url);
    setUserinfoUrl(KEYCLOAK_DEFAULTS.userinfo_url);
    setJwksUri(KEYCLOAK_DEFAULTS.jwks_uri);
    setScopes(KEYCLOAK_DEFAULTS.scopes);
    setGroupAttribute(KEYCLOAK_DEFAULTS.group_attribute);
    setAdminGroup(KEYCLOAK_DEFAULTS.admin_group);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Build attribute_mapping JSON with group_role_map
    let attributeMapping = '';
    try {
      const mapping: Record<string, unknown> = {};
      if (groupRoleMap.trim()) {
        mapping.group_role_map = JSON.parse(groupRoleMap);
      }
      if (Object.keys(mapping).length > 0) {
        attributeMapping = JSON.stringify(mapping);
      }
    } catch {
      setError('Group→Role mapping must be valid JSON (e.g. {"admins": "admin", "analysts": "analyst"})');
      return;
    }

    const body: Record<string, unknown> = {
      name,
      protocol,
      enabled,
      default_role: defaultRole,
      allowed_domains: allowedDomains,
      auto_create_users: autoCreateUsers,
      attribute_mapping: attributeMapping,
      group_attribute: groupAttribute,
      admin_group: adminGroup,
    };

    if (protocol === 'oauth2') {
      Object.assign(body, {
        client_id: clientId,
        client_secret: clientSecret,
        authorization_url: authorizationUrl,
        token_url: tokenUrl,
        userinfo_url: userinfoUrl,
        jwks_uri: jwksUri,
        scopes,
      });
    } else if (protocol === 'ldap') {
      Object.assign(body, {
        ldap_url: ldapUrl,
        ldap_bind_dn: ldapBindDn,
        ldap_bind_password: ldapBindPassword,
        ldap_base_dn: ldapBaseDn,
        ldap_user_filter: ldapUserFilter,
        ldap_group_filter: ldapGroupFilter,
        ldap_tls: ldapTls,
      });
    } else if (protocol === 'saml') {
      Object.assign(body, {
        idp_entity_id: idpEntityId,
        idp_sso_url: idpSsoUrl,
        sp_entity_id: spEntityId,
        sp_acs_url: spAcsUrl,
      });
    }

    saveMutation.mutate(body);
  };

  return (
    <ModalShell title={isEdit ? `Edit ${provider!.name}` : 'Add SSO Provider'} onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Basic Settings */}
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Provider Name">
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} required className={inputClass} placeholder="e.g. Keycloak" />
          </FormField>
          <FormField label="Protocol">
            <div className="relative">
              <select value={protocol} onChange={(e) => setProtocol(e.target.value)} disabled={isEdit} className={selectClass}>
                {PROTOCOLS.map((p) => <option key={p} value={p}>{PROTOCOL_LABELS[p]}</option>)}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-500 pointer-events-none" />
            </div>
          </FormField>
        </div>

        {/* Keycloak quick-fill button */}
        {protocol === 'oauth2' && !isEdit && (
          <button
            type="button"
            onClick={applyKeycloakDefaults}
            className="flex items-center gap-2 px-3 py-1.5 text-xs text-blue-400 bg-blue-500/10 border border-blue-500/20 rounded-lg hover:bg-blue-500/20 transition-colors"
          >
            <ExternalLink className="h-3 w-3" /> Fill Keycloak defaults (edit URLs to match your realm)
          </button>
        )}

        {/* OAuth2 Fields */}
        {protocol === 'oauth2' && (
          <div className="space-y-4 pt-2 border-t border-dark-700/50">
            <p className="text-xs text-dark-500 font-medium uppercase tracking-wider">OAuth2 / OIDC Configuration</p>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Client ID">
                <input type="text" value={clientId} onChange={(e) => setClientId(e.target.value)} className={inputClass} placeholder="spiderfoot-client" />
              </FormField>
              <FormField label="Client Secret">
                <input type="password" value={clientSecret} onChange={(e) => setClientSecret(e.target.value)} className={inputClass} placeholder="••••••••" />
              </FormField>
            </div>
            <FormField label="Authorization URL" hint="OIDC authorization endpoint">
              <input type="url" value={authorizationUrl} onChange={(e) => setAuthorizationUrl(e.target.value)} className={inputClass} placeholder="https://keycloak.example.com/realms/master/protocol/openid-connect/auth" />
            </FormField>
            <FormField label="Token URL" hint="OIDC token endpoint">
              <input type="url" value={tokenUrl} onChange={(e) => setTokenUrl(e.target.value)} className={inputClass} placeholder="https://keycloak.example.com/realms/master/protocol/openid-connect/token" />
            </FormField>
            <FormField label="Userinfo URL" hint="OIDC userinfo endpoint">
              <input type="url" value={userinfoUrl} onChange={(e) => setUserinfoUrl(e.target.value)} className={inputClass} placeholder="https://keycloak.example.com/realms/master/protocol/openid-connect/userinfo" />
            </FormField>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="JWKS URI" hint="JSON Web Key Set URL (optional)">
                <input type="url" value={jwksUri} onChange={(e) => setJwksUri(e.target.value)} className={inputClass} placeholder="https://..." />
              </FormField>
              <FormField label="Scopes" hint="Space-separated">
                <input type="text" value={scopes} onChange={(e) => setScopes(e.target.value)} className={inputClass} placeholder="openid email profile groups" />
              </FormField>
            </div>
          </div>
        )}

        {/* LDAP Fields */}
        {protocol === 'ldap' && (
          <div className="space-y-4 pt-2 border-t border-dark-700/50">
            <p className="text-xs text-dark-500 font-medium uppercase tracking-wider">LDAP Configuration</p>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="LDAP URL">
                <input type="text" value={ldapUrl} onChange={(e) => setLdapUrl(e.target.value)} className={inputClass} placeholder="ldaps://ldap.example.com:636" />
              </FormField>
              <FormField label="Base DN">
                <input type="text" value={ldapBaseDn} onChange={(e) => setLdapBaseDn(e.target.value)} className={inputClass} placeholder="dc=example,dc=com" />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Bind DN" hint="Service account DN">
                <input type="text" value={ldapBindDn} onChange={(e) => setLdapBindDn(e.target.value)} className={inputClass} placeholder="cn=admin,dc=example,dc=com" />
              </FormField>
              <FormField label="Bind Password">
                <input type="password" value={ldapBindPassword} onChange={(e) => setLdapBindPassword(e.target.value)} className={inputClass} />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="User Filter" hint="{username} is replaced">
                <input type="text" value={ldapUserFilter} onChange={(e) => setLdapUserFilter(e.target.value)} className={inputClass} />
              </FormField>
              <FormField label="Group Filter" hint="{dn} is replaced">
                <input type="text" value={ldapGroupFilter} onChange={(e) => setLdapGroupFilter(e.target.value)} className={inputClass} />
              </FormField>
            </div>
            <label className="flex items-center gap-2 text-sm text-dark-300 cursor-pointer">
              <input type="checkbox" checked={ldapTls} onChange={(e) => setLdapTls(e.target.checked)} className="rounded border-dark-600 bg-dark-900 text-spider-600 focus:ring-spider-500/40" />
              Use TLS (StartTLS)
            </label>
          </div>
        )}

        {/* SAML Fields */}
        {protocol === 'saml' && (
          <div className="space-y-4 pt-2 border-t border-dark-700/50">
            <p className="text-xs text-dark-500 font-medium uppercase tracking-wider">SAML 2.0 Configuration</p>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="IDP Entity ID">
                <input type="text" value={idpEntityId} onChange={(e) => setIdpEntityId(e.target.value)} className={inputClass} placeholder="https://idp.example.com/saml/metadata" />
              </FormField>
              <FormField label="IDP SSO URL">
                <input type="url" value={idpSsoUrl} onChange={(e) => setIdpSsoUrl(e.target.value)} className={inputClass} placeholder="https://idp.example.com/saml/sso" />
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="SP Entity ID">
                <input type="text" value={spEntityId} onChange={(e) => setSpEntityId(e.target.value)} className={inputClass} placeholder="spiderfoot" />
              </FormField>
              <FormField label="SP ACS URL">
                <input type="url" value={spAcsUrl} onChange={(e) => setSpAcsUrl(e.target.value)} className={inputClass} placeholder={`${window.location.origin}/api/auth/sso/saml/acs/...`} />
              </FormField>
            </div>
          </div>
        )}

        {/* Group → Role Mapping */}
        <div className="space-y-4 pt-2 border-t border-dark-700/50">
          <p className="text-xs text-dark-500 font-medium uppercase tracking-wider">User Provisioning & Role Mapping</p>

          <div className="grid grid-cols-2 gap-4">
            <FormField label="Default Role" hint="Role assigned to new SSO users">
              <div className="relative">
                <select value={defaultRole} onChange={(e) => setDefaultRole(e.target.value)} className={selectClass}>
                  {ROLES.map((r) => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-500 pointer-events-none" />
              </div>
            </FormField>
            <FormField label="Allowed Domains" hint="Comma-separated, empty = all">
              <input type="text" value={allowedDomains} onChange={(e) => setAllowedDomains(e.target.value)} className={inputClass} placeholder="example.com, corp.io" />
            </FormField>
          </div>

          <label className="flex items-center gap-2 text-sm text-dark-300 cursor-pointer">
            <input type="checkbox" checked={autoCreateUsers} onChange={(e) => setAutoCreateUsers(e.target.checked)} className="rounded border-dark-600 bg-dark-900 text-spider-600 focus:ring-spider-500/40" />
            Auto-create users on first SSO login
          </label>

          <div className="grid grid-cols-2 gap-4">
            <FormField label="Group Attribute" hint="Claim name in OIDC userinfo containing groups">
              <input type="text" value={groupAttribute} onChange={(e) => setGroupAttribute(e.target.value)} className={inputClass} placeholder="groups" />
            </FormField>
            <FormField label="Admin Group" hint="Group name that grants admin role">
              <input type="text" value={adminGroup} onChange={(e) => setAdminGroup(e.target.value)} className={inputClass} placeholder="/spiderfoot-admins" />
            </FormField>
          </div>

          <FormField label="Group → Role Mapping (JSON)" hint='Map IDP groups to SpiderFoot roles. e.g. {"analysts": "analyst", "ops-team": "operator"}'>
            <textarea
              value={groupRoleMap}
              onChange={(e) => setGroupRoleMap(e.target.value)}
              rows={4}
              className={clsx(inputClass, 'font-mono text-xs')}
              placeholder='{\n  "sf-analysts": "analyst",\n  "sf-operators": "operator",\n  "sf-admins": "admin"\n}'
            />
          </FormField>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between pt-3 border-t border-dark-700/50">
          <label className="flex items-center gap-2 text-sm text-dark-300 cursor-pointer">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} className="rounded border-dark-600 bg-dark-900 text-spider-600 focus:ring-spider-500/40" />
            Enabled
          </label>
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-dark-400 hover:text-dark-200 transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={saveMutation.isPending} className="px-4 py-2 bg-spider-600 hover:bg-spider-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">
              {saveMutation.isPending ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Provider'}
            </button>
          </div>
        </div>
      </form>
    </ModalShell>
  );
}


// ══════════════════════════════════════════════════════════
// Delete Provider Modal
// ══════════════════════════════════════════════════════════

function DeleteProviderModal({
  provider,
  onClose,
  onDeleted,
}: {
  provider: SSOProviderRecord;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/api/auth/sso/providers/${provider.id}`),
    onSuccess: () => onDeleted(),
  });

  const error = deleteMutation.error
    ? getErrorMessage(deleteMutation.error, 'Failed to delete provider')
    : '';

  return (
    <ModalShell title="Delete SSO Provider" onClose={onClose}>
      <div className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}
        <p className="text-dark-300 text-sm">
          Are you sure you want to delete the SSO provider{' '}
          <span className="text-foreground font-medium">{provider.name}</span>?
          Users who authenticated via this provider will no longer be able to sign in through SSO.
        </p>
        <div className="flex justify-end gap-3 pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-dark-400 hover:text-dark-200 transition-colors">
            Cancel
          </button>
          <button onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending} className="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">
            {deleteMutation.isPending ? 'Deleting...' : 'Delete Provider'}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
