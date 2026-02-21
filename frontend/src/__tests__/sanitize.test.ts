/**
 * Tests for the sanitizeHTML utility.
 *
 * Verifies that DOMPurify-based sanitization strips dangerous content
 * while preserving the allowed tags and attributes used by the app.
 */
import { describe, it, expect } from 'vitest';
import { sanitizeHTML } from '../lib/sanitize';

describe('sanitizeHTML', () => {
  it('strips <script> tags', () => {
    const dirty = '<p>Hello</p><script>alert("xss")</script>';
    expect(sanitizeHTML(dirty)).not.toContain('<script');
    expect(sanitizeHTML(dirty)).toContain('<p>Hello</p>');
  });

  it('strips event handler attributes', () => {
    const dirty = '<img src="x" onerror="alert(1)" />';
    expect(sanitizeHTML(dirty)).not.toContain('onerror');
  });

  it('strips data attributes', () => {
    const dirty = '<div data-payload="evil">ok</div>';
    expect(sanitizeHTML(dirty)).not.toContain('data-payload');
    expect(sanitizeHTML(dirty)).toContain('ok');
  });

  it('preserves allowed tags', () => {
    const clean = '<h1 class="title">Hello</h1><p>World</p>';
    expect(sanitizeHTML(clean)).toBe(clean);
  });

  it('preserves allowed attributes (class, href)', () => {
    const clean = '<a href="https://example.com" class="link">Link</a>';
    expect(sanitizeHTML(clean)).toContain('href="https://example.com"');
    expect(sanitizeHTML(clean)).toContain('class="link"');
  });

  it('strips javascript: URIs', () => {
    const dirty = '<a href="javascript:alert(1)">click</a>';
    const result = sanitizeHTML(dirty);
    expect(result).not.toContain('javascript:');
  });

  it('handles empty string', () => {
    expect(sanitizeHTML('')).toBe('');
  });
});
