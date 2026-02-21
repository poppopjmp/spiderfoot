/**
 * Smoke tests for CommandPalette component.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../lib/api');
  return {
    ...actual,
    scanApi: {
      list: vi.fn().mockResolvedValue({ scans: [], total: 0 }),
    },
  };
});

vi.mock('../../lib/auth', () => ({
  useAuthStore: vi.fn(() => ({
    hasPermission: () => true,
  })),
}));

import { CommandPalette } from '../../components/CommandPalette';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('CommandPalette', () => {
  beforeEach(() => vi.clearAllMocks());

  it('is hidden by default', () => {
    const { container } = render(<CommandPalette />, { wrapper: createWrapper() });
    // The palette overlay should not be visible
    expect(container.querySelector('[role="combobox"]')).toBeNull();
  });

  it('opens on Ctrl+K keyboard shortcut', () => {
    render(<CommandPalette />, { wrapper: createWrapper() });
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    expect(screen.getByRole('combobox')).toBeTruthy();
  });

  it('renders search input when open', () => {
    render(<CommandPalette />, { wrapper: createWrapper() });
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    const input = screen.getByRole('combobox');
    expect(input).toBeTruthy();
    expect(input.getAttribute('aria-expanded')).toBe('true');
  });

  it('shows static page items in dropdown', () => {
    render(<CommandPalette />, { wrapper: createWrapper() });
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    expect(screen.getByText('Dashboard')).toBeTruthy();
    expect(screen.getByText('New Scan')).toBeTruthy();
    expect(screen.getByText('Settings')).toBeTruthy();
  });

  it('filters results based on search query', () => {
    render(<CommandPalette />, { wrapper: createWrapper() });
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'settings' } });
    expect(screen.getByText('Settings')).toBeTruthy();
    // Dashboard should be filtered out
    expect(screen.queryByText('Dashboard')).toBeNull();
  });

  it('closes on Escape key', () => {
    const { container } = render(<CommandPalette />, { wrapper: createWrapper() });
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    expect(screen.getByRole('combobox')).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(container.querySelector('[role="combobox"]')).toBeNull();
  });

  it('shows listbox with options', () => {
    render(<CommandPalette />, { wrapper: createWrapper() });
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    expect(screen.getByRole('listbox')).toBeTruthy();
    const options = screen.getAllByRole('option');
    expect(options.length).toBeGreaterThan(0);
  });
});
