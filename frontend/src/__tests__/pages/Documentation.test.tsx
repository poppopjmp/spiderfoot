/**
 * Smoke tests for Documentation page.
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
      ...((actual.dataApi || {}) as Record<string, unknown>),
      modules: vi.fn().mockResolvedValue({ modules: [], total: 0 }),
      entityTypes: vi.fn().mockResolvedValue([]),
      moduleCategories: vi.fn().mockResolvedValue([]),
    },
  };
});

import DocumentationPage from '../../pages/Documentation';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('DocumentationPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders page heading', async () => {
    render(<DocumentationPage />, { wrapper: createWrapper() });
    expect(screen.getByText('Documentation')).toBeTruthy();
  });

  it('sets document title', async () => {
    render(<DocumentationPage />, { wrapper: createWrapper() });
    expect(document.title).toContain('Documentation');
  });
});
