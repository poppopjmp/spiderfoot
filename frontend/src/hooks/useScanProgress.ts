/**
 * useScanProgress — SSE hook for real-time scan progress.
 *
 * Connects to /api/scans/{id}/progress/stream and yields
 * per-module progress snapshots including overall percentage
 * and module-level breakdowns.
 *
 * Uses fetch() + ReadableStream instead of native EventSource so
 * auth credentials are sent via headers (not leaked in the URL).
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { getAuthHeaders } from '../lib/api';

export interface ModuleProgress {
  name: string;
  status: string;
  events_produced: number;
  started_at?: number;
  finished_at?: number;
}

export interface ScanProgressSnapshot {
  scan_id: string;
  status: string;
  overall_percent: number;
  modules_total: number;
  modules_finished: number;
  modules_running: number;
  modules: ModuleProgress[];
  timestamp: number;
}

interface UseScanProgressOpts {
  /** Only connect when scan is running */
  enabled?: boolean;
  /** SSE polling interval in seconds (default 2) */
  interval?: number;
  /** Called when scan completes */
  onComplete?: () => void;
}

/* ------------------------------------------------------------------ */
/* SSE line parser — processes `event:` / `data:` / blank-line frames */
/* ------------------------------------------------------------------ */

interface SSEFrame {
  event: string;
  data: string;
}

function parseSSEChunk(
  buffer: string,
  onFrame: (frame: SSEFrame) => void,
): string {
  const lines = buffer.split('\n');
  let currentEvent = 'message';
  let currentData = '';
  let incomplete = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Last element may be an incomplete line (no trailing \n)
    if (i === lines.length - 1 && !buffer.endsWith('\n')) {
      incomplete = line;
      break;
    }

    if (line === '' || line === '\r') {
      // Blank line = dispatch frame
      if (currentData) {
        onFrame({ event: currentEvent, data: currentData.trimEnd() });
      }
      currentEvent = 'message';
      currentData = '';
    } else if (line.startsWith('event:')) {
      currentEvent = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      currentData += (currentData ? '\n' : '') + line.slice(5).trimStart();
    }
    // Ignore `id:`, `retry:`, comments (`:`)
  }
  return incomplete;
}

export function useScanProgress(
  scanId: string | undefined,
  opts: UseScanProgressOpts = {},
) {
  const { enabled = true, interval = 2, onComplete } = opts;
  const [progress, setProgress] = useState<ScanProgressSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const disconnect = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!scanId || !enabled) {
      disconnect();
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;

    const url = `/api/scans/${encodeURIComponent(scanId)}/progress/stream?interval=${interval}`;

    const handleFrame = (frame: SSEFrame) => {
      if (frame.event === 'progress') {
        try {
          const data = JSON.parse(frame.data);
          const snapshot: ScanProgressSnapshot = {
            scan_id: data.scan_id ?? scanId,
            status: data.status ?? 'RUNNING',
            overall_percent: data.overall_percent ?? data.percent ?? 0,
            modules_total: data.modules_total ?? 0,
            modules_finished: data.modules_finished ?? 0,
            modules_running: data.modules_running ?? 0,
            modules: (data.modules ?? []).map((m: Record<string, unknown>) => ({
              name: m.name ?? m.module ?? '',
              status: m.status ?? 'unknown',
              events_produced: m.events_produced ?? m.event_count ?? 0,
              started_at: m.started_at,
              finished_at: m.finished_at,
            })),
            timestamp: data.timestamp ?? Date.now() / 1000,
          };
          setProgress(snapshot);
        } catch {
          // Ignore malformed progress events
        }
      } else if (frame.event === 'complete') {
        setProgress((prev) =>
          prev ? { ...prev, status: 'FINISHED', overall_percent: 100 } : null,
        );
        onCompleteRef.current?.();
        disconnect();
      }
      // heartbeat events — no action needed
    };

    (async () => {
      try {
        const res = await fetch(url, {
          headers: {
            Accept: 'text/event-stream',
            ...getAuthHeaders(),
          },
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          setError(`Stream error: ${res.status}`);
          setConnected(false);
          return;
        }

        setConnected(true);
        setError(null);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = '';

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          sseBuffer = parseSSEChunk(
            sseBuffer + decoder.decode(value, { stream: true }),
            handleFrame,
          );
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError('Connection lost');
        setConnected(false);
      }
    })();

    return disconnect;
  }, [scanId, enabled, interval, disconnect]);

  return { progress, connected, error, disconnect };
}
