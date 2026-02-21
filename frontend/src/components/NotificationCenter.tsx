/**
 * NotificationCenter — Bell icon + dropdown panel in the layout sidebar.
 * Shows unread badge, recent notifications, and mark-all-read action.
 */
import { useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Bell, Check, CheckCheck, X, Trash2,
  Radar, AlertTriangle, Info, Zap,
} from 'lucide-react';
import { clsx } from 'clsx';
import {
  useNotificationStore,
  type AppNotification,
  type NotificationType,
} from '../lib/notifications';

const typeConfig: Record<NotificationType, { icon: typeof Radar; color: string }> = {
  scan_complete: { icon: Check, color: 'text-green-400' },
  scan_failed: { icon: AlertTriangle, color: 'text-red-400' },
  scan_started: { icon: Radar, color: 'text-blue-400' },
  system: { icon: Zap, color: 'text-yellow-400' },
  info: { icon: Info, color: 'text-dark-400' },
};

function timeAgo(ts: number): string {
  const secs = Math.floor((Date.now() - ts) / 1000);
  if (secs < 60) return 'just now';
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

function NotificationItem({ n }: { n: AppNotification }) {
  const { markRead, remove } = useNotificationStore();
  const cfg = typeConfig[n.type] ?? typeConfig.info;
  const Icon = cfg.icon;

  const content = (
    <div
      className={clsx(
        'flex items-start gap-3 px-3 py-2.5 rounded-lg transition-colors group cursor-pointer',
        n.read ? 'opacity-60 hover:opacity-80' : 'hover:bg-dark-700/50',
      )}
      onClick={() => markRead(n.id)}
    >
      <Icon className={clsx('h-4 w-4 mt-0.5 flex-shrink-0', cfg.color)} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground truncate">{n.title}</p>
        <p className="text-xs text-dark-400 truncate">{n.message}</p>
        <p className="text-[10px] text-dark-600 mt-0.5">{timeAgo(n.timestamp)}</p>
      </div>
      {!n.read && <span className="w-2 h-2 rounded-full bg-spider-400 mt-1.5 flex-shrink-0" />}
      <button
        onClick={(e) => { e.stopPropagation(); remove(n.id); }}
        className="opacity-0 group-hover:opacity-100 text-dark-500 hover:text-dark-300 transition-opacity"
        aria-label="Dismiss"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );

  if (n.href) {
    return <Link to={n.href}>{content}</Link>;
  }
  return content;
}

export function NotificationBell() {
  const { unreadCount, toggle } = useNotificationStore();

  return (
    <button
      onClick={toggle}
      className="relative p-2 text-dark-400 hover:text-dark-200 hover:bg-dark-800 rounded-lg transition-colors"
      aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
    >
      <Bell className="h-4 w-4" />
      {unreadCount > 0 && (
        <span className="absolute -top-0.5 -right-0.5 h-4 min-w-[16px] px-1 flex items-center justify-center text-[10px] font-bold text-white bg-red-500 rounded-full animate-pulse">
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}
    </button>
  );
}

export function NotificationPanel() {
  const { notifications, isOpen, setOpen, markAllRead, clear, unreadCount } = useNotificationStore();
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [isOpen, setOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [isOpen, setOpen]);

  if (!isOpen) return null;

  return (
    <div
      ref={panelRef}
      className="absolute bottom-full left-0 mb-2 w-80 max-h-[60vh] bg-dark-800 border border-dark-700 rounded-xl shadow-2xl overflow-hidden animate-fade-in-up z-50"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-dark-700">
        <h3 className="text-sm font-semibold text-foreground">Notifications</h3>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              className="text-xs text-dark-400 hover:text-spider-400 flex items-center gap-1 transition-colors"
              title="Mark all as read"
            >
              <CheckCheck className="h-3.5 w-3.5" />
            </button>
          )}
          {notifications.length > 0 && (
            <button
              onClick={clear}
              className="text-xs text-dark-400 hover:text-red-400 flex items-center gap-1 transition-colors"
              title="Clear all"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* List */}
      <div className="overflow-y-auto max-h-[50vh] divide-y divide-dark-700/30">
        {notifications.length > 0 ? (
          notifications.map((n) => <NotificationItem key={n.id} n={n} />)
        ) : (
          <div className="px-4 py-8 text-center">
            <Bell className="h-8 w-8 text-dark-600 mx-auto mb-2" />
            <p className="text-sm text-dark-500">No notifications yet</p>
            <p className="text-xs text-dark-600 mt-1">Scan events will appear here</p>
          </div>
        )}
      </div>
    </div>
  );
}
