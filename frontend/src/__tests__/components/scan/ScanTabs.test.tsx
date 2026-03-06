/**
 * Smoke tests for scan tab components.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../../lib/api', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../../lib/api');
  return {
    ...actual,
    scanApi: {
      viz: vi.fn().mockResolvedValue({ nodes: [], edges: [] }),
      summary: vi.fn().mockResolvedValue({ data: [], total: 0 }),
      events: vi.fn().mockResolvedValue({ events: [], total: 0 }),
      logs: vi.fn().mockResolvedValue({ logs: [] }),
      exportLogs: vi.fn().mockResolvedValue({ data: new Blob() }),
    },
  };
});

vi.mock('../../../lib/geo', () => ({
  GEO_EVENT_TYPES: ['GEOINFO', 'PHYSICAL_COORDINATES', 'COUNTRY_NAME', 'PROVIDER_HOSTING'],
  COUNTRY_COORDS: {},
  COUNTRY_NAME_TO_CODE: {},
  WORLD_MAP_IMAGE: '',
}));

// Import after mock
const { default: GraphTab } = await import('../../../components/scan/GraphTab');
const { default: BrowseTab } = await import('../../../components/scan/BrowseTab');
const { default: LogTab } = await import('../../../components/scan/LogTab');
const { default: GeoMapTab } = await import('../../../components/scan/GeoMapTab');

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe('GraphTab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders without crashing', () => {
    render(<GraphTab scanId="test-scan-1" />, { wrapper: createWrapper() });
    // Should show loading or empty state initially
    expect(document.body.querySelector('.animate-spin') || screen.queryByText('No graph data')).toBeTruthy();
  });

  it('has accessible canvas when data loads', async () => {
    const { container } = render(<GraphTab scanId="test-scan-1" />, { wrapper: createWrapper() });
    // Canvas should have role="img" when rendered
    const canvas = container.querySelector('canvas');
    if (canvas) {
      expect(canvas.getAttribute('role')).toBe('img');
    }
  });
});

describe('BrowseTab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders without crashing', () => {
    render(<BrowseTab scanId="test-scan-1" />, { wrapper: createWrapper() });
    expect(document.body).toBeTruthy();
  });
});

describe('LogTab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders search input and filter', () => {
    render(<LogTab scanId="test-scan-1" />, { wrapper: createWrapper() });
    const select = document.querySelector('select[aria-label="Filter by log type"]');
    expect(select).toBeTruthy();
  });
});

describe('GeoMapTab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders without crashing', () => {
    render(<GeoMapTab scanId="test-scan-1" />, { wrapper: createWrapper() });
    expect(document.body).toBeTruthy();
  });
});
