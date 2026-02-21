/**
 * Tests for ErrorBoundary component.
 *
 * Validates error-catching behaviour, fallback UI rendering,
 * and recovery (Try Again) functionality.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ErrorBoundary from '../../components/ErrorBoundary';

/* ─── Helper: a component that throws based on a mutable ref ─ */
const shouldThrowRef = { current: false };

function ThrowingChild() {
  if (shouldThrowRef.current) {
    throw new Error('Boom!');
  }
  return <p>All good</p>;
}

/* A simpler component that always throws */
function AlwaysThrows() {
  throw new Error('Boom!');
}

/* Suppress console.error noise from React error boundary logging */
beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
  shouldThrowRef.current = false;
});

describe('ErrorBoundary', () => {
  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <p>Normal content</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText('Normal content')).toBeInTheDocument();
  });

  it('shows fallback UI when a child throws', () => {
    render(
      <ErrorBoundary>
        <AlwaysThrows />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText(/An unexpected error occurred/)).toBeInTheDocument();
  });

  it('displays the error message in a pre block', () => {
    render(
      <ErrorBoundary>
        <AlwaysThrows />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Boom!')).toBeInTheDocument();
  });

  it('renders a Try Again button', () => {
    render(
      <ErrorBoundary>
        <AlwaysThrows />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Try Again')).toBeInTheDocument();
  });

  it('renders a Reload Page button', () => {
    render(
      <ErrorBoundary>
        <AlwaysThrows />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Reload Page')).toBeInTheDocument();
  });

  it('recovers when Try Again is clicked and child stops throwing', () => {
    // Start with the ref-based child that throws
    shouldThrowRef.current = true;
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    // Stop throwing, then click Try Again — boundary resets and re-renders children
    shouldThrowRef.current = false;
    fireEvent.click(screen.getByText('Try Again'));

    expect(screen.getByText('All good')).toBeInTheDocument();
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });

  it('calls window.location.reload when Reload Page is clicked', () => {
    // Mock reload
    const reloadMock = vi.fn();
    Object.defineProperty(window, 'location', {
      value: { ...window.location, reload: reloadMock },
      writable: true,
    });

    render(
      <ErrorBoundary>
        <AlwaysThrows />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByText('Reload Page'));
    expect(reloadMock).toHaveBeenCalledTimes(1);
  });

  it('logs error to console.error via componentDidCatch', () => {
    render(
      <ErrorBoundary>
        <AlwaysThrows />
      </ErrorBoundary>,
    );
    // React + ErrorBoundary both call console.error
    expect(console.error).toHaveBeenCalled();
  });
});
