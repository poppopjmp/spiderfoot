import axios from 'axios';

/** Maximum length for user-visible error messages. */
const MAX_ERROR_LENGTH = 500;

/**
 * Strip HTML tags and control characters from a string.
 * Defence-in-depth — React escapes JSX, but this protects against
 * `dangerouslySetInnerHTML` or non-React rendering paths.
 */
export function sanitizeErrorText(raw: string): string {
  return raw
    .replace(/<[^>]*>/g, '')          // strip HTML tags
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '') // strip control chars (keep \t \n \r)
    .slice(0, MAX_ERROR_LENGTH)
    .trim();
}

/**
 * Extract a user-friendly error message from an unknown error.
 * Works with Axios errors — checks both FastAPI's `detail` field
 * and the custom error envelope `{ error: { message } }`.
 * Falls back to `Error.message` or a custom default.
 *
 * All messages are sanitised to remove HTML/script content.
 */
export function getErrorMessage(err: unknown, fallback: string): string {
  let msg: string | undefined;

  if (axios.isAxiosError(err)) {
    const data = err.response?.data;
    // FastAPI default: { detail: "..." }
    if (typeof data?.detail === 'string' && data.detail.length > 0) msg = data.detail;
    // Custom error handler envelope: { error: { code, message } }
    else if (typeof data?.error?.message === 'string' && data.error.message.length > 0) msg = data.error.message;
    // Axios message (includes network errors and status descriptions)
    else if (err.message) msg = err.message;
  } else if (err instanceof Error && err.message) {
    msg = err.message;
  }

  return sanitizeErrorText(msg ?? fallback);
}
