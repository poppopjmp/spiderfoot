/**
 * Safe localStorage wrapper that handles QuotaExceededError and
 * enforces a per-value size limit to prevent unbounded growth.
 */

/** Maximum bytes for a single localStorage value (100 KB). */
const MAX_VALUE_BYTES = 100_000;

/**
 * Write a value to localStorage.  Silently truncates values that
 * exceed MAX_VALUE_BYTES and catches QuotaExceededError so auth
 * tokens and other critical writes are never broken by oversized
 * report caches.
 */
export function safeSetItem(key: string, value: string): void {
  try {
    const trimmed = value.length > MAX_VALUE_BYTES
      ? value.slice(0, MAX_VALUE_BYTES)
      : value;
    localStorage.setItem(key, trimmed);
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
      localStorage.setItem(key, value.slice(0, MAX_VALUE_BYTES));
    } catch {
      // Storage is truly full — give up silently
      console.warn('[safeStorage] localStorage quota exceeded, write skipped for:', key);
    }
  }
}
