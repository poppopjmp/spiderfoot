/**
 * Safe localStorage wrapper that handles QuotaExceededError and
 * enforces a per-value size limit to prevent unbounded growth.
 *
 * All keys are prefixed with `sf_` to prevent collisions with
 * other applications on the same origin.
 *
 * Sensitive data (tokens, keys) should use the `sensitive*` variants
 * which prefer sessionStorage (cleared on tab close) and fall back
 * to localStorage if sessionStorage is unavailable.
 */

/** Maximum bytes for a single localStorage value (100 KB). */
const MAX_VALUE_BYTES = 100_000;

/** Namespace prefix for all SpiderFoot storage keys. */
const KEY_PREFIX = 'sf_';

/** Apply namespace prefix if not already present. */
function prefixKey(key: string): string {
  return key.startsWith(KEY_PREFIX) ? key : KEY_PREFIX + key;
}

/**
 * Write a value to localStorage.  Silently truncates values that
 * exceed MAX_VALUE_BYTES and catches QuotaExceededError so auth
 * tokens and other critical writes are never broken by oversized
 * report caches.
 */
export function safeSetItem(key: string, value: string): void {
  const prefixed = prefixKey(key);
  try {
    const trimmed = value.length > MAX_VALUE_BYTES
      ? value.slice(0, MAX_VALUE_BYTES)
      : value;
    localStorage.setItem(prefixed, trimmed);
  } catch {
    // QuotaExceededError — evict the oldest sf_ws_report_* / sf_report_* keys
    try {
      const keysToEvict: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && (k.startsWith('sf_ws_report_') || k.startsWith('sf_report_'))) {
          keysToEvict.push(k);
        }
      }
      // Remove up to 5 oldest report keys to free space
      keysToEvict.slice(0, 5).forEach((k) => localStorage.removeItem(k));
      // Retry once
      localStorage.setItem(prefixed, value.slice(0, MAX_VALUE_BYTES));
    } catch {
      // Storage is truly full — give up silently
      console.warn('[safeStorage] localStorage quota exceeded, write skipped for:', prefixed);
    }
  }
}

/**
 * Read a value from localStorage with namespace prefix.
 */
export function safeGetItem(key: string): string | null {
  const prefixed = prefixKey(key);
  try {
    return localStorage.getItem(prefixed);
  } catch {
    return null;
  }
}

/**
 * Remove a value from localStorage with namespace prefix.
 */
export function safeRemoveItem(key: string): void {
  const prefixed = prefixKey(key);
  try {
    localStorage.removeItem(prefixed);
  } catch {
    // ignore
  }
}

// -----------------------------------------------------------------
// Sensitive storage — prefers sessionStorage (dies on tab close)
// -----------------------------------------------------------------

function getSecureStore(): Storage {
  try {
    // Test sessionStorage access
    sessionStorage.setItem('__sf_test', '1');
    sessionStorage.removeItem('__sf_test');
    return sessionStorage;
  } catch {
    // Fall back to localStorage (Firefox private mode blocks sessionStorage)
    return localStorage;
  }
}

/** Write sensitive data (tokens, keys). Prefers sessionStorage. */
export function sensitiveSetItem(key: string, value: string): void {
  const prefixed = prefixKey(key);
  try {
    getSecureStore().setItem(prefixed, value);
  } catch {
    // Silently fail — don't leak errors about credential storage
  }
}

/** Read sensitive data. Checks sessionStorage first, then localStorage. */
export function sensitiveGetItem(key: string): string | null {
  const prefixed = prefixKey(key);
  try {
    return sessionStorage.getItem(prefixed) ?? localStorage.getItem(prefixed);
  } catch {
    try {
      return localStorage.getItem(prefixed);
    } catch {
      return null;
    }
  }
}

/** Remove sensitive data from both storage backends. */
export function sensitiveRemoveItem(key: string): void {
  const prefixed = prefixKey(key);
  try { sessionStorage.removeItem(prefixed); } catch { /* ignore */ }
  try { localStorage.removeItem(prefixed); } catch { /* ignore */ }
}

/**
 * Clear all SpiderFoot-prefixed keys from both storage backends.
 * Use on logout to ensure complete cleanup.
 */
export function clearAllSpiderFootData(): void {
  for (const store of [localStorage, sessionStorage]) {
    try {
      const keys: string[] = [];
      for (let i = 0; i < store.length; i++) {
        const k = store.key(i);
        if (k?.startsWith(KEY_PREFIX)) keys.push(k);
      }
      keys.forEach((k) => store.removeItem(k));
    } catch {
      // ignore storage access errors
    }
  }
}
