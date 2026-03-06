/**
 * Smoke tests for ScanDetail page.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../lib/api');
  return {
    ...actual,
    scanApi: {
      get: vi.fn().mockResolvedValue({
        id: 'scan-1',
        name: 'Test Scan',
        target: 'example.com',
        status: 'FINISHED',
        started: 1700000000,
        ended: 1700003600,
        results_count: 42,
      }),
      stop: vi.fn(),
      rerun: vi.fn(),
    },
  };
});

vi.mock('../../lib/useScanProgress', () => ({
  useScanProgress: () => ({ percent: 100, eta: 0, throughput: 0, status: 'FINISHED' }),
}));

import ScanDetail from '../../pages/ScanDetail';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/scans/scan-1']}>
        <Routes>
          <Route path="/scans/:scanId" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ScanDetail', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the scan name', async () => {
    render(<ScanDetail />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText('Test Scan')).toBeTruthy();
    });
  });

  it('shows the scan target', async () => {
    render(<ScanDetail />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText('example.com')).toBeTruthy();
    });
  });
});
