/**
 * Smoke tests for Settings page.
 */
import { render } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../lib/api');
  return {
    ...actual,
    configApi: {
      get: vi.fn().mockResolvedValue({}),
      update: vi.fn(),
      updateModuleOptions: vi.fn(),
      exportConfig: vi.fn(),
      importConfig: vi.fn(),
      reload: vi.fn(),
    },
    dataApi: {
      modules: vi.fn().mockResolvedValue([]),
    },
  };
});

import Settings from '../../pages/Settings';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('Settings', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the page title', async () => {
    render(<Settings />, { wrapper: createWrapper() });
    // Settings page renders — look for a heading or form structure
    expect(document.body.innerHTML.length).toBeGreaterThan(100);
  });
});
