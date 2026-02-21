/**
 * Tests for API helper functions (formatEpoch, formatDuration, statusColor).
 */
import { describe, it, expect } from 'vitest';
import { formatEpoch, formatDuration, statusColor, statusBadgeClass } from '../lib/api';

describe('formatEpoch', () => {
  it('returns dash for zero', () => {
    expect(formatEpoch(0)).toBe('\u2014');
  });

  it('formats a Unix timestamp in seconds', () => {
    // 2024-01-01 00:00:00 UTC = 1704067200
    const result = formatEpoch(1704067200);
    expect(result).not.toBe('\u2014');
    expect(result.length).toBeGreaterThan(5);
  });

  it('formats a Unix timestamp in milliseconds', () => {
    const result = formatEpoch(1704067200000);
    expect(result).not.toBe('\u2014');
  });
});

describe('formatDuration', () => {
  it('returns dash for zero start', () => {
    expect(formatDuration(0, 100)).toBe('\u2014');
  });

  it('formats seconds', () => {
    expect(formatDuration(1704067200, 1704067230)).toBe('30s');
  });

  it('formats minutes and seconds', () => {
    expect(formatDuration(1704067200, 1704067400)).toMatch(/\dm/);
  });

  it('formats hours and minutes', () => {
    expect(formatDuration(1704067200, 1704078000)).toMatch(/\dh/);
  });
});

describe('statusColor', () => {
  it('returns running class for RUNNING', () => {
    expect(statusColor('RUNNING')).toContain('running');
  });

  it('returns finished class for FINISHED', () => {
    expect(statusColor('FINISHED')).toContain('finished');
  });

  it('returns failed class for ERROR-FAILED', () => {
    expect(statusColor('ERROR-FAILED')).toContain('failed');
  });

  it('returns default for unknown status', () => {
    expect(statusColor('UNKNOWN')).toContain('default');
  });

  it('is case-insensitive', () => {
    expect(statusColor('running')).toContain('running');
  });
});

describe('statusBadgeClass', () => {
  it('returns proper badge for RUNNING', () => {
    expect(statusBadgeClass('RUNNING')).toContain('badge');
  });

  it('returns proper badge for FINISHED', () => {
    expect(statusBadgeClass('FINISHED')).toContain('success');
  });
});
