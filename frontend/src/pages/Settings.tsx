import { Shield, Database, Bell, Key, Palette } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Settings</h1>

      <div className="space-y-6 max-w-3xl">
        {/* General */}
        <SettingsSection
          title="General"
          icon={Palette}
          description="Basic application settings and preferences."
        >
          <SettingRow label="Instance Name" description="Display name for this SpiderFoot instance">
            <input className="input-field w-64" defaultValue="SpiderFoot" />
          </SettingRow>
          <SettingRow label="Debug Mode" description="Enable verbose logging output">
            <Toggle />
          </SettingRow>
        </SettingsSection>

        {/* Security */}
        <SettingsSection
          title="Security"
          icon={Shield}
          description="Authentication and access control settings."
        >
          <SettingRow label="RBAC Enforcement" description="Enforce role-based access control">
            <Toggle />
          </SettingRow>
          <SettingRow label="Default Role" description="Default role for new users">
            <select className="input-field w-48">
              <option value="viewer">Viewer</option>
              <option value="analyst">Analyst</option>
              <option value="operator">Operator</option>
              <option value="admin">Admin</option>
            </select>
          </SettingRow>
        </SettingsSection>

        {/* Database */}
        <SettingsSection
          title="Database"
          icon={Database}
          description="Database connection and storage configuration."
        >
          <SettingRow label="Database Type" description="Primary data store">
            <select className="input-field w-48">
              <option value="sqlite">SQLite</option>
              <option value="postgres">PostgreSQL</option>
            </select>
          </SettingRow>
        </SettingsSection>

        {/* Notifications */}
        <SettingsSection
          title="Notifications"
          icon={Bell}
          description="Configure notification channels for scan events."
        >
          <SettingRow label="Webhooks" description="HTTP webhook notifications">
            <Toggle />
          </SettingRow>
          <SettingRow label="Slack" description="Slack channel notifications">
            <Toggle />
          </SettingRow>
          <SettingRow label="Email" description="Email notifications via SMTP">
            <Toggle />
          </SettingRow>
        </SettingsSection>

        {/* API */}
        <SettingsSection
          title="API"
          icon={Key}
          description="API configuration and rate limiting."
        >
          <SettingRow label="Rate Limiting" description="Enable API rate limiting">
            <Toggle />
          </SettingRow>
          <SettingRow label="CORS Origins" description="Allowed CORS origins (comma-separated)">
            <input className="input-field w-64" defaultValue="*" />
          </SettingRow>
        </SettingsSection>
      </div>
    </div>
  );
}

function SettingsSection({
  title,
  icon: Icon,
  description,
  children,
}: {
  title: string;
  icon: React.ElementType;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-spider-600/20 rounded-lg">
          <Icon className="h-5 w-5 text-spider-400" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <p className="text-sm text-dark-400">{description}</p>
        </div>
      </div>
      <div className="space-y-4 divide-y divide-dark-700">{children}</div>
    </div>
  );
}

function SettingRow({
  label,
  description,
  children,
}: {
  label: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between pt-4 first:pt-0">
      <div>
        <p className="text-sm font-medium text-white">{label}</p>
        <p className="text-xs text-dark-400">{description}</p>
      </div>
      {children}
    </div>
  );
}

function Toggle() {
  return (
    <label className="relative inline-flex items-center cursor-pointer">
      <input type="checkbox" className="sr-only peer" />
      <div className="w-11 h-6 bg-dark-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-spider-500" />
    </label>
  );
}
