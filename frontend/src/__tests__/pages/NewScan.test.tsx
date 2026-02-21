/**
 * Smoke tests for NewScan page.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../lib/api');
  return {
    ...actual,
    dataApi: {
      modules: vi.fn().mockResolvedValue([]),
      entityTypes: vi.fn().mockResolvedValue([]),
    },
    scanApi: {
      create: vi.fn().mockResolvedValue({ id: 'new-1' }),
      profiles: vi.fn().mockResolvedValue([]),
    },
  };
});

import NewScan from '../../pages/NewScan';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('NewScan', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the page header', async () => {
    render(<NewScan />, { wrapper: createWrapper() });
    expect(screen.getByText('New Scan')).toBeTruthy();
  });

  it('renders the target input', async () => {
    render(<NewScan />, { wrapper: createWrapper() });
    expect(screen.getByPlaceholderText(/target|domain|IP/i)).toBeTruthy();
  });
});
