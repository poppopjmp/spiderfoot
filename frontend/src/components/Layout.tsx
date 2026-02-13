import { Outlet, NavLink } from 'react-router-dom';
import { useState } from 'react';
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
  ExternalLink,
  ChevronDown,
  X,
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
      { name: 'Modules', to: '/modules', icon: Cpu },
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

const SERVICE_LINKS = [
  { name: 'Grafana', url: '/grafana/', desc: 'Metrics & dashboards' },
  { name: 'Jaeger', url: '/jaeger/', desc: 'Distributed tracing' },
  { name: 'Prometheus', url: '/prometheus/', desc: 'Metrics collection' },
  { name: 'Traefik', url: '/dashboard/', desc: 'Reverse proxy' },
  { name: 'MinIO', url: '/minio/', desc: 'Object storage' },
  { name: 'Flower', url: '/flower/', desc: 'Celery task monitor' },
];

export default function Layout() {
  const [showAbout, setShowAbout] = useState(false);
  const [servicesOpen, setServicesOpen] = useState(false);

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="w-64 bg-dark-900 border-r border-dark-700 flex flex-col">
        {/* Logo */}
        <div
          className="flex items-center gap-3 px-6 py-5 border-b border-dark-700 cursor-pointer hover:bg-dark-800/50 transition-colors"
          onClick={() => setShowAbout(true)}
        >
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

        {/* Services dropdown */}
        <div className="px-3 pb-2">
          <button
            onClick={() => setServicesOpen(!servicesOpen)}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-dark-400 hover:text-dark-200 hover:bg-dark-800 rounded-lg transition-colors"
          >
            <Server className="h-3.5 w-3.5" />
            <span className="flex-1 text-left">Services</span>
            <ChevronDown className={clsx('h-3 w-3 transition-transform', servicesOpen && 'rotate-180')} />
          </button>
          {servicesOpen && (
            <div className="mt-1 space-y-0.5 animate-fade-in">
              {SERVICE_LINKS.map((svc) => (
                <a
                  key={svc.name}
                  href={svc.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-3 py-1.5 text-xs text-dark-400 hover:text-dark-200 hover:bg-dark-800 rounded-lg transition-colors"
                >
                  <ExternalLink className="h-3 w-3" />
                  <span className="flex-1">{svc.name}</span>
                </a>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-dark-700">
          <p className="text-xs text-dark-500">SpiderFoot v5.7.7</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <Outlet />
        </div>
      </main>

      {/* About Modal */}
      {showAbout && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowAbout(false)} />
          <div className="relative bg-dark-800 border border-dark-700 rounded-2xl p-8 max-w-md w-full shadow-2xl animate-fade-in-up">
            <button
              onClick={() => setShowAbout(false)}
              className="absolute top-4 right-4 text-dark-500 hover:text-dark-300"
            >
              <X className="h-5 w-5" />
            </button>
            <div className="text-center">
              <Bug className="h-16 w-16 text-spider-500 mx-auto mb-4" />
              <h2 className="text-xl font-bold text-white">SpiderFoot</h2>
              <p className="text-dark-400 text-sm mt-1">Open Source Intelligence Automation</p>
              <p className="text-spider-400 font-mono text-sm mt-3">v5.7.7</p>
              <div className="mt-6 space-y-2 text-sm text-dark-400">
                <p>An OSINT automation tool for reconnaissance.</p>
                <p>
                  <a
                    href="https://github.com/smicallef/spiderfoot"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-spider-400 hover:text-spider-300 underline decoration-spider-600/50 underline-offset-2"
                  >
                    View on GitHub
                  </a>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
