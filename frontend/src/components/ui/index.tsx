/**
 * Shared UI primitives — used across all pages.
 * Follows emotional design principles:
 * - Micro-interactions that delight (hover lifts, press effects)
 * - Progressive disclosure (expandable sections, tooltips)
 * - Helpful empty states with actionable guidance
 * - Loading skeletons instead of spinners where possible
 * - Contextual feedback (toast, inline success)
 */

import { clsx } from 'clsx';
import React, { useState, useRef, useEffect, useCallback, useId } from 'react';
import { createPortal } from 'react-dom';
import {
  ChevronDown, ChevronRight, Copy, Check, Search,
  AlertCircle, X, Info, CheckCircle2,
} from 'lucide-react';

/* ── Page Header ──────────────────────────────────────────── */
export function PageHeader({
  title, subtitle, children, className,
}: {
  title: string; subtitle?: string; children?: React.ReactNode; className?: string;
}) {
  return (
    <div className={clsx('flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8 animate-fade-in', className)}>
      <div>
        <h1 className="text-2xl font-bold text-foreground tracking-tight">{title}</h1>
        {subtitle && <p className="text-dark-400 mt-1 text-sm">{subtitle}</p>}
      </div>
      {children && <div className="flex items-center gap-3 flex-shrink-0">{children}</div>}
    </div>
  );
}

/* ── Stat Card ────────────────────────────────────────────── */
export function StatCard({
  label, value, icon: Icon, color = 'text-spider-400', loading, delay = 0,
  trend, trendLabel,
}: {
  label: string;
  value: number | string;
  icon: React.ComponentType<{ className?: string }>;
  color?: string;
  loading?: boolean;
  delay?: number;
  trend?: 'up' | 'down' | 'flat';
  trendLabel?: string;
}) {
  return (
    <div
      className="card-hover flex items-center gap-4"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className={clsx('p-3 rounded-xl bg-dark-700/50', color)}>
        <Icon className="h-6 w-6" />
      </div>
      <div className="flex-1 min-w-0">
        {loading ? (
          <div className="skeleton h-7 w-16 mb-1" />
        ) : (
          <p className="text-2xl font-bold text-foreground animate-count-up">{value}</p>
        )}
        <p className="text-xs text-dark-400 truncate">{label}</p>
      </div>
      {trend && trendLabel && (
        <span className={clsx('text-xs font-medium', {
          'text-green-400': trend === 'up',
          'text-red-400': trend === 'down',
          'text-dark-500': trend === 'flat',
        })}>
          {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '–'} {trendLabel}
        </span>
      )}
    </div>
  );
}

/* ── Debounce Hook ────────────────────────────────────────── */
/**
 * Returns a debounced version of the value that only updates
 * after the specified delay (default 250ms). Useful for search
 * inputs to avoid firing on every keystroke.
 */
export function useDebounce<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/* ── Search Input ─────────────────────────────────────────── */
export function SearchInput({
  value, onChange, placeholder = 'Search...', className, debounceMs,
}: {
  value: string; onChange: (v: string) => void; placeholder?: string; className?: string;
  /** When set, onChange fires only after debounceMs of inactivity. */
  debounceMs?: number;
}) {
  const [local, setLocal] = useState(value);
  const debounced = useDebounce(local, debounceMs ?? 0);
  const isDebounced = (debounceMs ?? 0) > 0;

  // Sync debounced value back to parent
  useEffect(() => {
    if (isDebounced) onChange(debounced);
  }, [debounced, isDebounced, onChange]);

  // Sync external value changes to local state
  useEffect(() => {
    if (!isDebounced) setLocal(value);
  }, [value, isDebounced]);

  const handleChange = (v: string) => {
    setLocal(v);
    if (!isDebounced) onChange(v);
  };

  return (
    <div className={clsx('relative', className)}>
      <Search className="h-4 w-4 text-dark-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
      <input
        type="text"
        className="input-search"
        placeholder={placeholder}
        value={local}
        onChange={(e) => handleChange(e.target.value)}
      />
      {local && (
        <button
          onClick={() => handleChange('')}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-500 hover:text-dark-300 transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

/* ── Copy Button ──────────────────────────────────────────── */
export function CopyButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {
      /* Clipboard API may be blocked (non-HTTPS, iframes, denied permission) */
    });
  }, [text]);

  return (
    <button
      onClick={copy}
      className={clsx('btn-icon transition-all', className)}
      title={copied ? 'Copied!' : 'Copy'}
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-green-400" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}

/* ── Tooltip ───────────────────────────────────────────────── */
/**
 * Accessible tooltip that appears on hover/focus.
 * Positions itself above, below, left, or right of the trigger.
 * Uses CSS class `.tooltip` and renders via portal to avoid clipping.
 */
export function Tooltip({
  children, content, side = 'top', className, delayMs = 200,
}: {
  children: React.ReactElement;
  content: React.ReactNode;
  side?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
  delayMs?: number;
}) {
  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState({ x: 0, y: 0 });
  const triggerRef = useRef<HTMLElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const tooltipId = useId();

  const show = useCallback(() => {
    timerRef.current = setTimeout(() => setVisible(true), delayMs);
  }, [delayMs]);

  const hide = useCallback(() => {
    clearTimeout(timerRef.current);
    setVisible(false);
  }, []);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  // Position calculation after tooltip becomes visible
  useEffect(() => {
    if (!visible || !triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const gap = 8;

    let x = rect.left + rect.width / 2;
    let y: number;

    if (side === 'top') {
      y = rect.top - gap;
    } else if (side === 'bottom') {
      y = rect.bottom + gap;
    } else if (side === 'left') {
      x = rect.left - gap;
      y = rect.top + rect.height / 2;
    } else {
      x = rect.right + gap;
      y = rect.top + rect.height / 2;
    }
    setCoords({ x, y });
  }, [visible, side]);

  // Clamp tooltip into viewport
  useEffect(() => {
    if (!visible || !tooltipRef.current) return;
    const el = tooltipRef.current;
    const r = el.getBoundingClientRect();
    const overRight = r.right - window.innerWidth + 8;
    const overLeft = 8 - r.left;
    if (overRight > 0) el.style.transform = `translateX(-${overRight}px)`;
    else if (overLeft > 0) el.style.transform = `translateX(${overLeft}px)`;
  }, [visible, coords]);

  const sideStyle: React.CSSProperties =
    side === 'top' ? { left: coords.x, top: coords.y, transform: 'translate(-50%, -100%)' }
    : side === 'bottom' ? { left: coords.x, top: coords.y, transform: 'translate(-50%, 0)' }
    : side === 'left' ? { left: coords.x, top: coords.y, transform: 'translate(-100%, -50%)' }
    : { left: coords.x, top: coords.y, transform: 'translate(0, -50%)' };

  return (
    <>
      {React.cloneElement(children, {
        ref: triggerRef,
        onMouseEnter: show,
        onMouseLeave: hide,
        onFocus: show,
        onBlur: hide,
        'aria-describedby': visible ? tooltipId : undefined,
      })}
      {visible && createPortal(
        <div
          ref={tooltipRef}
          id={tooltipId}
          role="tooltip"
          className={clsx('tooltip', className)}
          style={{ ...sideStyle, position: 'fixed' }}
        >
          {content}
        </div>,
        document.body,
      )}
    </>
  );
}

/* ── Expandable Section ───────────────────────────────────── */
export function Expandable({
  title, children, defaultOpen = false, badge, className,
}: {
  title: string; children: React.ReactNode; defaultOpen?: boolean; badge?: React.ReactNode; className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={clsx('border border-dark-700/50 rounded-lg overflow-hidden', className)}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 text-sm font-medium text-dark-200 hover:bg-dark-700/30 transition-colors"
      >
        {open ? <ChevronDown className="h-4 w-4 text-dark-500" /> : <ChevronRight className="h-4 w-4 text-dark-500" />}
        <span className="flex-1 text-left">{title}</span>
        {badge}
      </button>
      {open && (
        <div className="px-4 pb-4 animate-fade-in">
          {children}
        </div>
      )}
    </div>
  );
}

/* ── Empty State ──────────────────────────────────────────── */
export function EmptyState({
  icon: Icon, title, description, action, className,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx('empty-state animate-fade-in-up', className)}>
      <Icon className="empty-state-icon" />
      <h3 className="empty-state-title">{title}</h3>
      {description && <p className="empty-state-text">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

/* ── Skeleton / Loading ───────────────────────────────────── */
export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('skeleton', className)} />;
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4" style={{ animationDelay: `${i * 80}ms` }}>
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className={clsx('h-5 rounded', j === 0 ? 'w-1/3' : 'w-1/6')} />
          ))}
        </div>
      ))}
    </div>
  );
}

/* ── Toast / Notification ─────────────────────────────────── */
export type ToastType = 'success' | 'error' | 'info' | 'warning';

const toastConfig: Record<ToastType, { icon: typeof CheckCircle2; color: string; bg: string }> = {
  success: { icon: CheckCircle2, color: 'text-green-400', bg: 'bg-green-900/20 border-green-800/30' },
  error: { icon: AlertCircle, color: 'text-red-400', bg: 'bg-red-900/20 border-red-800/30' },
  info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-900/20 border-blue-800/30' },
  warning: { icon: AlertCircle, color: 'text-yellow-400', bg: 'bg-yellow-900/20 border-yellow-800/30' },
};

export function Toast({
  type = 'info', message, onClose,
}: {
  type?: ToastType; message: string; onClose: () => void;
}) {
  const cfg = toastConfig[type];
  const Icon = cfg.icon;

  useEffect(() => {
    const t = setTimeout(onClose, 5000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div className={clsx(
      'animate-toast fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl border shadow-2xl max-w-sm',
      cfg.bg,
    )}>
      <Icon className={clsx('h-5 w-5 flex-shrink-0', cfg.color)} />
      <p className="text-sm text-dark-100 flex-1">{message}</p>
      <button onClick={onClose} className="text-dark-400 hover:text-dark-200">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

/* ── Confirm Dialog ───────────────────────────────────────── */
export function ConfirmDialog({
  open, title, message, confirmLabel = 'Confirm', danger = false,
  onConfirm, onCancel,
}: {
  open: boolean; title: string; message: string; confirmLabel?: string; danger?: boolean;
  onConfirm: () => void; onCancel: () => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative bg-dark-800 border border-dark-700 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-fade-in-up">
        <h3 className="text-lg font-semibold text-foreground mb-2">{title}</h3>
        <p className="text-sm text-dark-300 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <button className="btn-secondary" onClick={onCancel}>Cancel</button>
          <button className={danger ? 'btn-danger' : 'btn-primary'} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Progress Bar ─────────────────────────────────────────── */
export function ProgressBar({
  value, max = 100, color = 'bg-spider-500', className, showLabel = false,
}: {
  value: number; max?: number; color?: string; className?: string; showLabel?: boolean;
}) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <div className="progress-bar flex-1">
        <div className={clsx('progress-fill animate-progress', color)} style={{ width: `${pct}%` }} />
      </div>
      {showLabel && <span className="text-xs text-dark-400 w-8 text-right tabular-nums">{pct}%</span>}
    </div>
  );
}

/* ── Dropdown Menu ────────────────────────────────────────── */
export function DropdownMenu({
  trigger, children, align = 'right',
}: {
  trigger: React.ReactNode; children: React.ReactNode; align?: 'left' | 'right';
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <div onClick={() => setOpen(!open)}>{trigger}</div>
      {open && (
        <div
          className={clsx(
            'absolute z-40 mt-1 min-w-[180px] bg-dark-800 border border-dark-700 rounded-xl shadow-2xl py-1 animate-fade-in',
            align === 'right' ? 'right-0' : 'left-0',
          )}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export function DropdownItem({
  children, onClick, danger, disabled, icon: Icon,
}: {
  children: React.ReactNode; onClick?: () => void; danger?: boolean; disabled?: boolean;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left transition-colors',
        danger
          ? 'text-red-400 hover:bg-red-900/20'
          : 'text-dark-200 hover:bg-dark-700/60',
        disabled && 'opacity-40 cursor-not-allowed',
      )}
    >
      {Icon && <Icon className="h-4 w-4 flex-shrink-0" />}
      {children}
    </button>
  );
}

/* ── Status Badge (scan-aware) ────────────────────────────── */
export function StatusBadge({ status }: { status: string }) {
  const s = status?.toUpperCase() ?? '';
  const dotClass = s.includes('RUNNING') || s.includes('STARTING') ? 'status-dot-running'
    : s === 'FINISHED' ? 'status-dot-finished'
    : s === 'ERROR-FAILED' ? 'status-dot-failed'
    : s.includes('ABORT') || s.includes('STOP') ? 'status-dot-aborted'
    : s === 'SKIPPED' ? 'status-dot bg-dark-600'
    : 'status-dot bg-dark-500';

  const badgeClass = s.includes('RUNNING') || s.includes('STARTING') ? 'badge-running'
    : s === 'FINISHED' ? 'badge-success'
    : s === 'ERROR-FAILED' ? 'badge-critical'
    : s.includes('ABORT') || s.includes('STOP') ? 'badge-medium'
    : s === 'SKIPPED' ? 'badge-skipped'
    : 'badge-info';

  return (
    <span className={clsx('badge', badgeClass)}>
      <span className={dotClass} />
      {status}
    </span>
  );
}

/* ── Risk Pills (correlation summary row) ─────────────────── */
export function RiskPills({
  high = 0, medium = 0, low = 0, info = 0,
}: {
  high?: number; medium?: number; low?: number; info?: number;
}) {
  if (!high && !medium && !low && !info) return <span className="text-dark-600 text-xs">—</span>;
  return (
    <div className="flex items-center gap-1.5">
      {high > 0 && <span className="risk-pill risk-pill-high">{high} H</span>}
      {medium > 0 && <span className="risk-pill risk-pill-medium">{medium} M</span>}
      {low > 0 && <span className="risk-pill risk-pill-low">{low} L</span>}
      {info > 0 && <span className="risk-pill risk-pill-info">{info} I</span>}
    </div>
  );
}

/* ── Modal Shell (unified modal wrapper) ──────────────────── */
export function ModalShell({
  title, onClose, children, wide = false,
}: {
  title: string; onClose: () => void; children: React.ReactNode; wide?: boolean;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useRef(`modal-title-${Math.random().toString(36).slice(2, 8)}`).current;

  // Escape key handler
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  // Focus trap: keep Tab/Shift+Tab inside the dialog
  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;

    // Auto-focus the dialog panel on mount
    el.focus();

    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const focusable = el.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleTab);
    return () => document.removeEventListener('keydown', handleTab);
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <div
        ref={dialogRef}
        tabIndex={-1}
        className={clsx(
          'relative bg-dark-800 border border-dark-700 rounded-2xl p-6 shadow-2xl animate-fade-in-up max-h-[90vh] overflow-y-auto focus:outline-none',
          wide ? 'max-w-2xl w-full' : 'max-w-lg w-full',
        )}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 id={titleId} className="text-lg font-bold text-foreground">{title}</h2>
          <button
            onClick={onClose}
            className="text-dark-500 hover:text-dark-300 transition-colors"
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

/* ── Tabs Component ───────────────────────────────────────── */
export function Tabs<T extends string>({
  tabs, active, onChange,
}: {
  tabs: { key: T; label: string; icon?: React.ComponentType<{ className?: string }>; count?: number }[];
  active: T;
  onChange: (tab: T) => void;
}) {
  return (
    <div className="tab-bar">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={active === t.key ? 'tab-button-active' : 'tab-button'}
        >
          {t.icon && <t.icon className="h-4 w-4" />}
          {t.label}
          {t.count != null && (
            <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-dark-700/60 text-dark-400">
              {t.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
