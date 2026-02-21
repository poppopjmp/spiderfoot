/**
 * Tests for Tooltip, Notification store, and Command Palette components.
 * Covers B10 emotional design additions.
 */
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Tooltip } from '../components/ui';
import { useNotificationStore } from '../lib/notifications';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('Tooltip', () => {
  it('renders children without tooltip by default', () => {
    render(
      <Tooltip content="Helpful text">
        <button>Hover me</button>
      </Tooltip>,
      { wrapper: Wrapper },
    );
    expect(screen.getByText('Hover me')).toBeTruthy();
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('shows tooltip on mouse enter after delay', async () => {
    vi.useFakeTimers();
    render(
      <Tooltip content="Helpful text" delayMs={100}>
        <button>Hover me</button>
      </Tooltip>,
      { wrapper: Wrapper },
    );

    fireEvent.mouseEnter(screen.getByText('Hover me'));
    
    // Not yet visible
    expect(screen.queryByRole('tooltip')).toBeNull();

    // Advance timer
    await act(async () => { vi.advanceTimersByTime(150); });

    expect(screen.getByRole('tooltip')).toBeTruthy();
    expect(screen.getByText('Helpful text')).toBeTruthy();

    vi.useRealTimers();
  });

  it('hides tooltip on mouse leave', async () => {
    vi.useFakeTimers();
    render(
      <Tooltip content="Hide me" delayMs={0}>
        <button>Hover</button>
      </Tooltip>,
      { wrapper: Wrapper },
    );

    fireEvent.mouseEnter(screen.getByText('Hover'));
    await act(async () => { vi.advanceTimersByTime(10); });
    expect(screen.getByRole('tooltip')).toBeTruthy();

    fireEvent.mouseLeave(screen.getByText('Hover'));
    expect(screen.queryByRole('tooltip')).toBeNull();

    vi.useRealTimers();
  });

  it('sets aria-describedby when visible', async () => {
    vi.useFakeTimers();
    render(
      <Tooltip content="Accessible" delayMs={0}>
        <button>Target</button>
      </Tooltip>,
      { wrapper: Wrapper },
    );

    const btn = screen.getByText('Target');
    expect(btn.getAttribute('aria-describedby')).toBeNull();

    fireEvent.mouseEnter(btn);
    await act(async () => { vi.advanceTimersByTime(10); });

    expect(btn.getAttribute('aria-describedby')).toBeTruthy();
    vi.useRealTimers();
  });
});

describe('NotificationStore', () => {
  beforeEach(() => {
    useNotificationStore.getState().clear();
  });

  it('starts with empty notifications', () => {
    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(0);
    expect(state.unreadCount).toBe(0);
  });

  it('adds a notification and increments unread count', () => {
    useNotificationStore.getState().add({
      type: 'scan_complete',
      title: 'Scan Done',
      message: 'example.com finished',
    });

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(1);
    expect(state.unreadCount).toBe(1);
    expect(state.notifications[0].title).toBe('Scan Done');
    expect(state.notifications[0].read).toBe(false);
  });

  it('marks a notification as read', () => {
    useNotificationStore.getState().add({
      type: 'info',
      title: 'Test',
      message: 'msg',
    });

    const id = useNotificationStore.getState().notifications[0].id;
    useNotificationStore.getState().markRead(id);

    const state = useNotificationStore.getState();
    expect(state.notifications[0].read).toBe(true);
    expect(state.unreadCount).toBe(0);
  });

  it('marks all as read', () => {
    const { add } = useNotificationStore.getState();
    add({ type: 'info', title: 'A', message: '1' });
    add({ type: 'info', title: 'B', message: '2' });
    add({ type: 'info', title: 'C', message: '3' });

    expect(useNotificationStore.getState().unreadCount).toBe(3);

    useNotificationStore.getState().markAllRead();
    expect(useNotificationStore.getState().unreadCount).toBe(0);
  });

  it('removes a notification', () => {
    useNotificationStore.getState().add({
      type: 'system',
      title: 'Remove me',
      message: 'msg',
    });

    const id = useNotificationStore.getState().notifications[0].id;
    useNotificationStore.getState().remove(id);

    expect(useNotificationStore.getState().notifications).toHaveLength(0);
  });

  it('caps at 50 notifications', () => {
    const { add } = useNotificationStore.getState();
    for (let i = 0; i < 60; i++) {
      add({ type: 'info', title: `N${i}`, message: `msg${i}` });
    }
    expect(useNotificationStore.getState().notifications).toHaveLength(50);
    // Most recent should be first
    expect(useNotificationStore.getState().notifications[0].title).toBe('N59');
  });

  it('toggles panel open state', () => {
    expect(useNotificationStore.getState().isOpen).toBe(false);
    useNotificationStore.getState().toggle();
    expect(useNotificationStore.getState().isOpen).toBe(true);
    useNotificationStore.getState().toggle();
    expect(useNotificationStore.getState().isOpen).toBe(false);
  });

  it('clears all notifications', () => {
    const { add } = useNotificationStore.getState();
    add({ type: 'info', title: 'A', message: '1' });
    add({ type: 'info', title: 'B', message: '2' });

    useNotificationStore.getState().clear();
    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(0);
    expect(state.unreadCount).toBe(0);
  });
});

describe('useScanProgress hook', () => {
  it('module is importable', async () => {
    const mod = await import('../hooks/useScanProgress');
    expect(typeof mod.useScanProgress).toBe('function');
  });
});
