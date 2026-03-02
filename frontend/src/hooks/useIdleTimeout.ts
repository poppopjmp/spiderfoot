/**
 * Idle-timeout hook for session security.
 *
 * Monitors user interaction (mouse, keyboard, touch, scroll) and triggers
 * a callback after a configurable period of inactivity.  A warning callback
 * fires beforehand so the UI can show a "Session expiring" banner.
 *
 * Usage:
 *   useIdleTimeout({
 *     timeout: 15 * 60_000,       // 15 min
 *     warningBefore: 60_000,      // warn 1 min before
 *     onIdle: () => authStore.logout(),
 *     onWarning: (remaining) => setShowBanner(true),
 *     onActive: () => setShowBanner(false),
 *   });
 */
import { useCallback, useEffect, useRef } from 'react';

/** Configuration options for {@link useIdleTimeout}. */
export interface IdleTimeoutOptions {
  /** Inactivity duration in milliseconds before `onIdle` fires.  Default 15 min. */
  timeout?: number;
  /** Fire `onWarning` this many ms *before* `onIdle`.  Default 60 000 (1 min). */
  warningBefore?: number;
  /** Called when the user has been idle for `timeout` ms. */
  onIdle: () => void;
  /** Called when warning threshold is reached.  Receives remaining ms. */
  onWarning?: (remainingMs: number) => void;
  /** Called when user activity resumes after a warning was issued. */
  onActive?: () => void;
  /** Disable the hook entirely (e.g. when auth is not required). */
  disabled?: boolean;
}

const ACTIVITY_EVENTS: (keyof WindowEventMap)[] = [
  'mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll',
];

const DEFAULT_TIMEOUT = 15 * 60_000;   // 15 min
const DEFAULT_WARNING = 60_000;        // 1 min

/**
 * Track user activity and fire callbacks on inactivity.
 *
 * Internally uses two timeouts: one for the warning and one for the
 * final idle trigger.  Activity events are throttled to avoid excessive
 * timer resets.
 */
export function useIdleTimeout(options: IdleTimeoutOptions): void {
  const {
    timeout = DEFAULT_TIMEOUT,
    warningBefore = DEFAULT_WARNING,
    onIdle,
    onWarning,
    onActive,
    disabled = false,
  } = options;

  const warningRef = useRef<ReturnType<typeof setTimeout>>();
  const idleRef = useRef<ReturnType<typeof setTimeout>>();
  const warnedRef = useRef(false);
  const lastActivityRef = useRef(Date.now());

  // Stable callback refs so we never need to re-register event listeners
  const onIdleRef = useRef(onIdle);
  const onWarningRef = useRef(onWarning);
  const onActiveRef = useRef(onActive);
  onIdleRef.current = onIdle;
  onWarningRef.current = onWarning;
  onActiveRef.current = onActive;

  const resetTimers = useCallback(() => {
    clearTimeout(warningRef.current);
    clearTimeout(idleRef.current);
    lastActivityRef.current = Date.now();

    if (warnedRef.current) {
      warnedRef.current = false;
      onActiveRef.current?.();
    }

    const warningDelay = Math.max(timeout - warningBefore, 0);

    warningRef.current = setTimeout(() => {
      warnedRef.current = true;
      onWarningRef.current?.(warningBefore);
    }, warningDelay);

    idleRef.current = setTimeout(() => {
      onIdleRef.current();
    }, timeout);
  }, [timeout, warningBefore]);

  useEffect(() => {
    if (disabled) return;

    // Throttle activity events (max once per 5 s)
    let throttleTimer: ReturnType<typeof setTimeout> | undefined;
    const THROTTLE_MS = 5_000;

    const handleActivity = () => {
      if (throttleTimer) return;
      throttleTimer = setTimeout(() => { throttleTimer = undefined; }, THROTTLE_MS);
      resetTimers();
    };

    resetTimers();
    for (const evt of ACTIVITY_EVENTS) {
      window.addEventListener(evt, handleActivity, { passive: true });
    }

    return () => {
      for (const evt of ACTIVITY_EVENTS) {
        window.removeEventListener(evt, handleActivity);
      }
      clearTimeout(warningRef.current);
      clearTimeout(idleRef.current);
      clearTimeout(throttleTimer);
    };
  }, [disabled, resetTimers]);
}
