/**
 * Tests for shared UI components from src/components/ui/index.tsx.
 *
 * Covers: StatusBadge, Toast, Tabs, ConfirmDialog, ModalShell,
 * Expandable, EmptyState, PageHeader, ProgressBar.
 */
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  StatusBadge,
  Toast,
  Tabs,
  ConfirmDialog,
  ModalShell,
  Expandable,
  EmptyState,
  PageHeader,
  ProgressBar,
} from '../../components/ui';
import { AlertCircle } from 'lucide-react';

/* ─── StatusBadge ───────────────────────────────────────── */

describe('StatusBadge', () => {
  it('renders the status text', () => {
    render(<StatusBadge status="FINISHED" />);
    expect(screen.getByText('FINISHED')).toBeInTheDocument();
  });

  it('applies badge-success class for FINISHED status', () => {
    const { container } = render(<StatusBadge status="FINISHED" />);
    const badge = container.querySelector('.badge');
    expect(badge).toHaveClass('badge-success');
  });

  it('applies badge-running class for RUNNING status', () => {
    const { container } = render(<StatusBadge status="RUNNING" />);
    const badge = container.querySelector('.badge');
    expect(badge).toHaveClass('badge-running');
  });

  it('applies badge-running class for STARTING status', () => {
    const { container } = render(<StatusBadge status="STARTING" />);
    const badge = container.querySelector('.badge');
    expect(badge).toHaveClass('badge-running');
  });

  it('applies badge-critical class for ERROR-FAILED status', () => {
    const { container } = render(<StatusBadge status="ERROR-FAILED" />);
    const badge = container.querySelector('.badge');
    expect(badge).toHaveClass('badge-critical');
  });

  it('applies badge-medium class for ABORTED status', () => {
    const { container } = render(<StatusBadge status="ABORTED" />);
    const badge = container.querySelector('.badge');
    expect(badge).toHaveClass('badge-medium');
  });

  it('applies badge-skipped class for SKIPPED status', () => {
    const { container } = render(<StatusBadge status="SKIPPED" />);
    const badge = container.querySelector('.badge');
    expect(badge).toHaveClass('badge-skipped');
  });

  it('applies badge-info class for unknown statuses', () => {
    const { container } = render(<StatusBadge status="UNKNOWN" />);
    const badge = container.querySelector('.badge');
    expect(badge).toHaveClass('badge-info');
  });

  it('renders running dot for RUNNING', () => {
    const { container } = render(<StatusBadge status="RUNNING" />);
    expect(container.querySelector('.status-dot-running')).toBeInTheDocument();
  });

  it('renders finished dot for FINISHED', () => {
    const { container } = render(<StatusBadge status="FINISHED" />);
    expect(container.querySelector('.status-dot-finished')).toBeInTheDocument();
  });

  it('renders failed dot for ERROR-FAILED', () => {
    const { container } = render(<StatusBadge status="ERROR-FAILED" />);
    expect(container.querySelector('.status-dot-failed')).toBeInTheDocument();
  });
});

/* ─── Toast ─────────────────────────────────────────────── */

describe('Toast', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('renders message text', () => {
    render(<Toast message="Operation succeeded" onClose={vi.fn()} type="success" />);
    expect(screen.getByText('Operation succeeded')).toBeInTheDocument();
  });

  it('renders with success styling', () => {
    const { container } = render(<Toast message="OK" onClose={vi.fn()} type="success" />);
    // success config has bg-green-900/20
    expect(container.firstChild).toHaveClass('bg-green-900/20');
  });

  it('renders with error styling', () => {
    const { container } = render(<Toast message="Fail" onClose={vi.fn()} type="error" />);
    expect(container.firstChild).toHaveClass('bg-red-900/20');
  });

  it('renders with warning styling', () => {
    const { container } = render(<Toast message="Warn" onClose={vi.fn()} type="warning" />);
    expect(container.firstChild).toHaveClass('bg-yellow-900/20');
  });

  it('renders with info styling by default', () => {
    const { container } = render(<Toast message="Info" onClose={vi.fn()} />);
    expect(container.firstChild).toHaveClass('bg-blue-900/20');
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(<Toast message="Test" onClose={onClose} />);
    // The close button is the last button inside the toast
    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[0]);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('auto-closes after 5 seconds', () => {
    const onClose = vi.fn();
    render(<Toast message="Auto" onClose={onClose} />);
    expect(onClose).not.toHaveBeenCalled();
    act(() => { vi.advanceTimersByTime(5000); });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not auto-close before 5 seconds', () => {
    const onClose = vi.fn();
    render(<Toast message="Not yet" onClose={onClose} />);
    act(() => { vi.advanceTimersByTime(4999); });
    expect(onClose).not.toHaveBeenCalled();
  });
});

/* ─── Tabs ──────────────────────────────────────────────── */

describe('Tabs', () => {
  const tabDef = [
    { key: 'overview' as const, label: 'Overview' },
    { key: 'details' as const, label: 'Details' },
    { key: 'settings' as const, label: 'Settings' },
  ];

  it('renders all tab labels', () => {
    render(<Tabs tabs={tabDef} active="overview" onChange={vi.fn()} />);
    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Details')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('marks the active tab with active class', () => {
    render(<Tabs tabs={tabDef} active="details" onChange={vi.fn()} />);
    expect(screen.getByText('Details').closest('button')).toHaveClass('tab-button-active');
    expect(screen.getByText('Overview').closest('button')).toHaveClass('tab-button');
  });

  it('calls onChange with the correct key when a tab is clicked', () => {
    const onChange = vi.fn();
    render(<Tabs tabs={tabDef} active="overview" onChange={onChange} />);
    fireEvent.click(screen.getByText('Settings'));
    expect(onChange).toHaveBeenCalledWith('settings');
  });

  it('renders count badge when provided', () => {
    const tabs = [
      { key: 'items' as const, label: 'Items', count: 42 },
    ];
    render(<Tabs tabs={tabs} active="items" onChange={vi.fn()} />);
    expect(screen.getByText('42')).toBeInTheDocument();
  });
});

/* ─── ConfirmDialog ─────────────────────────────────────── */

describe('ConfirmDialog', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(
      <ConfirmDialog
        open={false}
        title="Delete?"
        message="This is permanent."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders title and message when open', () => {
    render(
      <ConfirmDialog
        open={true}
        title="Delete scan?"
        message="This cannot be undone."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText('Delete scan?')).toBeInTheDocument();
    expect(screen.getByText('This cannot be undone.')).toBeInTheDocument();
  });

  it('renders custom confirm label', () => {
    render(
      <ConfirmDialog
        open={true}
        title="Remove"
        message="Sure?"
        confirmLabel="Yes, remove"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText('Yes, remove')).toBeInTheDocument();
  });

  it('calls onConfirm when confirm button is clicked', () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open={true}
        title="OK?"
        message="Confirm?"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText('Confirm'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when cancel button is clicked', () => {
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open={true}
        title="OK?"
        message="Cancel?"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    fireEvent.click(screen.getByText('Cancel'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('applies btn-danger class when danger is true', () => {
    render(
      <ConfirmDialog
        open={true}
        title="Danger"
        message="Destructive action"
        danger={true}
        confirmLabel="Delete"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText('Delete')).toHaveClass('btn-danger');
  });

  it('applies btn-primary class when danger is false', () => {
    render(
      <ConfirmDialog
        open={true}
        title="Safe"
        message="Safe action"
        danger={false}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText('Confirm')).toHaveClass('btn-primary');
  });
});

/* ─── ModalShell ────────────────────────────────────────── */

describe('ModalShell', () => {
  it('renders title and children', () => {
    render(
      <ModalShell title="My Modal" onClose={vi.fn()}>
        <p>Modal body content</p>
      </ModalShell>,
    );
    expect(screen.getByText('My Modal')).toBeInTheDocument();
    expect(screen.getByText('Modal body content')).toBeInTheDocument();
  });

  it('renders with dialog role', () => {
    render(
      <ModalShell title="Accessible" onClose={vi.fn()}>
        content
      </ModalShell>,
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(
      <ModalShell title="Closable" onClose={onClose}>
        body
      </ModalShell>,
    );
    fireEvent.click(screen.getByLabelText('Close dialog'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn();
    render(
      <ModalShell title="Escape" onClose={onClose}>
        body
      </ModalShell>,
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('applies wide class when wide prop is true', () => {
    const { container } = render(
      <ModalShell title="Wide" onClose={vi.fn()} wide>
        wide content
      </ModalShell>,
    );
    const panel = container.querySelector('[tabindex="-1"]');
    expect(panel).toHaveClass('max-w-2xl');
  });

  it('applies narrow class when wide is false', () => {
    const { container } = render(
      <ModalShell title="Narrow" onClose={vi.fn()}>
        narrow
      </ModalShell>,
    );
    const panel = container.querySelector('[tabindex="-1"]');
    expect(panel).toHaveClass('max-w-lg');
  });
});

/* ─── Expandable ────────────────────────────────────────── */

describe('Expandable', () => {
  it('is collapsed by default and does not show children', () => {
    render(
      <Expandable title="More info">
        <p>Hidden content</p>
      </Expandable>,
    );
    expect(screen.getByText('More info')).toBeInTheDocument();
    expect(screen.queryByText('Hidden content')).not.toBeInTheDocument();
  });

  it('shows children when defaultOpen is true', () => {
    render(
      <Expandable title="Open" defaultOpen>
        <p>Visible content</p>
      </Expandable>,
    );
    expect(screen.getByText('Visible content')).toBeInTheDocument();
  });

  it('toggles content on click', () => {
    render(
      <Expandable title="Toggle">
        <p>Toggle content</p>
      </Expandable>,
    );
    expect(screen.queryByText('Toggle content')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Toggle'));
    expect(screen.getByText('Toggle content')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Toggle'));
    expect(screen.queryByText('Toggle content')).not.toBeInTheDocument();
  });
});

/* ─── EmptyState ────────────────────────────────────────── */

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(
      <EmptyState
        icon={AlertCircle}
        title="No results"
        description="Try a different query."
      />,
    );
    expect(screen.getByText('No results')).toBeInTheDocument();
    expect(screen.getByText('Try a different query.')).toBeInTheDocument();
  });

  it('renders action when provided', () => {
    render(
      <EmptyState
        icon={AlertCircle}
        title="Empty"
        action={<button>Create new</button>}
      />,
    );
    expect(screen.getByText('Create new')).toBeInTheDocument();
  });
});

/* ─── PageHeader ────────────────────────────────────────── */

describe('PageHeader', () => {
  it('renders title', () => {
    render(<PageHeader title="Dashboard" />);
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    render(<PageHeader title="Scans" subtitle="All running scans" />);
    expect(screen.getByText('All running scans')).toBeInTheDocument();
  });

  it('renders children actions', () => {
    render(
      <PageHeader title="Page">
        <button>New Scan</button>
      </PageHeader>,
    );
    expect(screen.getByText('New Scan')).toBeInTheDocument();
  });
});

/* ─── ProgressBar ───────────────────────────────────────── */

describe('ProgressBar', () => {
  it('renders progress at correct percentage', () => {
    const { container } = render(<ProgressBar value={50} max={100} showLabel />);
    expect(screen.getByText('50%')).toBeInTheDocument();
    const fill = container.querySelector('.progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('50%');
  });

  it('clamps at 100%', () => {
    const { container } = render(<ProgressBar value={200} max={100} showLabel />);
    expect(screen.getByText('100%')).toBeInTheDocument();
    const fill = container.querySelector('.progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('100%');
  });

  it('does not show label by default', () => {
    render(<ProgressBar value={30} />);
    expect(screen.queryByText('30%')).not.toBeInTheDocument();
  });
});
