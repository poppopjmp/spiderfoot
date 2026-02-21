/**
 * CommandPalette — ⌘K / Ctrl+K quick navigation overlay.
 *
 * Provides fuzzy search across pages, actions, and recent scans.
 * Uses emotional design: instant filtering, keyboard navigation,
 * smooth transitions.
 */
import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Search, LayoutDashboard, Radar, PlusCircle, Settings,
  Briefcase, BookOpen, Cpu, Users, Key, Lock, Bot,
  ArrowRight, Command,
} from 'lucide-react';
import { clsx } from 'clsx';
import { scanApi, type Scan } from '../lib/api';
import { useAuthStore } from '../lib/auth';

interface PaletteItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
  section: string;
}

const staticItems: PaletteItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, href: '/', section: 'Pages' },
  { id: 'new-scan', label: 'New Scan', description: 'Start a new reconnaissance', icon: PlusCircle, href: '/scans/new', section: 'Pages' },
  { id: 'scans', label: 'Scans', icon: Radar, href: '/scans', section: 'Pages' },
  { id: 'modules', label: 'Modules', icon: Cpu, href: '/modules', section: 'Pages' },
  { id: 'workspaces', label: 'Workspaces', icon: Briefcase, href: '/workspaces', section: 'Pages' },
  { id: 'documentation', label: 'Documentation', icon: BookOpen, href: '/documentation', section: 'Pages' },
  { id: 'settings', label: 'Settings', icon: Settings, href: '/settings', section: 'Pages' },
  { id: 'agents', label: 'AI Agents', icon: Bot, href: '/agents', section: 'Pages' },
];

const adminItems: PaletteItem[] = [
  { id: 'users', label: 'Users', icon: Users, href: '/users', section: 'Admin' },
  { id: 'api-keys', label: 'API Keys', icon: Key, href: '/api-keys', section: 'Admin' },
  { id: 'sso-settings', label: 'SSO Settings', icon: Lock, href: '/sso-settings', section: 'Admin' },
];

function fuzzyMatch(query: string, text: string): boolean {
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  if (t.includes(q)) return true;
  // Simple fuzzy: each char of query must appear in order in text
  let qi = 0;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (q[qi] === t[ti]) qi++;
  }
  return qi === q.length;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { isAuthenticated, hasPermission } = useAuthStore();

  // Fetch recent scans for palette
  const { data: scanData } = useQuery({
    queryKey: ['palette-scans'],
    queryFn: ({ signal }) => scanApi.list({ page: 1, page_size: 5, sort_by: 'created', sort_order: 'desc' }, signal),
    enabled: open,
    staleTime: 30_000,
  });

  const allItems = useMemo(() => {
    const items: PaletteItem[] = [...staticItems];
    if (isAuthenticated && hasPermission('user:read')) items.push(...adminItems);
    // Add recent scans
    if (scanData?.items) {
      for (const scan of scanData.items as Scan[]) {
        items.push({
          id: `scan-${scan.scan_id}`,
          label: scan.name || 'Untitled Scan',
          description: `${scan.target} · ${scan.status}`,
          icon: Radar,
          href: `/scans/${scan.scan_id}`,
          section: 'Recent Scans',
        });
      }
    }
    return items;
  }, [isAuthenticated, hasPermission, scanData]);

  const filtered = useMemo(() => {
    if (!query.trim()) return allItems;
    return allItems.filter((item) =>
      fuzzyMatch(query, item.label) ||
      fuzzyMatch(query, item.description ?? '') ||
      fuzzyMatch(query, item.section),
    );
  }, [allItems, query]);

  // Group by section
  const grouped = useMemo(() => {
    const map = new Map<string, PaletteItem[]>();
    for (const item of filtered) {
      const group = map.get(item.section) ?? [];
      group.push(item);
      map.set(item.section, group);
    }
    return map;
  }, [filtered]);

  // Reset selection on filter change
  useEffect(() => setSelectedIdx(0), [query]);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIdx(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Keyboard shortcut to open
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open]);

  const navigate_ = useCallback((href: string) => {
    setOpen(false);
    navigate(href);
  }, [navigate]);

  // Keyboard navigation in list
  const handleListKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIdx((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered[selectedIdx]) {
      navigate_(filtered[selectedIdx].href);
    }
  };

  // Scroll selected item into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${selectedIdx}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [selectedIdx]);

  if (!open) return null;

  let flatIdx = -1;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[15vh]">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setOpen(false)} />
      <div className="relative w-full max-w-lg bg-dark-800 border border-dark-700 rounded-2xl shadow-2xl overflow-hidden animate-fade-in-up">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-dark-700">
          <Search className="h-4 w-4 text-dark-500 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search pages, scans, actions..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleListKey}
            role="combobox"
            aria-expanded={filtered.length > 0}
            aria-controls="cmd-palette-listbox"
            aria-activedescendant={selectedIdx >= 0 ? `cmd-palette-opt-${selectedIdx}` : undefined}
            aria-autocomplete="list"
            className="flex-1 bg-transparent text-foreground text-sm placeholder:text-dark-500 focus:outline-none"
          />
          <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-mono text-dark-500 bg-dark-700/60 rounded">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div ref={listRef} id="cmd-palette-listbox" role="listbox" className="max-h-80 overflow-y-auto py-2">
          {filtered.length > 0 ? (
            Array.from(grouped.entries()).map(([section, items]) => (
              <div key={section}>
                <p className="px-4 pt-2 pb-1 text-[10px] font-semibold text-dark-500 uppercase tracking-wider">
                  {section}
                </p>
                {items.map((item) => {
                  flatIdx++;
                  const idx = flatIdx;
                  return (
                    <button
                      key={item.id}
                      id={`cmd-palette-opt-${idx}`}
                      role="option"
                      aria-selected={idx === selectedIdx}
                      data-idx={idx}
                      onClick={() => navigate_(item.href)}
                      className={clsx(
                        'w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors',
                        idx === selectedIdx
                          ? 'bg-spider-600/20 text-spider-400'
                          : 'text-dark-200 hover:bg-dark-700/50',
                      )}
                    >
                      <item.icon className="h-4 w-4 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium">{item.label}</span>
                        {item.description && (
                          <span className="text-xs text-dark-500 ml-2">{item.description}</span>
                        )}
                      </div>
                      <ArrowRight className="h-3 w-3 text-dark-600 flex-shrink-0" />
                    </button>
                  );
                })}
              </div>
            ))
          ) : (
            <div className="px-4 py-8 text-center">
              <p className="text-sm text-dark-500">No results for &ldquo;{query}&rdquo;</p>
            </div>
          )}
        </div>

        {/* Footer hint */}
        <div className="flex items-center gap-4 px-4 py-2 border-t border-dark-700 text-[10px] text-dark-500">
          <span className="flex items-center gap-1">
            <kbd className="px-1 bg-dark-700/60 rounded">↑↓</kbd> navigate
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 bg-dark-700/60 rounded">↵</kbd> select
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 bg-dark-700/60 rounded">esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * Small trigger button to hint at the command palette.
 * Shows Ctrl+K / ⌘K keyboard shortcut.
 */
export function CommandPaletteTrigger() {
  return (
    <button
      onClick={() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))}
      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-dark-400 hover:text-dark-200 hover:bg-dark-800 rounded-lg transition-colors"
    >
      <Command className="h-3.5 w-3.5" />
      <span className="flex-1 text-left">Quick Search</span>
      <kbd className="text-[10px] font-mono text-dark-500 bg-dark-700/60 px-1.5 py-0.5 rounded">
        ⌘K
      </kbd>
    </button>
  );
}
