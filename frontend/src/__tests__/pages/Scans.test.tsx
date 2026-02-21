/**
 * Smoke tests for Scans page.
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
      stop: vi.fn(),
      delete: vi.fn(),
      rerun: vi.fn(),
      clone: vi.fn(),
      bulkStop: vi.fn(),
      bulkDelete: vi.fn(),
      exportEvents: vi.fn(),
    },
    SCAN_STATUSES: ['RUNNING', 'FINISHED', 'ABORTED', 'ERROR-FAILED'],
  };
});

import Scans from '../../pages/Scans';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('Scans', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the page header', async () => {
    render(<Scans />, { wrapper: createWrapper() });
    expect(screen.getByText('Scans')).toBeTruthy();
  });

  it('shows empty state when no scans exist', async () => {
    render(<Scans />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/No scans found/i)).toBeTruthy();
    });
  });
});
