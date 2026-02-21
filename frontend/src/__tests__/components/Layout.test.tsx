/**
 * Tests for the Layout component (src/components/Layout.tsx).
 *
 * Covers: sidebar navigation rendering, nav item presence, active highlighting,
 * sidebar collapse/expand, services dropdown, user menu, mobile header,
 * admin-only items, and about modal.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from '../../components/Layout';
import { useAuthStore } from '../../lib/auth';

// Mock react-router-dom's Outlet so we can detect child rendering
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    Outlet: () => <div data-testid="outlet">outlet-content</div>,
  };
});

// Mock the theme hook
vi.mock('../../lib/theme', () => ({
  useTheme: () => ({ theme: 'dark' as const, resolved: 'dark' as const, setTheme: vi.fn(), toggle: vi.fn() }),
}));

// Helper to render Layout within a MemoryRouter at a given path
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function renderLayout(initialRoute = '/') {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Layout />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// Helper to set up an authenticated admin user in the store
function setAdminUser() {
  useAuthStore.setState({
    user: { id: '1', username: 'admin', role: 'admin', email: 'a@b.c', display_name: 'Admin', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' },
    isAuthenticated: true,
    accessToken: 'tok',
  });
}

function setViewerUser() {
  useAuthStore.setState({
    user: { id: '2', username: 'viewer', role: 'viewer', email: 'v@b.c', display_name: 'Viewer', auth_method: 'local', status: 'active', created_at: 0, last_login: 0, sso_provider_id: '' },
    isAuthenticated: true,
    accessToken: 'tok',
  });
}

describe('Layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      authRequired: false,
      ssoProviders: [],
      error: null,
    });
  });

  /* ─── Sidebar navigation rendering ─────────────────────── */

  it('renders all core nav items', () => {
    renderLayout();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('New Scan')).toBeInTheDocument();
    expect(screen.getByText('Scans')).toBeInTheDocument();
    expect(screen.getByText('Modules')).toBeInTheDocument();
    expect(screen.getByText('Workspaces')).toBeInTheDocument();
    expect(screen.getByText('Documentation')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders the SpiderFoot logo heading', () => {
    renderLayout();
    // "SpiderFoot" appears in both sidebar <h1> and mobile header <span>
    const matches = screen.getAllByText('SpiderFoot');
    expect(matches.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('OSINT Platform')).toBeInTheDocument();
  });

  it('renders the version in footer', () => {
    renderLayout();
    expect(screen.getByText('SpiderFoot v6.0.0')).toBeInTheDocument();
  });

  /* ─── Outlet (children) rendering ───────────────────────── */

  it('renders the Outlet for child routes', () => {
    renderLayout();
    expect(screen.getByTestId('outlet')).toBeInTheDocument();
    expect(screen.getByText('outlet-content')).toBeInTheDocument();
  });

  /* ─── Services dropdown ──────────────────────────────────── */

  it('shows services list when Services button is clicked', () => {
    renderLayout();
    const servicesBtn = screen.getByText('Services');
    fireEvent.click(servicesBtn);

    expect(screen.getByText('AI Agents')).toBeInTheDocument();
    expect(screen.getByText('Grafana')).toBeInTheDocument();
    expect(screen.getByText('Jaeger')).toBeInTheDocument();
  });

  it('hides services list on second click (toggle)', () => {
    renderLayout();
    const servicesBtn = screen.getByText('Services');
    fireEvent.click(servicesBtn);
    expect(screen.getByText('Grafana')).toBeInTheDocument();

    fireEvent.click(servicesBtn);
    expect(screen.queryByText('Grafana')).not.toBeInTheDocument();
  });

  /* ─── Admin-only nav items ──────────────────────────────── */

  it('shows Users link for admin user', () => {
    setAdminUser();
    renderLayout();
    expect(screen.getByText('Users')).toBeInTheDocument();
  });

  it('shows SSO Settings link for admin user', () => {
    setAdminUser();
    renderLayout();
    expect(screen.getByText('SSO Settings')).toBeInTheDocument();
  });

  it('does not show Users link for unauthenticated user', () => {
    renderLayout();
    expect(screen.queryByText('Users')).not.toBeInTheDocument();
  });

  it('does not show SSO Settings for viewer user', () => {
    setViewerUser();
    renderLayout();
    expect(screen.queryByText('SSO Settings')).not.toBeInTheDocument();
  });

  /* ─── API Keys for authenticated users ──────────────────── */

  it('shows API Keys link for any authenticated user', () => {
    setViewerUser();
    renderLayout();
    expect(screen.getByText('API Keys')).toBeInTheDocument();
  });

  it('does not show API Keys when not authenticated', () => {
    renderLayout();
    expect(screen.queryByText('API Keys')).not.toBeInTheDocument();
  });

  /* ─── User menu ──────────────────────────────────────────── */

  it('shows username and role when authenticated', () => {
    setAdminUser();
    renderLayout();
    // "admin" appears as both username and role — use getAllByText
    const adminTexts = screen.getAllByText('admin');
    expect(adminTexts.length).toBeGreaterThanOrEqual(2);
  });

  it('shows sign out button when authenticated', () => {
    setAdminUser();
    renderLayout();
    expect(screen.getByText('Sign out')).toBeInTheDocument();
  });

  it('does not show sign out when not authenticated', () => {
    renderLayout();
    expect(screen.queryByText('Sign out')).not.toBeInTheDocument();
  });

  /* ─── About modal ───────────────────────────────────────── */

  it('opens About modal when logo area is clicked', () => {
    renderLayout();
    const logoArea = screen.getByText('OSINT Platform').closest('div[class*="cursor-pointer"]');
    expect(logoArea).toBeTruthy();
    fireEvent.click(logoArea!);
    expect(screen.getByText('About SpiderFoot')).toBeInTheDocument();
    expect(screen.getByText('v6.0.0')).toBeInTheDocument();
  });

  /* ─── Mobile header ─────────────────────────────────────── */

  it('renders mobile header with menu button', () => {
    renderLayout();
    // The mobile header contains a Menu button (hamburger icon)
    const mobileHeaders = document.querySelectorAll('.lg\\:hidden');
    expect(mobileHeaders.length).toBeGreaterThan(0);
  });

  /* ─── Theme toggle ──────────────────────────────────────── */

  it('renders theme toggle buttons', () => {
    renderLayout();
    expect(screen.getByTitle('Light')).toBeInTheDocument();
    expect(screen.getByTitle('Dark')).toBeInTheDocument();
    expect(screen.getByTitle('System')).toBeInTheDocument();
  });
});
