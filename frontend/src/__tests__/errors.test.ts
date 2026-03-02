/**
 * Tests for the error message extraction and sanitisation utility.
 *
 * Validates that `getErrorMessage` extracts user-friendly messages from
 * Axios errors and that `sanitizeErrorText` strips HTML/control chars.
 */
import { describe, it, expect } from 'vitest';
import { sanitizeErrorText, getErrorMessage } from '../lib/errors';

// ── sanitizeErrorText ──────────────────────────────────────────────

describe('sanitizeErrorText', () => {
  it('returns plain text unchanged', () => {
    expect(sanitizeErrorText('Something went wrong')).toBe('Something went wrong');
  });

  it('strips HTML tags', () => {
    expect(sanitizeErrorText('<b>bold</b> text')).toBe('bold text');
  });

  it('strips script tags (text content remains harmless)', () => {
    const input = 'Error<script>alert("xss")</script> occurred';
    const result = sanitizeErrorText(input);
    expect(result).not.toContain('<script');
    expect(result).not.toContain('</script');
    expect(result).toContain('Error');
    expect(result).toContain('occurred');
  });

  it('strips control characters but keeps tab/newline/CR', () => {
    const input = 'Line1\nLine2\t\r\x00\x07end';
    const result = sanitizeErrorText(input);
    expect(result).toContain('\n');
    expect(result).toContain('\t');
    expect(result).not.toContain('\x00');
    expect(result).not.toContain('\x07');
  });

  it('truncates messages longer than 500 characters', () => {
    const longMsg = 'x'.repeat(1000);
    expect(sanitizeErrorText(longMsg).length).toBeLessThanOrEqual(500);
  });

  it('trims whitespace', () => {
    expect(sanitizeErrorText('  hello  ')).toBe('hello');
  });
});

// ── getErrorMessage ────────────────────────────────────────────────

describe('getErrorMessage', () => {
  it('returns fallback for null', () => {
    expect(getErrorMessage(null, 'fallback')).toBe('fallback');
  });

  it('returns fallback for undefined', () => {
    expect(getErrorMessage(undefined, 'fallback')).toBe('fallback');
  });

  it('extracts message from plain Error', () => {
    expect(getErrorMessage(new Error('oops'), 'fb')).toBe('oops');
  });

  it('sanitizes HTML in Error.message', () => {
    const err = new Error('<img onerror=alert(1)>bad');
    const msg = getErrorMessage(err, 'fb');
    expect(msg).not.toContain('<img');
    expect(msg).toContain('bad');
  });

  it('returns fallback for non-error objects', () => {
    expect(getErrorMessage({ random: true }, 'fallback')).toBe('fallback');
  });

  it('sanitizes the fallback too', () => {
    const result = getErrorMessage(null, '<b>fallback</b>');
    expect(result).toBe('fallback');
  });
});
