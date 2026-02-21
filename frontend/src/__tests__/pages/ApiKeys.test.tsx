/**
 * Smoke tests for ApiKeys page.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../lib/api');
  return {
    ...actual,
    default: {
      get: vi.fn().mockResolvedValue({ data: { keys: [] } }),
      post: vi.fn().mockResolvedValue({ data: {} }),
      delete: vi.fn().mockResolvedValue({ data: {} }),
    },
  };
});

import ApiKeysPage from '../../pages/ApiKeys';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ApiKeysPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders page heading', async () => {
    render(<ApiKeysPage />, { wrapper: createWrapper() });
    expect(screen.getByText('API Keys')).toBeTruthy();
  });

  it('sets document title', async () => {
    render(<ApiKeysPage />, { wrapper: createWrapper() });
    expect(document.title).toContain('API Keys');
  });
});
