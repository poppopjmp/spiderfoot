/**
 * Tests for Schedules page.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the API module
vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../lib/api');
  return {
    ...actual,
    scheduleApi: {
      list: vi.fn().mockResolvedValue({ schedules: [] }),
      get: vi.fn(),
      create: vi.fn().mockResolvedValue({ id: '1' }),
      update: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      trigger: vi.fn().mockResolvedValue({}),
    },
  };
});

import SchedulesPage from '../../pages/Schedules';
import { scheduleApi } from '../../lib/api';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('SchedulesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (scheduleApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      schedules: [],
    });
  });

  it('renders page header and new schedule button', async () => {
    render(<SchedulesPage />, { wrapper: createWrapper() });

    expect(screen.getByText('Schedules')).toBeTruthy();
    expect(screen.getByText(/New Schedule/)).toBeTruthy();
  });

  it('shows empty state when there are no schedules', async () => {
    render(<SchedulesPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/No schedules/i)).toBeTruthy();
    });
  });

  it('shows schedule rows when data is present', async () => {
    (scheduleApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      schedules: [
        {
          id: 'sched-1',
          name: 'Daily example.com',
          target: 'example.com',
          scan_type: 'all',
          cron_expression: '0 0 * * *',
          enabled: true,
          last_run: 1700000000,
          next_run: 1700086400,
          created_at: 1699900000,
        },
      ],
    });

    render(<SchedulesPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Daily example.com')).toBeTruthy();
      expect(screen.getByText('example.com')).toBeTruthy();
    });
  });

  it('opens create modal on button click', async () => {
    render(<SchedulesPage />, { wrapper: createWrapper() });

    fireEvent.click(screen.getByText(/New Schedule/));

    await waitFor(() => {
      expect(screen.getByText(/Create Schedule/)).toBeTruthy();
    });
  });
});
