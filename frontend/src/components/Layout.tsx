import { Outlet, NavLink } from 'react-router-dom';
import { useState } from 'react';
import {
  LayoutDashboard,
  Radar,
  PlusCircle,
  Settings,
  Server,
  ExternalLink,
  ChevronDown,
  X,
  Briefcase,
  Bot,
  BookOpen,
  Menu,
  LogOut,
  Users,
  User,
  Shield,
  Key,
  Lock,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useAuthStore } from '../lib/auth';

interface NavItem {
  name: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
}

/* Navigation matches CherryPy: New Scan, Scans, Workspaces, Documentation, Settings
   plus Dashboard (new) and Agents (from Services dropdown) */
const navItems: NavItem[] = [
  { name: 'Dashboard', to: '/', icon: LayoutDashboard },
  { name: 'New Scan', to: '/scans/new', icon: PlusCircle },
  { name: 'Scans', to: '/scans', icon: Radar },
  { name: 'Workspaces', to: '/workspaces', icon: Briefcase },
  { name: 'Documentation', to: '/documentation', icon: BookOpen },
  { name: 'Settings', to: '/settings', icon: Settings },
];

const SERVICE_LINKS = [
  { name: 'AI Agents', url: '/agents', internal: true, desc: 'AI agent orchestrator' },
  { name: 'Grafana', url: '/grafana/', internal: false, desc: 'Metrics & dashboards (admin/spiderfoot)' },
  { name: 'Jaeger', url: '/jaeger/', internal: false, desc: 'Distributed tracing' },
  { name: 'Prometheus', url: '/prometheus/', internal: false, desc: 'Metrics collection' },
  { name: 'Traefik', url: '/dashboard/', internal: false, desc: 'Reverse proxy (admin/spiderfoot)' },
  { name: 'MinIO', url: '/minio/', internal: false, desc: 'Object storage (spiderfoot/changeme123)' },
  { name: 'Flower', url: '/flower/', internal: false, desc: 'Celery monitor (admin/spiderfoot)' },
];

export default function Layout() {
  const [showAbout, setShowAbout] = useState(false);
  const [servicesOpen, setServicesOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { user, isAuthenticated, logout, hasPermission } = useAuthStore();

  return (
    <div className="flex h-full">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={clsx(
        'fixed lg:relative z-40 w-64 bg-dark-900 border-r border-dark-700 flex flex-col h-full transition-transform lg:translate-x-0',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        {/* Logo */}
        <div
          className="flex items-center gap-3 px-6 py-5 border-b border-dark-700 cursor-pointer hover:bg-dark-800/50 transition-colors"
          onClick={() => setShowAbout(true)}
        >
          <img src="/spiderfoot-icon.png" alt="SpiderFoot" className="h-8 w-8" />
          <div>
            <h1 className="text-lg font-bold text-white">SpiderFoot</h1>
            <p className="text-xs text-dark-400">OSINT Platform</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={() => { if (window.innerWidth < 1024) setSidebarOpen(false); }}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors',
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

          {/* Admin-only nav items */}
          {isAuthenticated && hasPermission('user:read') && (
            <NavLink
              to="/users"
              onClick={() => { if (window.innerWidth < 1024) setSidebarOpen(false); }}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors',
                  isActive
                    ? 'bg-spider-600/20 text-spider-400'
                    : 'text-dark-300 hover:bg-dark-800 hover:text-dark-100',
                )
              }
            >
              <Users className="h-4 w-4 flex-shrink-0" />
              Users
            </NavLink>
          )}

          {/* SSO Settings (admin only) */}
          {isAuthenticated && hasPermission('config:write') && (
            <NavLink
              to="/sso-settings"
              onClick={() => { if (window.innerWidth < 1024) setSidebarOpen(false); }}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors',
                  isActive
                    ? 'bg-spider-600/20 text-spider-400'
                    : 'text-dark-300 hover:bg-dark-800 hover:text-dark-100',
                )
              }
            >
              <Lock className="h-4 w-4 flex-shrink-0" />
              SSO Settings
            </NavLink>
          )}

          {/* API Keys (all authenticated users) */}
          {isAuthenticated && (
            <NavLink
              to="/api-keys"
              onClick={() => { if (window.innerWidth < 1024) setSidebarOpen(false); }}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors',
                  isActive
                    ? 'bg-spider-600/20 text-spider-400'
                    : 'text-dark-300 hover:bg-dark-800 hover:text-dark-100',
                )
              }
            >
              <Key className="h-4 w-4 flex-shrink-0" />
              API Keys
            </NavLink>
          )}
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
              {SERVICE_LINKS.map((svc) =>
                svc.internal ? (
                  <NavLink
                    key={svc.name}
                    to={svc.url}
                    className="flex items-center gap-2 px-3 py-1.5 text-xs text-dark-400 hover:text-dark-200 hover:bg-dark-800 rounded-lg transition-colors"
                  >
                    <Bot className="h-3 w-3" />
                    <span className="flex-1">{svc.name}</span>
                  </NavLink>
                ) : (
                  <a
                    key={svc.name}
                    href={svc.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={svc.desc}
                    className="flex items-center gap-2 px-3 py-1.5 text-xs text-dark-400 hover:text-dark-200 hover:bg-dark-800 rounded-lg transition-colors"
                  >
                    <ExternalLink className="h-3 w-3" />
                    <span className="flex-1">{svc.name}</span>
                  </a>
                ),
              )}
            </div>
          )}
        </div>

        {/* User menu & Footer */}
        <div className="px-3 pb-2 border-t border-dark-700">
          {isAuthenticated && user ? (
            <div className="py-3">
              <div className="flex items-center gap-3 px-3 py-2">
                <div className="h-8 w-8 rounded-full bg-spider-600/20 flex items-center justify-center flex-shrink-0">
                  <User className="h-4 w-4 text-spider-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{user.username}</p>
                  <div className="flex items-center gap-1">
                    <Shield className="h-3 w-3 text-dark-500" />
                    <p className="text-xs text-dark-500 capitalize">{user.role}</p>
                  </div>
                </div>
              </div>
              <button
                onClick={() => logout()}
                className="w-full flex items-center gap-2 px-3 py-2 mt-1 text-xs text-dark-400 hover:text-red-400 hover:bg-dark-800 rounded-lg transition-colors"
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </button>
            </div>
          ) : null}
          <div className="px-3 py-2">
            <p className="text-xs text-dark-500">SpiderFoot v5.8.0</p>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {/* Mobile header */}
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-dark-700 bg-dark-900">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-dark-300 hover:text-white">
            <Menu className="h-5 w-5" />
          </button>
          <img src="/spiderfoot-icon.png" alt="SpiderFoot" className="h-5 w-5" />
          <span className="text-sm font-bold text-white">SpiderFoot</span>
        </div>
        <div className="px-6 py-8">
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
              <img src="/spiderfoot-header-dark.png" alt="SpiderFoot" className="h-16 mx-auto mb-4" />
              <h2 className="text-xl font-bold text-white">SpiderFoot</h2>
              <p className="text-dark-400 text-sm mt-1">Open Source Intelligence Automation</p>
              <p className="text-spider-400 font-mono text-sm mt-3">v5.8.0</p>
              <div className="mt-6 space-y-2 text-sm text-dark-400">
                <p>An OSINT automation tool for reconnaissance.</p>
                <p>
                  <a
                    href="https://github.com/poppopjmp/spiderfoot"
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
