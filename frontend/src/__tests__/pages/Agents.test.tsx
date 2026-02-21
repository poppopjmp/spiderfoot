/**
 * Smoke tests for Agents page.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../lib/api');
  return {
    ...actual,
    agentsApi: {
      status: vi.fn().mockResolvedValue({ agents: [], total: 0 }),
    },
    aiConfigApi: {
      presets: vi.fn().mockResolvedValue({ presets: [] }),
      targetTypes: vi.fn().mockResolvedValue([]),
      stealthLevels: vi.fn().mockResolvedValue([]),
      recommend: vi.fn().mockResolvedValue({}),
      feedback: vi.fn().mockResolvedValue({}),
    },
  };
});

import AgentsPage from '../../pages/Agents';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AgentsPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders page heading', async () => {
    render(<AgentsPage />, { wrapper: createWrapper() });
    expect(screen.getByText('AI Agents & Scan Intelligence')).toBeTruthy();
  });

  it('sets document title', async () => {
    render(<AgentsPage />, { wrapper: createWrapper() });
    expect(document.title).toContain('Agents');
  });
});
