/**
 * Tests for the Login page component.
 *
 * Mocks the Zustand auth store and react-router-dom to isolate
 * form rendering, validation, submission, and error display.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

/* ─── Mocks ─────────────────────────────────────────────── */

const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

// Mutable store values that individual tests can override
const storeFns = {
  login: vi.fn(),
  ldapLogin: vi.fn(),
  fetchAuthStatus: vi.fn(),
  setTokensFromUrl: vi.fn(),
  clearError: vi.fn(),
  isAuthenticated: false,
  ssoProviders: [] as { id: string; name: string; protocol: string; enabled: boolean; default_role: string }[],
  error: null as string | null,
};

vi.mock('../../lib/auth', () => ({
  useAuthStore: () => storeFns,
  // Re-export SSOProvider type helper (not actually used at runtime)
  SSOProvider: {},
}));

/* ─── Import after mocks ────────────────────────────────── */
import LoginPage from '../../pages/Login';

beforeEach(() => {
  vi.clearAllMocks();
  storeFns.login.mockReset();
  storeFns.ldapLogin.mockReset();
  storeFns.fetchAuthStatus.mockReset();
  storeFns.setTokensFromUrl.mockReset();
  storeFns.clearError.mockReset();
  storeFns.isAuthenticated = false;
  storeFns.ssoProviders = [];
  storeFns.error = null;
});

describe('LoginPage', () => {
  /* ── Basic rendering ──────────────────────────────────── */

  it('renders the SpiderFoot branding', () => {
    render(<LoginPage />);
    expect(screen.getByText('SpiderFoot')).toBeInTheDocument();
    expect(screen.getByText('OSINT Automation Platform')).toBeInTheDocument();
  });

  it('renders username and password fields', () => {
    render(<LoginPage />);
    expect(screen.getByPlaceholderText('Enter username')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter password')).toBeInTheDocument();
  });

  it('renders a Sign In button', () => {
    render(<LoginPage />);
    expect(screen.getByText('Sign In')).toBeInTheDocument();
  });

  it('renders labels for username and password', () => {
    render(<LoginPage />);
    expect(screen.getByText('Username')).toBeInTheDocument();
    expect(screen.getByText('Password')).toBeInTheDocument();
  });

  /* ── Submit button disabled state ─────────────────────── */

  it('disables Sign In when both fields are empty', () => {
    render(<LoginPage />);
    const btn = screen.getByText('Sign In').closest('button')!;
    expect(btn).toBeDisabled();
  });

  it('disables Sign In when only username is filled', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByPlaceholderText('Enter username'), 'admin');
    const btn = screen.getByText('Sign In').closest('button')!;
    expect(btn).toBeDisabled();
  });

  it('disables Sign In when only password is filled', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByPlaceholderText('Enter password'), 'secret');
    const btn = screen.getByText('Sign In').closest('button')!;
    expect(btn).toBeDisabled();
  });

  it('enables Sign In when both fields are filled', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByPlaceholderText('Enter username'), 'admin');
    await user.type(screen.getByPlaceholderText('Enter password'), 'secret');
    const btn = screen.getByText('Sign In').closest('button')!;
    expect(btn).not.toBeDisabled();
  });

  /* ── Form submission ──────────────────────────────────── */

  it('calls login with username and password on submit', async () => {
    storeFns.login.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByPlaceholderText('Enter username'), 'admin');
    await user.type(screen.getByPlaceholderText('Enter password'), 'pass123');
    await user.click(screen.getByText('Sign In').closest('button')!);

    await waitFor(() => {
      expect(storeFns.login).toHaveBeenCalledWith('admin', 'pass123');
    });
  });

  it('navigates to / on successful login', async () => {
    storeFns.login.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByPlaceholderText('Enter username'), 'admin');
    await user.type(screen.getByPlaceholderText('Enter password'), 'pass');
    await user.click(screen.getByText('Sign In').closest('button')!);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
    });
  });

  /* ── Error display ────────────────────────────────────── */

  it('shows error message from auth store', () => {
    storeFns.error = 'Invalid credentials';
    render(<LoginPage />);
    expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
  });

  it('handles login failure gracefully', async () => {
    storeFns.login.mockRejectedValue(new Error('Login failed'));
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByPlaceholderText('Enter username'), 'bad');
    await user.type(screen.getByPlaceholderText('Enter password'), 'wrong');
    await user.click(screen.getByText('Sign In').closest('button')!);

    // Should not crash — error is set in store
    await waitFor(() => {
      expect(storeFns.login).toHaveBeenCalled();
    });
  });

  /* ── Password visibility toggle ───────────────────────── */

  it('toggles password visibility when eye icon is clicked', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    const passwordInput = screen.getByPlaceholderText('Enter password');

    // Initially password type
    expect(passwordInput).toHaveAttribute('type', 'password');

    // Click the toggle button (the button inside the password field div)
    const toggleButtons = screen.getAllByRole('button').filter(
      (b) => !b.textContent?.includes('Sign In'),
    );
    // The first non-Sign-In button is the eye toggle
    await user.click(toggleButtons[0]);

    expect(passwordInput).toHaveAttribute('type', 'text');
  });

  /* ── Auth status fetch ────────────────────────────────── */

  it('calls fetchAuthStatus on mount', () => {
    render(<LoginPage />);
    expect(storeFns.fetchAuthStatus).toHaveBeenCalled();
  });

  it('calls setTokensFromUrl on mount (SSO callback)', () => {
    render(<LoginPage />);
    expect(storeFns.setTokensFromUrl).toHaveBeenCalled();
  });

  /* ── SSO providers ────────────────────────────────────── */

  it('shows LDAP tab when LDAP providers exist', () => {
    storeFns.ssoProviders = [
      { id: 'ldap1', name: 'Corp LDAP', protocol: 'ldap', enabled: true, default_role: 'analyst' },
    ];
    render(<LoginPage />);
    expect(screen.getByText('LDAP')).toBeInTheDocument();
    expect(screen.getByText('Local')).toBeInTheDocument();
  });

  it('does not show LDAP/Local tabs when no LDAP providers', () => {
    storeFns.ssoProviders = [];
    render(<LoginPage />);
    expect(screen.queryByText('LDAP')).not.toBeInTheDocument();
    expect(screen.queryByText('Local')).not.toBeInTheDocument();
  });

  it('renders OAuth SSO buttons when providers exist', () => {
    storeFns.ssoProviders = [
      { id: 'gh', name: 'GitHub SSO', protocol: 'oauth2', enabled: true, default_role: 'analyst' },
    ];
    render(<LoginPage />);
    expect(screen.getByText('GitHub SSO')).toBeInTheDocument();
  });

  it('renders SAML SSO buttons when providers exist', () => {
    storeFns.ssoProviders = [
      { id: 'okta', name: 'Okta SAML', protocol: 'saml', enabled: true, default_role: 'analyst' },
    ];
    render(<LoginPage />);
    expect(screen.getByText('Okta SAML')).toBeInTheDocument();
  });

  /* ── Redirect when already authenticated ──────────────── */

  it('navigates away if already authenticated', () => {
    storeFns.isAuthenticated = true;
    render(<LoginPage />);
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
  });

  /* ── Footer ───────────────────────────────────────────── */

  it('renders footer text', () => {
    render(<LoginPage />);
    expect(screen.getByText(/SpiderFoot OSINT Platform/)).toBeInTheDocument();
  });
});
