/**
 * Vite Plugin — Subresource Integrity (SRI)
 *
 * Adds `integrity` attributes (SHA-384 hashes) to all <script> and <link rel="stylesheet">
 * tags in the built HTML. This prevents CDN/MITM tampering with served assets.
 *
 * Usage in vite.config.ts:
 *   import { sriPlugin } from './src/lib/sriPlugin';
 *   export default defineConfig({ plugins: [sriPlugin()] });
 *
 * Only runs during `vite build` (no-op in dev server mode).
 */

import { createHash } from 'crypto';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import type { Plugin } from 'vite';

export interface SriPluginOptions {
  /** Hash algorithm (default: sha384) */
  algorithm?: 'sha256' | 'sha384' | 'sha512';
  /** Cross-origin attribute value (default: anonymous) */
  crossorigin?: string;
}

/**
 * Compute SRI hash for a buffer.
 */
function computeSriHash(content: Buffer | string, algorithm: string): string {
  const hash = createHash(algorithm).update(content).digest('base64');
  return `${algorithm}-${hash}`;
}

export function sriPlugin(options: SriPluginOptions = {}): Plugin {
  const algorithm = options.algorithm ?? 'sha384';
  const crossorigin = options.crossorigin ?? 'anonymous';
  let outDir = '';

  return {
    name: 'vite-plugin-sri',
    apply: 'build',
    enforce: 'post',

    configResolved(config) {
      outDir = config.build.outDir;
    },

    transformIndexHtml: {
      order: 'post',
      handler(html, ctx) {
        // Resolve output directory from the HTML file location
        const htmlDir = ctx.filename ? dirname(ctx.filename) : outDir;

        // Process <script src="..."> tags
        html = html.replace(
          /<script([^>]*)\ssrc="([^"]+)"([^>]*)><\/script>/g,
          (match, before, src, after) => {
            if (src.startsWith('http://') || src.startsWith('https://') || src.startsWith('//')) {
              return match; // Skip external URLs
            }
            try {
              const filePath = resolve(htmlDir, src.replace(/^\//, ''));
              const content = readFileSync(filePath);
              const hash = computeSriHash(content, algorithm);
              // Remove any existing integrity/crossorigin to avoid duplication
              const cleanBefore = before.replace(/\s*integrity="[^"]*"/, '').replace(/\s*crossorigin="[^"]*"/, '');
              const cleanAfter = after.replace(/\s*integrity="[^"]*"/, '').replace(/\s*crossorigin="[^"]*"/, '');
              return `<script${cleanBefore} src="${src}" integrity="${hash}" crossorigin="${crossorigin}"${cleanAfter}></script>`;
            } catch {
              // File not found — skip SRI for this tag
              return match;
            }
          },
        );

        // Process <link rel="stylesheet" href="..."> tags
        html = html.replace(
          /<link([^>]*)\shref="([^"]+)"([^>]*)\/?>/g,
          (match, before, href, after) => {
            const full = before + after;
            if (!full.includes('stylesheet') && !before.includes('rel="stylesheet"')) {
              return match; // Not a stylesheet link
            }
            if (href.startsWith('http://') || href.startsWith('https://') || href.startsWith('//')) {
              return match; // Skip external URLs
            }
            try {
              const filePath = resolve(htmlDir, href.replace(/^\//, ''));
              const content = readFileSync(filePath);
              const hash = computeSriHash(content, algorithm);
              const cleanBefore = before.replace(/\s*integrity="[^"]*"/, '').replace(/\s*crossorigin="[^"]*"/, '');
              const cleanAfter = after.replace(/\s*integrity="[^"]*"/, '').replace(/\s*crossorigin="[^"]*"/, '');
              return `<link${cleanBefore} href="${href}" integrity="${hash}" crossorigin="${crossorigin}"${cleanAfter}/>`;
            } catch {
              return match;
            }
          },
        );

        return html;
      },
    },
  };
}
