/**
 * Vite plugin — Subresource Integrity for production builds.
 *
 * After Vite emits assets, this plugin computes SHA-384 hashes for JS/CSS
 * bundles and adds ``integrity`` + ``crossorigin`` attributes to the
 * ``<script>`` and ``<link>`` tags in ``index.html``.
 *
 * Why SHA-384: Recommended by the W3C SRI spec — the same algorithm Vite's
 * built-in manifest uses and what CDN vendors default to.
 */
import { createHash } from 'crypto';
import type { Plugin } from 'vite';

/**
 * Return a Vite plugin that adds SRI attributes to index.html.
 *
 * @param algorithm Hash algorithm (default "sha384").
 */
export function sriPlugin(algorithm = 'sha384'): Plugin {
  const hashes = new Map<string, string>();

  return {
    name: 'vite-plugin-sri',
    enforce: 'post',
    apply: 'build',

    generateBundle(_options, bundle) {
      for (const [fileName, chunk] of Object.entries(bundle)) {
        if (chunk.type === 'asset' && /\.css$/.test(fileName)) {
          const hash = createHash(algorithm)
            .update(
              typeof chunk.source === 'string'
                ? chunk.source
                : Buffer.from(chunk.source),
            )
            .digest('base64');
          hashes.set(fileName, `${algorithm}-${hash}`);
        } else if (chunk.type === 'chunk' && /\.js$/.test(fileName)) {
          const hash = createHash(algorithm)
            .update(chunk.code)
            .digest('base64');
          hashes.set(fileName, `${algorithm}-${hash}`);
        }
      }
    },

    transformIndexHtml(html) {
      // Add integrity attribute to <script src="..."> tags
      html = html.replace(
        /<script([^>]*)\ssrc="([^"]+)"([^>]*)>/gi,
        (_match, before: string, src: string, after: string) => {
          const cleanSrc = src.replace(/^\//, '');
          const integrity = hashes.get(cleanSrc);
          if (integrity && !before.includes('integrity') && !after.includes('integrity')) {
            return `<script${before} src="${src}" integrity="${integrity}" crossorigin="anonymous"${after}>`;
          }
          return _match;
        },
      );

      // Add integrity attribute to <link rel="stylesheet" href="..."> tags
      html = html.replace(
        /<link([^>]*)\shref="([^"]+\.css)"([^>]*)\/?>/gi,
        (_match, before: string, href: string, after: string) => {
          const cleanHref = href.replace(/^\//, '');
          const integrity = hashes.get(cleanHref);
          if (integrity && !before.includes('integrity') && !after.includes('integrity')) {
            return `<link${before} href="${href}" integrity="${integrity}" crossorigin="anonymous"${after}/>`;
          }
          return _match;
        },
      );

      return html;
    },
  };
}
