/**
 * HTML sanitization utilities using DOMPurify.
 *
 * Every string that flows into dangerouslySetInnerHTML MUST pass through
 * `sanitizeHTML` first to strip script injections, event‑handler attributes,
 * and other XSS vectors.
 */
import DOMPurify from 'dompurify';

/**
 * Allowed tags – covers everything the hand‑rolled markdown renderers emit.
 * Anything not on this list is stripped.
 */
const ALLOWED_TAGS = [
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'p', 'br', 'hr',
  'strong', 'b', 'em', 'i', 'u', 'code', 'pre',
  'ul', 'ol', 'li',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
  'blockquote', 'div', 'span',
  'a', 'img',
];

/**
 * Allowed attributes – limited to styling classes and safe link attrs.
 */
const ALLOWED_ATTR = ['class', 'href', 'target', 'rel', 'src', 'alt', 'title'];

/**
 * Sanitize an HTML string for safe injection via dangerouslySetInnerHTML.
 */
export function sanitizeHTML(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOW_DATA_ATTR: false,
  });
}
