/**
 * useScanProgress — SSE hook for real-time scan progress.
 *
 * Connects to /api/scans/{id}/progress/stream and yields
 * per-module progress snapshots including overall percentage
 * and module-level breakdowns.
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

export function useScanProgress(
  scanId: string | undefined,
  opts: UseScanProgressOpts = {},
) {
  const { enabled = true, interval = 2, onComplete } = opts;
  const [progress, setProgress] = useState<ScanProgressSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!scanId || !enabled) {
      disconnect();
      return;
    }

    // Build SSE URL with auth
    const headers = getAuthHeaders();
    const params = new URLSearchParams({ interval: String(interval) });

    // EventSource doesn't support custom headers; pass token as query param
    const token = headers['Authorization']?.replace('Bearer ', '');
    if (token) params.set('token', token);
    const apiKey = headers['X-API-Key'];
    if (apiKey) params.set('api_key', apiKey);

    const url = `/api/scans/${scanId}/progress/stream?${params}`;

    try {
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.onopen = () => {
        setConnected(true);
        setError(null);
      };

      es.addEventListener('progress', (event) => {
        try {
          const data = JSON.parse(event.data);
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
      });

      es.addEventListener('complete', () => {
        setProgress((prev) => prev ? { ...prev, status: 'FINISHED', overall_percent: 100 } : null);
        onCompleteRef.current?.();
        disconnect();
      });

      es.addEventListener('heartbeat', () => {
        // Keep connection alive — no action needed
      });

      es.onerror = () => {
        // EventSource auto-reconnects; track transient errors
        setError('Connection lost — reconnecting...');
        setConnected(false);
      };
    } catch {
      setError('Failed to connect to progress stream');
    }

    return disconnect;
  }, [scanId, enabled, interval, disconnect]);

  return { progress, connected, error, disconnect };
}
