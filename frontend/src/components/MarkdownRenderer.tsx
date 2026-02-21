/**
 * Shared Markdown renderer for SpiderFoot.
 *
 * Converts a Markdown string to sanitized HTML and renders it inside a
 * `<div>`.  All output is passed through DOMPurify via `sanitizeHTML`
 * so it is safe for `dangerouslySetInnerHTML`.
 *
 * Usage:
 *   <MarkdownRenderer content={md} className="prose" />
 */

import React from 'react';
import { sanitizeHTML } from '../lib/sanitize';

// ── Inline formatting (shared) ────────────────────────────────

/** Convert inline Markdown (bold, italic, code) to HTML. */
export function inlineFormat(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-foreground font-semibold">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(
      /`(.+?)`/g,
      '<code class="bg-dark-700 px-1 py-0.5 rounded text-spider-400 text-xs font-mono">$1</code>',
    );
}

// ── Block-level renderer ──────────────────────────────────────

/** Render a Markdown string to an HTML string (unsanitized). */
export function renderMarkdownToHTML(md: string): string {
  const lines = md.split('\n');
  const html: string[] = [];
  let inTable = false;
  let inBlockquote = false;
  let inList = false;
  let inCodeBlock = false;

  lines.forEach((line) => {
    // Fenced code blocks
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        html.push('</code></pre>');
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
        html.push(
          '<pre class="bg-dark-900 border border-dark-700/50 rounded-lg p-4 my-3 overflow-x-auto"><code class="text-xs font-mono text-dark-300">',
        );
      }
      return;
    }
    if (inCodeBlock) {
      html.push(line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'));
      return;
    }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) {
      if (inList) { html.push('</ul>'); inList = false; }
      if (inBlockquote) { html.push('</blockquote>'); inBlockquote = false; }
      html.push('<hr class="border-dark-700/50 my-6" />');
      return;
    }

    // Headings
    const hMatch = line.match(/^(#{1,6})\s+(.*)/);
    if (hMatch) {
      if (inList) { html.push('</ul>'); inList = false; }
      if (inBlockquote) { html.push('</blockquote>'); inBlockquote = false; }
      const level = hMatch[1].length;
      const sizes: Record<number, string> = {
        1: 'text-2xl font-bold text-foreground mt-6 mb-3 pb-2 border-b border-dark-700/40',
        2: 'text-xl font-bold text-foreground mt-5 mb-2',
        3: 'text-lg font-semibold text-dark-100 mt-4 mb-2',
        4: 'text-base font-semibold text-dark-200 mt-3 mb-1',
        5: 'text-sm font-semibold text-dark-300 mt-2 mb-1',
        6: 'text-xs font-semibold text-dark-400 mt-2 mb-1',
      };
      html.push(`<h${level} class="${sizes[level]}">${inlineFormat(hMatch[2])}</h${level}>`);
      return;
    }

    // Tables
    if (line.trim().startsWith('|')) {
      if (!inTable) {
        html.push(
          '<div class="overflow-x-auto my-3"><table class="w-full text-sm border border-dark-700/40 rounded-lg overflow-hidden"><tbody>',
        );
        inTable = true;
      }
      if (/^\|[-:|\s]+\|$/.test(line.trim())) return;
      const cells = line.split('|').filter((c) => c.trim() !== '');
      const isHeader = !html.some((l) => l.includes('<tr'));
      const rowClass = isHeader ? 'bg-dark-800/60' : 'hover:bg-dark-800/30 transition-colors';
      html.push(`<tr class="border-b border-dark-700/30 ${rowClass}">`);
      cells.forEach((cell) => {
        const tag = isHeader ? 'th' : 'td';
        const cls = isHeader
          ? 'px-4 py-2.5 text-left text-xs font-semibold text-dark-300 uppercase tracking-wider'
          : 'px-4 py-2 text-dark-300';
        const align = cell.trim().match(/^\d/) ? ' text-right' : '';
        html.push(`<${tag} class="${cls}${align}">${inlineFormat(cell.trim())}</${tag}>`);
      });
      html.push('</tr>');
      return;
    } else if (inTable) {
      html.push('</tbody></table></div>');
      inTable = false;
    }

    // Blockquotes
    if (line.trim().startsWith('>')) {
      if (!inBlockquote) {
        html.push(
          '<blockquote class="border-l-3 border-spider-500 pl-4 py-2 my-3 bg-dark-800/30 rounded-r-lg">',
        );
        inBlockquote = true;
      }
      html.push(
        `<p class="text-sm text-dark-300">${inlineFormat(line.replace(/^>\s*/, ''))}</p>`,
      );
      return;
    } else if (inBlockquote) {
      html.push('</blockquote>');
      inBlockquote = false;
    }

    // Lists
    const liMatch = line.match(/^(\s*)(\d+\.|[-*])\s+(.*)/);
    if (liMatch) {
      const isOrdered = /\d+\./.test(liMatch[2]);
      if (!inList) {
        const tag = isOrdered ? 'ol' : 'ul';
        const listClass = isOrdered ? 'list-decimal' : 'list-disc';
        html.push(
          `<${tag} class="${listClass} list-inside space-y-1.5 my-3 text-sm text-dark-300 pl-2">`,
        );
        inList = true;
      }
      html.push(`<li class="leading-relaxed">${inlineFormat(liMatch[3])}</li>`);
      return;
    } else if (inList && line.trim() === '') {
      html.push('</ul>');
      inList = false;
    }

    // Empty line
    if (line.trim() === '') {
      html.push('<div class="h-3"></div>');
      return;
    }

    // Paragraph
    html.push(
      `<p class="text-sm text-dark-300 leading-relaxed my-1">${inlineFormat(line)}</p>`,
    );
  });

  if (inCodeBlock) html.push('</code></pre>');
  if (inTable) html.push('</tbody></table></div>');
  if (inList) html.push('</ul>');
  if (inBlockquote) html.push('</blockquote>');

  return html.join('\n');
}

// ── React component ───────────────────────────────────────────

interface MarkdownRendererProps {
  /** Raw Markdown string to render. */
  content: string;
  /** Extra CSS classes for the wrapper `<div>`. */
  className?: string;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className }) => {
  const html = React.useMemo(
    () => sanitizeHTML(renderMarkdownToHTML(content)),
    [content],
  );

  return (
    <div
      className={className}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};

export default MarkdownRenderer;
