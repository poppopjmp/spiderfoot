/**
 * Tests for the MarkdownRenderer React component.
 *
 * Validates rendering, className prop, sanitization, and empty content.
 */
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import MarkdownRenderer from '../../components/MarkdownRenderer';

describe('MarkdownRenderer', () => {
  it('renders a heading from markdown', () => {
    const { container } = render(<MarkdownRenderer content="# Hello World" />);
    const h1 = container.querySelector('h1');
    expect(h1).toBeInTheDocument();
    expect(h1?.textContent).toBe('Hello World');
  });

  it('renders a paragraph', () => {
    const { container } = render(<MarkdownRenderer content="Some paragraph text." />);
    const p = container.querySelector('p');
    expect(p).toBeInTheDocument();
    expect(p?.textContent).toBe('Some paragraph text.');
  });

  it('renders bold text via inline formatting', () => {
    const { container } = render(<MarkdownRenderer content="**bold text**" />);
    const strong = container.querySelector('strong');
    expect(strong).toBeInTheDocument();
    expect(strong?.textContent).toBe('bold text');
  });

  it('renders italic text', () => {
    const { container } = render(<MarkdownRenderer content="*italic*" />);
    const em = container.querySelector('em');
    expect(em).toBeInTheDocument();
    expect(em?.textContent).toBe('italic');
  });

  it('renders inline code', () => {
    const { container } = render(<MarkdownRenderer content="`some code`" />);
    const code = container.querySelector('code');
    expect(code).toBeInTheDocument();
    expect(code?.textContent).toBe('some code');
  });

  it('renders an unordered list', () => {
    const { container } = render(
      <MarkdownRenderer content={"- item one\n- item two\n- item three"} />,
    );
    const items = container.querySelectorAll('li');
    expect(items).toHaveLength(3);
    expect(items[0].textContent).toBe('item one');
  });

  it('renders a blockquote', () => {
    const { container } = render(
      <MarkdownRenderer content={"> This is a quote"} />,
    );
    const bq = container.querySelector('blockquote');
    expect(bq).toBeInTheDocument();
  });

  it('renders a horizontal rule', () => {
    const { container } = render(
      <MarkdownRenderer content={"Above\n\n---\n\nBelow"} />,
    );
    const hr = container.querySelector('hr');
    expect(hr).toBeInTheDocument();
  });

  it('renders fenced code blocks', () => {
    const md = "```\nconsole.log('hi');\n```";
    const { container } = render(<MarkdownRenderer content={md} />);
    const pre = container.querySelector('pre');
    expect(pre).toBeInTheDocument();
  });

  it('applies className prop to wrapper div', () => {
    const { container } = render(
      <MarkdownRenderer content="test" className="my-custom-class" />,
    );
    expect(container.firstChild).toHaveClass('my-custom-class');
  });

  it('handles empty content without crashing', () => {
    const { container } = render(<MarkdownRenderer content="" />);
    expect(container.firstChild).toBeInTheDocument();
    // Should render an empty wrapper div
    expect(container.firstChild?.childNodes.length || 0).toBeLessThanOrEqual(1);
  });

  it('sanitizes script tags out of output', () => {
    const { container } = render(
      <MarkdownRenderer content='<script>alert("xss")</script>' />,
    );
    expect(container.querySelector('script')).not.toBeInTheDocument();
    expect(container.innerHTML).not.toContain('<script');
  });

  it('sanitizes event handler attributes', () => {
    const { container } = render(
      <MarkdownRenderer content='<img src="x" onerror="alert(1)" />' />,
    );
    expect(container.innerHTML).not.toContain('onerror');
  });

  it('renders multiple heading levels', () => {
    const md = "# H1\n## H2\n### H3";
    const { container } = render(<MarkdownRenderer content={md} />);
    expect(container.querySelector('h1')).toBeInTheDocument();
    expect(container.querySelector('h2')).toBeInTheDocument();
    expect(container.querySelector('h3')).toBeInTheDocument();
  });

  it('renders mixed content', () => {
    const md = "# Title\n\nSome **bold** and *italic* text.\n\n- list item";
    const { container } = render(<MarkdownRenderer content={md} />);
    expect(container.querySelector('h1')).toBeInTheDocument();
    expect(container.querySelector('strong')).toBeInTheDocument();
    expect(container.querySelector('em')).toBeInTheDocument();
    expect(container.querySelector('li')).toBeInTheDocument();
  });

  it('wraps content in a div element', () => {
    const { container } = render(<MarkdownRenderer content="hello" />);
    expect(container.firstChild?.nodeName).toBe('DIV');
  });
});
