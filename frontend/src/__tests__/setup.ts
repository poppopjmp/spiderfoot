/**
 * Vitest setup — runs before every test file.
 *
 * Provides DOM assertion matchers via @testing-library/jest-dom
 * and stubs browser APIs not available in jsdom.
 */

import '@testing-library/jest-dom/vitest';

/* Stub window.matchMedia (used by Tailwind/responsive components) */
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

/* Stub IntersectionObserver (used by virtualised lists) */
class IntersectionObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  value: IntersectionObserverStub,
});

/* Stub ResizeObserver */
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: ResizeObserverStub,
});
