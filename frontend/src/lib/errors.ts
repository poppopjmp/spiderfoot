import axios from 'axios';

/**
 * Extract a user-friendly error message from an unknown error.
 * Works with Axios errors (reads `response.data.detail`) and
 * falls back to `Error.message` or a custom default.
 */
export function getErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string' && detail.length > 0) return detail;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
