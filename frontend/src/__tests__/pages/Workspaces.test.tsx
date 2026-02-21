/**
 * Smoke tests for Workspaces page.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../lib/api');
  return {
    ...actual,
    workspaceApi: {
      list: vi.fn().mockResolvedValue({ workspaces: [] }),
      get: vi.fn().mockResolvedValue({}),
      targets: vi.fn().mockResolvedValue([]),
      summary: vi.fn().mockResolvedValue({}),
      create: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      clone: vi.fn().mockResolvedValue({}),
      setActive: vi.fn().mockResolvedValue({}),
      update: vi.fn().mockResolvedValue({}),
      addTarget: vi.fn().mockResolvedValue({}),
      deleteTarget: vi.fn().mockResolvedValue({}),
      multiScan: vi.fn().mockResolvedValue({}),
      linkScan: vi.fn().mockResolvedValue({}),
      unlinkScan: vi.fn().mockResolvedValue({}),
    },
    scanApi: {
      list: vi.fn().mockResolvedValue({ scans: [], total: 0 }),
    },
    agentsApi: {
      status: vi.fn().mockResolvedValue({ agents: [], total: 0 }),
    },
  };
});

import WorkspacesPage from '../../pages/Workspaces';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('WorkspacesPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders page heading', async () => {
    render(<WorkspacesPage />, { wrapper: createWrapper() });
    expect(screen.getByText('Workspaces')).toBeTruthy();
  });

  it('sets document title', async () => {
    render(<WorkspacesPage />, { wrapper: createWrapper() });
    expect(document.title).toContain('Workspaces');
  });
});
