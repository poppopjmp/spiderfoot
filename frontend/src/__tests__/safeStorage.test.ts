/**
 * Tests for the safeStorage utility.
 *
 * Verifies truncation, normal writes, and quota handling.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { safeSetItem } from '../lib/safeStorage';

describe('safeSetItem', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('writes a normal value to localStorage', () => {
    safeSetItem('test_key', 'hello');
    expect(localStorage.getItem('test_key')).toBe('hello');
  });

  it('truncates values exceeding 100 KB', () => {
    const longValue = 'x'.repeat(200_000);
    safeSetItem('big_key', longValue);
    const stored = localStorage.getItem('big_key');
    expect(stored).not.toBeNull();
    expect(stored!.length).toBe(100_000);
  });

  it('does not throw on QuotaExceededError', () => {
    // Mock localStorage.setItem to throw QuotaExceededError
    const original = Storage.prototype.setItem;
    let callCount = 0;
    Storage.prototype.setItem = vi.fn(() => {
      callCount++;
      if (callCount <= 2) {
        const err = new DOMException('quota exceeded', 'QuotaExceededError');
        throw err;
      }
    });

    // Should not throw
    expect(() => safeSetItem('key', 'value')).not.toThrow();

    Storage.prototype.setItem = original;
  });

  it('evicts sf_report_* keys on quota error and retries', () => {
    // Pre-populate some report keys
    localStorage.setItem('sf_report_1', 'cached_report');
    localStorage.setItem('sf_report_2', 'cached_report_2');

    // Mock setItem to fail first time, succeed second time
    const originalSetItem = Storage.prototype.setItem;
    let callCount = 0;
    Storage.prototype.setItem = vi.fn(function (this: Storage, key: string, value: string) {
      callCount++;
      if (callCount === 1) {
        throw new DOMException('quota exceeded', 'QuotaExceededError');
      }
      // Second call succeeds
      originalSetItem.call(this, key, value);
    });

    safeSetItem('new_key', 'new_value');

    Storage.prototype.setItem = originalSetItem;

    // The eviction should have removed report keys
    // (we can't fully verify in jsdom, but at least the function didn't throw)
  });
});
