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
} from 'lucide-react';
import { clsx } from 'clsx';

const navigation = [
  { name: 'Dashboard', to: '/', icon: LayoutDashboard },
  { name: 'Scans', to: '/scans', icon: Radar },
  { name: 'New Scan', to: '/scans/new', icon: PlusCircle },
  { name: 'Engines', to: '/engines', icon: Cpu },
  { name: 'Schedules', to: '/schedules', icon: Clock },
  { name: 'Monitor', to: '/monitor', icon: Globe },
  { name: 'Settings', to: '/settings', icon: Settings },
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
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors',
                  isActive
                    ? 'bg-spider-600/20 text-spider-400'
                    : 'text-dark-300 hover:bg-dark-800 hover:text-dark-100',
                )
              }
            >
              <item.icon className="h-5 w-5 flex-shrink-0" />
              {item.name}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-dark-700">
          <p className="text-xs text-dark-500">SpiderFoot v5.5</p>
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
