/**
 * Tests for the MarkdownRenderer shared component.
 *
 * Verifies that renderMarkdownToHTML and inlineFormat produce correct
 * HTML output for various Markdown constructs.
 */
import { describe, it, expect } from 'vitest';
import { renderMarkdownToHTML, inlineFormat } from '../components/MarkdownRenderer';

describe('inlineFormat', () => {
  it('converts bold text', () => {
    expect(inlineFormat('**bold**')).toContain('<strong');
    expect(inlineFormat('**bold**')).toContain('bold');
  });

  it('converts italic text', () => {
    expect(inlineFormat('*italic*')).toContain('<em>italic</em>');
  });

  it('converts inline code', () => {
    expect(inlineFormat('`code`')).toContain('<code');
    expect(inlineFormat('`code`')).toContain('code');
  });

  it('preserves plain text', () => {
    expect(inlineFormat('hello world')).toBe('hello world');
  });
});

describe('renderMarkdownToHTML', () => {
  it('renders headings', () => {
    const html = renderMarkdownToHTML('# Title\n## Subtitle');
    expect(html).toContain('<h1');
    expect(html).toContain('Title');
    expect(html).toContain('<h2');
    expect(html).toContain('Subtitle');
  });

  it('renders paragraphs', () => {
    const html = renderMarkdownToHTML('Hello world');
    expect(html).toContain('<p');
    expect(html).toContain('Hello world');
  });

  it('renders code blocks', () => {
    const html = renderMarkdownToHTML('```\nconst x = 1;\n```');
    expect(html).toContain('<pre');
    expect(html).toContain('<code');
    expect(html).toContain('const x = 1;');
  });

  it('escapes HTML inside code blocks', () => {
    const html = renderMarkdownToHTML('```\n<script>alert(1)</script>\n```');
    expect(html).toContain('&lt;script&gt;');
    expect(html).not.toContain('<script>');
  });

  it('renders unordered lists', () => {
    const html = renderMarkdownToHTML('- Item 1\n- Item 2');
    expect(html).toContain('<li');
    expect(html).toContain('Item 1');
    expect(html).toContain('Item 2');
  });

  it('renders ordered lists', () => {
    const html = renderMarkdownToHTML('1. First\n2. Second');
    expect(html).toContain('<ol');
    expect(html).toContain('First');
  });

  it('renders blockquotes', () => {
    const html = renderMarkdownToHTML('> Quote text');
    expect(html).toContain('<blockquote');
    expect(html).toContain('Quote text');
  });

  it('renders horizontal rules', () => {
    const html = renderMarkdownToHTML('---');
    expect(html).toContain('<hr');
  });

  it('renders tables', () => {
    const md = '| Name | Value |\n| --- | --- |\n| A | 1 |';
    const html = renderMarkdownToHTML(md);
    expect(html).toContain('<table');
    expect(html).toContain('<th');
    expect(html).toContain('Name');
    expect(html).toContain('<td');
    expect(html).toContain('A');
  });

  it('handles empty input gracefully', () => {
    // Empty string produces a single spacer div (empty line handler)
    const html = renderMarkdownToHTML('');
    expect(html).toBeDefined();
    expect(html).not.toContain('<script');
  });
});
