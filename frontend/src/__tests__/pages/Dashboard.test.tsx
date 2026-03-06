/**
 * Smoke tests for Dashboard page.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../lib/api');
  return {
    ...actual,
    scanApi: {
      list: vi.fn().mockResolvedValue({ scans: [], total: 0 }),
      search: vi.fn().mockResolvedValue({ results: [] }),
      correlationsSummary: vi.fn().mockResolvedValue({ total: 0, by_type: {} }),
    },
    healthApi: {
      dashboard: vi.fn().mockResolvedValue({ components: [], overall: 'healthy' }),
    },
  };
});

import Dashboard from '../../pages/Dashboard';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('Dashboard', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the page header', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });
    expect(screen.getByText('Dashboard')).toBeTruthy();
  });

  it('shows empty state when no scans exist', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/No scans yet/i)).toBeTruthy();
    });
  });
});
