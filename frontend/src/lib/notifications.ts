/**
 * Notification store — Zustand store for in-app notifications.
 *
 * Supports scan events (started, completed, failed), system alerts,
 * and arbitrary messages. Persists unread count and recent notifications.
 */
import { create } from 'zustand';

export type NotificationType = 'scan_complete' | 'scan_failed' | 'scan_started' | 'system' | 'info';

export interface AppNotification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  timestamp: number;
  read: boolean;
  /** Optional link to navigate to */
  href?: string;
}

interface NotificationState {
  notifications: AppNotification[];
  unreadCount: number;
  isOpen: boolean;

  /** Add a new notification */
  add: (n: Omit<AppNotification, 'id' | 'timestamp' | 'read'>) => void;
  /** Mark a single notification as read */
  markRead: (id: string) => void;
  /** Mark all notifications as read */
  markAllRead: () => void;
  /** Remove a notification */
  remove: (id: string) => void;
  /** Clear all */
  clear: () => void;
  /** Toggle the notification panel */
  toggle: () => void;
  /** Set open state */
  setOpen: (open: boolean) => void;
}

let counter = 0;

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  unreadCount: 0,
  isOpen: false,

  add: (n) => set((state) => {
    const notification: AppNotification = {
      ...n,
      id: `notif-${++counter}-${Date.now()}`,
      timestamp: Date.now(),
      read: false,
    };
    const notifications = [notification, ...state.notifications].slice(0, 50); // Keep last 50
    return {
      notifications,
      unreadCount: notifications.filter((x) => !x.read).length,
    };
  }),

  markRead: (id) => set((state) => {
    const notifications = state.notifications.map((n) =>
      n.id === id ? { ...n, read: true } : n,
    );
    return {
      notifications,
      unreadCount: notifications.filter((x) => !x.read).length,
    };
  }),

  markAllRead: () => set((state) => ({
    notifications: state.notifications.map((n) => ({ ...n, read: true })),
    unreadCount: 0,
  })),

  remove: (id) => set((state) => {
    const notifications = state.notifications.filter((n) => n.id !== id);
    return {
      notifications,
      unreadCount: notifications.filter((x) => !x.read).length,
    };
  }),

  clear: () => set({ notifications: [], unreadCount: 0 }),

  toggle: () => set((state) => ({ isOpen: !state.isOpen })),

  setOpen: (open) => set({ isOpen: open }),
}));
