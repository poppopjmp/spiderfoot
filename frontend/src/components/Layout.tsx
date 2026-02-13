import { Outlet, NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Radar,
  PlusCircle,
  Cpu,
  Clock,
  Globe,
  Settings,
  Bug,
  ShieldCheck,
  Key,
  ScrollText,
  Lock,
  Link,
  FileText,
  FileDown,
  Bell,
  Webhook,
  Tags,
  GitCompare,
  Database,
  Server,
  Building2,
  Store,
  Target,
} from 'lucide-react';
import { clsx } from 'clsx';

interface NavItem {
  name: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavSection {
  label: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    label: 'Core',
    items: [
      { name: 'Dashboard', to: '/', icon: LayoutDashboard },
      { name: 'Scans', to: '/scans', icon: Radar },
      { name: 'New Scan', to: '/scans/new', icon: PlusCircle },
      { name: 'Engines', to: '/engines', icon: Cpu },
      { name: 'Schedules', to: '/schedules', icon: Clock },
      { name: 'Monitor', to: '/monitor', icon: Globe },
    ],
  },
  {
    label: 'Analysis',
    items: [
      { name: 'Correlations', to: '/correlations', icon: Link },
      { name: 'Scan Compare', to: '/scan-compare', icon: GitCompare },
      { name: 'ASM', to: '/asm', icon: Target },
    ],
  },
  {
    label: 'Reports',
    items: [
      { name: 'Templates', to: '/report-templates', icon: FileText },
      { name: 'Export', to: '/export', icon: FileDown },
    ],
  },
  {
    label: 'Security',
    items: [
      { name: 'RBAC', to: '/rbac', icon: ShieldCheck },
      { name: 'API Keys', to: '/api-keys', icon: Key },
      { name: 'Audit Log', to: '/audit', icon: ScrollText },
      { name: 'SSO / SAML', to: '/sso', icon: Lock },
    ],
  },
  {
    label: 'Enterprise',
    items: [
      { name: 'Tenants', to: '/tenants', icon: Building2 },
      { name: 'Tags & Groups', to: '/tags-groups', icon: Tags },
      { name: 'Data Retention', to: '/data-retention', icon: Database },
    ],
  },
  {
    label: 'Integrations',
    items: [
      { name: 'Webhooks', to: '/webhooks', icon: Webhook },
      { name: 'Notifications', to: '/notifications', icon: Bell },
      { name: 'Marketplace', to: '/marketplace', icon: Store },
      { name: 'Distributed', to: '/distributed', icon: Server },
    ],
  },
];

export default function Layout() {
  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="w-64 bg-dark-900 border-r border-dark-700 flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-dark-700">
          <Bug className="h-8 w-8 text-spider-500" />
          <div>
            <h1 className="text-lg font-bold text-white">SpiderFoot</h1>
            <p className="text-xs text-dark-400">OSINT Platform</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-4 overflow-y-auto">
          {navSections.map((section) => (
            <div key={section.label}>
              <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-dark-500">
                {section.label}
              </p>
              <div className="space-y-0.5">
                {section.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/'}
                    className={({ isActive }) =>
                      clsx(
                        'flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-colors',
                        isActive
                          ? 'bg-spider-600/20 text-spider-400'
                          : 'text-dark-300 hover:bg-dark-800 hover:text-dark-100',
                      )
                    }
                  >
                    <item.icon className="h-4 w-4 flex-shrink-0" />
                    {item.name}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}

          {/* Settings (standalone at bottom of nav) */}
          <div>
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-colors',
                  isActive
                    ? 'bg-spider-600/20 text-spider-400'
                    : 'text-dark-300 hover:bg-dark-800 hover:text-dark-100',
                )
              }
            >
              <Settings className="h-4 w-4 flex-shrink-0" />
              Settings
            </NavLink>
          </div>
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-dark-700">
          <p className="text-xs text-dark-500">SpiderFoot v5.7.4</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
