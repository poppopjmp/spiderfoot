/**
 * Tests for API helpers and the getErrorMessage utility.
 *
 * Covers: formatEpoch edge cases, formatDuration edge cases,
 * statusColor for all statuses, statusBadgeClass for all statuses,
 * getErrorMessage for different error shapes.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { formatEpoch, formatDuration, statusColor, statusBadgeClass } from '../../lib/api';
import { getErrorMessage } from '../../lib/errors';
import axios from 'axios';

// We need the real axios.isAxiosError, so don't mock axios here

beforeEach(() => {
  vi.clearAllMocks();
});

/* ─── formatEpoch edge cases ──────────────────────────────── */

describe('formatEpoch — edge cases', () => {
  it('returns dash for 0', () => {
    expect(formatEpoch(0)).toBe('\u2014');
  });

  it('returns dash for NaN-ish falsy values (coerced 0)', () => {
    // The function receives a number; 0 is the only falsy number
    expect(formatEpoch(0)).toBe('\u2014');
  });

  it('formats a negative epoch (before 1970) without crashing', () => {
    // Negative epoch: December 31, 1969
    const result = formatEpoch(-86400);
    expect(result).not.toBe('\u2014');
    expect(typeof result).toBe('string');
  });

  it('formats a future timestamp in seconds', () => {
    // Year 2030 roughly: 1893456000
    const result = formatEpoch(1893456000);
    expect(result).not.toBe('\u2014');
    expect(result).toMatch(/20[23]\d/); // 2030
  });

  it('formats a future timestamp in milliseconds', () => {
    const result = formatEpoch(1893456000000);
    expect(result).not.toBe('\u2014');
  });

  it('normalises seconds to ms (small value treated as seconds)', () => {
    // 1704067200 is in seconds (2024-01-01)
    const secResult = formatEpoch(1704067200);
    const msResult = formatEpoch(1704067200000);
    // Both should produce the same date string
    expect(secResult).toBe(msResult);
  });

  it('returns a non-empty string for epoch value 1', () => {
    const result = formatEpoch(1);
    expect(result).not.toBe('\u2014');
    expect(result.length).toBeGreaterThan(0);
  });
});

/* ─── formatDuration edge cases ───────────────────────────── */

describe('formatDuration — edge cases', () => {
  it('returns dash for 0 start epoch', () => {
    expect(formatDuration(0, 1000)).toBe('\u2014');
  });

  it('returns dash when end < start (negative duration)', () => {
    expect(formatDuration(1704067300, 1704067200)).toBe('\u2014');
  });

  it('returns "0s" for identical start and end', () => {
    expect(formatDuration(1704067200, 1704067200)).toBe('0s');
  });

  it('formats exactly 60 seconds as "1m 0s"', () => {
    expect(formatDuration(1704067200, 1704067260)).toBe('1m 0s');
  });

  it('formats exactly 3600 seconds as "1h 0m"', () => {
    expect(formatDuration(1704067200, 1704070800)).toBe('1h 0m');
  });

  it('formats multi-hour durations', () => {
    // 5 hours 30 minutes = 19800 seconds
    expect(formatDuration(1704067200, 1704087000)).toBe('5h 30m');
  });

  it('uses Date.now() when endEpoch is 0 (falsy)', () => {
    // Start epoch: a few seconds ago (should yield small result)
    const nowSec = Math.floor(Date.now() / 1000);
    const result = formatDuration(nowSec - 10, 0);
    expect(result).toMatch(/\d+s/);
  });

  it('handles ms-based timestamps correctly', () => {
    // 30 seconds in ms timestamps
    expect(formatDuration(1704067200000, 1704067230000)).toBe('30s');
  });
});

/* ─── statusColor — all statuses ──────────────────────────── */

describe('statusColor — all statuses', () => {
  it('RUNNING → running', () => {
    expect(statusColor('RUNNING')).toBe('status-text-running');
  });

  it('STARTING → running', () => {
    expect(statusColor('STARTING')).toBe('status-text-running');
  });

  it('FINISHED → finished', () => {
    expect(statusColor('FINISHED')).toBe('status-text-finished');
  });

  it('ABORTED → aborted', () => {
    expect(statusColor('ABORTED')).toBe('status-text-aborted');
  });

  it('STOPPED → aborted', () => {
    expect(statusColor('STOPPED')).toBe('status-text-aborted');
  });

  it('ERROR-FAILED → failed', () => {
    expect(statusColor('ERROR-FAILED')).toBe('status-text-failed');
  });

  it('SKIPPED → skipped', () => {
    expect(statusColor('SKIPPED')).toBe('status-text-skipped');
  });

  it('unknown status → default', () => {
    expect(statusColor('WHATEVER')).toBe('status-text-default');
  });

  it('is case-insensitive', () => {
    expect(statusColor('running')).toBe('status-text-running');
    expect(statusColor('Finished')).toBe('status-text-finished');
  });

  it('handles null/undefined gracefully', () => {
    expect(statusColor(null as unknown as string)).toBe('status-text-default');
    expect(statusColor(undefined as unknown as string)).toBe('status-text-default');
  });

  it('handles empty string', () => {
    expect(statusColor('')).toBe('status-text-default');
  });
});

/* ─── statusBadgeClass — all statuses ─────────────────────── */

describe('statusBadgeClass — all statuses', () => {
  it('RUNNING → badge badge-running', () => {
    expect(statusBadgeClass('RUNNING')).toBe('badge badge-running');
  });

  it('STARTING → badge badge-running', () => {
    expect(statusBadgeClass('STARTING')).toBe('badge badge-running');
  });

  it('FINISHED → badge badge-success', () => {
    expect(statusBadgeClass('FINISHED')).toBe('badge badge-success');
  });

  it('ABORTED → badge badge-medium', () => {
    expect(statusBadgeClass('ABORTED')).toBe('badge badge-medium');
  });

  it('STOPPED → badge badge-medium', () => {
    expect(statusBadgeClass('STOPPED')).toBe('badge badge-medium');
  });

  it('ERROR-FAILED → badge badge-critical', () => {
    expect(statusBadgeClass('ERROR-FAILED')).toBe('badge badge-critical');
  });

  it('SKIPPED → badge badge-skipped', () => {
    expect(statusBadgeClass('SKIPPED')).toBe('badge badge-skipped');
  });

  it('unknown → badge badge-info', () => {
    expect(statusBadgeClass('XYZ')).toBe('badge badge-info');
  });

  it('is case-insensitive', () => {
    expect(statusBadgeClass('finished')).toBe('badge badge-success');
  });

  it('handles null gracefully', () => {
    expect(statusBadgeClass(null as unknown as string)).toBe('badge badge-info');
  });
});

/* ─── getErrorMessage ─────────────────────────────────────── */

describe('getErrorMessage', () => {
  it('returns detail from AxiosError response data', () => {
    const axiosError = new axios.AxiosError('Request failed', '400', undefined, undefined, {
      status: 400,
      statusText: 'Bad Request',
      headers: {},
      config: { headers: {} } as never,
      data: { detail: 'Invalid credentials' },
    });
    expect(getErrorMessage(axiosError, 'fallback')).toBe('Invalid credentials');
  });

  it('returns fallback when AxiosError has no detail', () => {
    const axiosError = new axios.AxiosError('Request failed', '500', undefined, undefined, {
      status: 500,
      statusText: 'Internal Server Error',
      headers: {},
      config: { headers: {} } as never,
      data: {},
    });
    // No detail string → falls through to Error.message
    expect(getErrorMessage(axiosError, 'Server error')).toBe('Request failed');
  });

  it('returns Error.message for standard Error', () => {
    expect(getErrorMessage(new Error('something broke'), 'default')).toBe('something broke');
  });

  it('returns fallback for string error', () => {
    // A plain string is not an Error instance
    expect(getErrorMessage('oops', 'default msg')).toBe('default msg');
  });

  it('returns fallback for null', () => {
    expect(getErrorMessage(null, 'unknown error')).toBe('unknown error');
  });

  it('returns fallback for undefined', () => {
    expect(getErrorMessage(undefined, 'unknown error')).toBe('unknown error');
  });

  it('returns fallback for number', () => {
    expect(getErrorMessage(42, 'not a real error')).toBe('not a real error');
  });

  it('returns fallback for empty Error message', () => {
    expect(getErrorMessage(new Error(''), 'fallback')).toBe('fallback');
  });

  it('returns detail even if AxiosError also has message', () => {
    const axiosError = new axios.AxiosError('generic msg', '403', undefined, undefined, {
      status: 403,
      statusText: 'Forbidden',
      headers: {},
      config: { headers: {} } as never,
      data: { detail: 'Access denied' },
    });
    expect(getErrorMessage(axiosError, 'fallback')).toBe('Access denied');
  });
});
