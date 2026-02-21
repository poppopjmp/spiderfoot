/**
 * Smoke tests for Modules page.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../lib/api');
  return {
    ...actual,
    dataApi: {
      modules: vi.fn().mockResolvedValue([]),
      modulesStatus: vi.fn().mockResolvedValue({}),
      moduleCategories: vi.fn().mockResolvedValue([]),
      enableModule: vi.fn(),
      disableModule: vi.fn(),
    },
  };
});

import Modules from '../../pages/Modules';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('Modules', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the page header', async () => {
    render(<Modules />, { wrapper: createWrapper() });
    expect(screen.getByText('Modules')).toBeTruthy();
  });

  it('shows empty state when no modules found', async () => {
    render(<Modules />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/No modules found/i)).toBeTruthy();
    });
  });
});
