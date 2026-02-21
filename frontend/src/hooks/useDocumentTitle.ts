import { useEffect } from 'react';

/**
 * Set `document.title` while a component is mounted.
 * Restores the original title on unmount.
 */
export function useDocumentTitle(title: string) {
  useEffect(() => {
    const prev = document.title;
    document.title = title ? `${title} — SpiderFoot` : 'SpiderFoot';
    return () => { document.title = prev; };
  }, [title]);
}
