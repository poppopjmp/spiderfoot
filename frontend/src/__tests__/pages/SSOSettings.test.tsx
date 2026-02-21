/**
 * Smoke tests for SSOSettings page.
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
      get: vi.fn().mockResolvedValue({ data: { providers: [] } }),
      patch: vi.fn().mockResolvedValue({ data: {} }),
    },
  };
});

import SSOSettingsPage from '../../pages/SSOSettings';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('SSOSettingsPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders page heading', async () => {
    render(<SSOSettingsPage />, { wrapper: createWrapper() });
    expect(screen.getByText('SSO Settings')).toBeTruthy();
  });

  it('sets document title', async () => {
    render(<SSOSettingsPage />, { wrapper: createWrapper() });
    expect(document.title).toContain('SSO Settings');
  });
});
