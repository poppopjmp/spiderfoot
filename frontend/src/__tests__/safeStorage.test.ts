/**
 * Tests for the safeStorage utility.
 *
 * Verifies truncation, normal writes, quota handling, key prefixing,
 * sensitive storage, and cleanup functionality.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  safeSetItem,
  safeGetItem,
  safeRemoveItem,
  sensitiveSetItem,
  sensitiveGetItem,
  sensitiveRemoveItem,
  clearAllSpiderFootData,
} from '../lib/safeStorage';

describe('safeSetItem', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('writes a normal value to localStorage with sf_ prefix', () => {
    safeSetItem('test_key', 'hello');
    // Key should be stored with sf_ prefix
    expect(localStorage.getItem('sf_test_key')).toBe('hello');
  });

  it('does not double-prefix keys starting with sf_', () => {
    safeSetItem('sf_already_prefixed', 'value');
    expect(localStorage.getItem('sf_already_prefixed')).toBe('value');
    // Should NOT create sf_sf_already_prefixed
    expect(localStorage.getItem('sf_sf_already_prefixed')).toBeNull();
  });

  it('truncates values exceeding 100 KB', () => {
    const longValue = 'x'.repeat(200_000);
    safeSetItem('big_key', longValue);
    const stored = localStorage.getItem('sf_big_key');
    expect(stored).not.toBeNull();
    expect(stored!.length).toBe(100_000);
  });

  it('does not throw on QuotaExceededError', () => {
    const original = Storage.prototype.setItem;
    let callCount = 0;
    Storage.prototype.setItem = vi.fn(() => {
      callCount++;
      if (callCount <= 2) {
        const err = new DOMException('quota exceeded', 'QuotaExceededError');
        throw err;
      }
    });

    expect(() => safeSetItem('key', 'value')).not.toThrow();

    Storage.prototype.setItem = original;
  });

  it('evicts sf_report_* keys on quota error and retries', () => {
    localStorage.setItem('sf_report_1', 'cached_report');
    localStorage.setItem('sf_report_2', 'cached_report_2');

    const originalSetItem = Storage.prototype.setItem;
    let callCount = 0;
    Storage.prototype.setItem = vi.fn(function (this: Storage, key: string, value: string) {
      callCount++;
      if (callCount === 1) {
        throw new DOMException('quota exceeded', 'QuotaExceededError');
      }
      originalSetItem.call(this, key, value);
    });

    safeSetItem('new_key', 'new_value');

    Storage.prototype.setItem = originalSetItem;
  });
});

describe('safeGetItem / safeRemoveItem', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('reads back values with prefix', () => {
    safeSetItem('read_test', 'hello');
    expect(safeGetItem('read_test')).toBe('hello');
  });

  it('returns null for missing keys', () => {
    expect(safeGetItem('nonexistent')).toBeNull();
  });

  it('removes items with prefix', () => {
    safeSetItem('remove_test', 'data');
    safeRemoveItem('remove_test');
    expect(safeGetItem('remove_test')).toBeNull();
  });
});

describe('sensitiveStorage', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('stores sensitive data in sessionStorage', () => {
    sensitiveSetItem('token', 'my-secret-jwt');
    expect(sessionStorage.getItem('sf_token')).toBe('my-secret-jwt');
  });

  it('reads sensitive data back', () => {
    sensitiveSetItem('api_key', 'key-123');
    expect(sensitiveGetItem('api_key')).toBe('key-123');
  });

  it('removes sensitive data from both stores', () => {
    sensitiveSetItem('token', 'jwt');
    // Also put in localStorage to verify both are cleaned
    localStorage.setItem('sf_token', 'jwt-local');
    sensitiveRemoveItem('token');
    expect(sessionStorage.getItem('sf_token')).toBeNull();
    expect(localStorage.getItem('sf_token')).toBeNull();
  });
});

describe('clearAllSpiderFootData', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('removes all sf_ prefixed keys from both stores', () => {
    localStorage.setItem('sf_token', 'jwt');
    localStorage.setItem('sf_settings', 'data');
    localStorage.setItem('other_app_key', 'keep');
    sessionStorage.setItem('sf_session', 'sess');

    clearAllSpiderFootData();

    expect(localStorage.getItem('sf_token')).toBeNull();
    expect(localStorage.getItem('sf_settings')).toBeNull();
    expect(sessionStorage.getItem('sf_session')).toBeNull();
    // Non-sf keys should be preserved
    expect(localStorage.getItem('other_app_key')).toBe('keep');
  });
});
