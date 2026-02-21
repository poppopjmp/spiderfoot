/**
 * SpiderFoot API – generated TypeScript client
 *
 * Usage:
 *   import { listScans, getScan, createScan } from '@/api';
 *
 * The client is pre-configured with JWT/API-key interceptors
 * (same behaviour as the legacy `src/lib/api.ts` Axios instance).
 *
 * Regenerate after backend changes:
 *   npm run generate:api
 */

// Initialise interceptors (side-effect import — must come first)
import './client';

// Re-export the configured client for advanced use (e.g. custom calls)
export { client } from './client';

// Re-export every generated SDK function
export * from './generated/sdk.gen';

// Re-export every generated type
export type * from './generated/types.gen';
