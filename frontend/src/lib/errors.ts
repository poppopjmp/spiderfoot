import axios from 'axios';

/**
 * Extract a user-friendly error message from an unknown error.
 * Works with Axios errors — checks both FastAPI's `detail` field
 * and the custom error envelope `{ error: { message } }`.
 * Falls back to `Error.message` or a custom default.
 */
export function getErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data;
    // FastAPI default: { detail: "..." }
    if (typeof data?.detail === 'string' && data.detail.length > 0) return data.detail;
    // Custom error handler envelope: { error: { code, message } }
    if (typeof data?.error?.message === 'string' && data.error.message.length > 0) return data.error.message;
    // Network-level errors (no response)
    if (!err.response && err.message) return err.message;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
