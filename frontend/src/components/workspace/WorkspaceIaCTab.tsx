import { memo, useEffect, useRef, useState, useCallback } from 'react';
import mermaid from 'mermaid';
import { type Workspace, type WorkspaceTarget, type Scan } from '../../lib/api';
import { GitBranch, Download, Copy, CheckCircle2, Loader2 } from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────

interface WorkspaceIaCTabProps {
  workspace?: Workspace;
  workspaceId: string;
  targets: WorkspaceTarget[];
  /** All scans associated with this workspace (both linked + implicit). */
  scans: Scan[];
}

// ── Helpers ───────────────────────────────────────────────────

/** Map raw scan status strings → Mermaid classDef names. */
const STATUS_CLASS: Record<string, string> = {
  FINISHED:  'sfFinished',
  COMPLETE:  'sfFinished',
  COMPLETED: 'sfFinished',
  RUNNING:   'sfRunning',
  STARTING:  'sfRunning',
  SCANNING:  'sfRunning',
  ERROR:     'sfError',
  FAILED:    'sfError',
  ABORTED:   'sfError',
  QUEUED:    'sfQueued',
  PAUSED:    'sfPaused',
};

/** Escape characters that break Mermaid label strings. */
function mml(s: string): string {
  return s
    .replace(/"/g,  '#quot;')
    .replace(/\\/g, '/')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/\n/g, ' ');
}

function buildDiagram(
  workspace: Workspace | undefined,
  targets: WorkspaceTarget[],
  scans: Scan[],
): string {
  const wsName = mml((workspace?.name ?? 'Workspace').slice(0, 40));

  const lines: string[] = [
    'flowchart TB',
    '  classDef sfWS       fill:#7c3aed,stroke:#6d28d9,color:#fff,font-weight:bold',
    '  classDef sfTarget   fill:#1e3a8a,stroke:#1d4ed8,color:#93c5fd',
    '  classDef sfFinished fill:#059669,stroke:#047857,color:#fff',
    '  classDef sfRunning  fill:#2563eb,stroke:#1d4ed8,color:#fff',
    '  classDef sfError    fill:#dc2626,stroke:#b91c1c,color:#fff',
    '  classDef sfQueued   fill:#d97706,stroke:#b45309,color:#fff',
    '  classDef sfPaused   fill:#4b5563,stroke:#374151,color:#d1d5db',
    '',
    `  WS[["🔍 ${wsName}"]]:::sfWS`,
  ];

  // Group scans by their target value
  const scansByTarget = new Map<string, Scan[]>();
  for (const s of scans) {
    const key = s.target ?? '__orphan__';
    if (!scansByTarget.has(key)) scansByTarget.set(key, []);
    scansByTarget.get(key)!.push(s);
  }

  // Emit target nodes
  targets.forEach((t, ti) => {
    const tid   = `T${ti}`;
    const val   = mml(t.value.slice(0, 40));
    const typ   = t.type.replace(/_/g, ' ');
    lines.push(`  ${tid}["📌 ${val}\\n${typ}"]:::sfTarget`);
    lines.push(`  WS --> ${tid}`);

    const tScans = scansByTarget.get(t.value) ?? [];
    tScans.forEach((s, si) => {
      const sid        = `S${ti}_${si}`;
      const statusRaw  = (s.status ?? '').toUpperCase();
      const cls        = STATUS_CLASS[statusRaw] ?? 'sfPaused';
      const name       = mml((s.name || 'Untitled').slice(0, 28));
      const status     = mml(s.status ?? 'unknown');
      const evts       = s.result_count != null ? `\\n${s.result_count.toLocaleString()} events` : '';
      lines.push(`  ${sid}["🔍 ${name}\\n${status}${evts}"]:::${cls}`);
      lines.push(`  ${tid} --> ${sid}`);
    });

    // mark target as consumed
    scansByTarget.delete(t.value);
  });

  // Orphan scans (linked but target not in workspace targets)
  const orphanEntries = [...scansByTarget.entries()].filter(([k]) => k !== '__orphan__');
  const orphans       = [
    ...scansByTarget.get('__orphan__') ?? [],
    ...orphanEntries.flatMap(([, v]) => v),
  ];

  if (orphans.length > 0) {
    lines.push(`  ORPH["📂 Other Linked Scans"]:::sfTarget`);
    lines.push(`  WS --> ORPH`);
    orphans.forEach((s, i) => {
      const sid       = `SX${i}`;
      const statusRaw = (s.status ?? '').toUpperCase();
      const cls       = STATUS_CLASS[statusRaw] ?? 'sfPaused';
      const name      = mml((s.name || 'Untitled').slice(0, 28));
      const status    = mml(s.status ?? 'unknown');
      const evts      = s.result_count != null ? `\\n${s.result_count.toLocaleString()} events` : '';
      const tgt       = s.target ? `\\n${mml(s.target.slice(0, 28))}` : '';
      lines.push(`  ${sid}["🔍 ${name}${tgt}\\n${status}${evts}"]:::${cls}`);
      lines.push(`  ORPH --> ${sid}`);
    });
  }

  // Completely empty workspace hint
  if (targets.length === 0 && scans.length === 0) {
    lines.push(`  EMPTY["No targets or scans yet\\nAdd targets to get started"]:::sfPaused`);
    lines.push(`  WS --> EMPTY`);
  }

  return lines.join('\n');
}

// ── Legend item ───────────────────────────────────────────────

const LEGEND = [
  { bg: 'bg-[#7c3aed]', label: 'Workspace' },
  { bg: 'bg-[#1e3a8a]', label: 'Target' },
  { bg: 'bg-[#059669]', label: 'Completed' },
  { bg: 'bg-[#2563eb]', label: 'Running' },
  { bg: 'bg-[#dc2626]', label: 'Error' },
  { bg: 'bg-[#d97706]', label: 'Queued' },
  { bg: 'bg-[#4b5563]', label: 'Other' },
];

// ── Component ─────────────────────────────────────────────────

function WorkspaceIaCTab({ workspace, workspaceId, targets, scans }: WorkspaceIaCTabProps) {
  const containerRef              = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState('');
  const [renderErr, setRenderErr]   = useState<string | null>(null);
  const [loading, setLoading]       = useState(true);
  const [copied,  setCopied]        = useState(false);
  const [showSrc, setShowSrc]       = useState(false);

  const source = buildDiagram(workspace, targets, scans);

  // (re-)render whenever the diagram source changes
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setRenderErr(null);

    mermaid.initialize({
      startOnLoad:   false,
      theme:         'dark',
      flowchart:     { curve: 'basis', useMaxWidth: true },
      securityLevel: 'loose',
    });

    // mermaid v10+ returns a Promise<{ svg }>
    const diagramId = `ws-iac-${workspaceId.replace(/[^a-zA-Z0-9]/g, '')}`;
    (mermaid.render(diagramId, source) as Promise<{ svg: string }>)
      .then(({ svg }) => {
        if (alive) { setSvgContent(svg); setLoading(false); }
      })
      .catch((err: Error) => {
        if (alive) { setRenderErr(err.message); setLoading(false); }
      });

    return () => { alive = false; };
  }, [source, workspaceId]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(source).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [source]);

  const handleDownloadSVG = useCallback(() => {
    if (!svgContent) return;
    const blob = new Blob([svgContent], { type: 'image/svg+xml' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `workspace-iac-${workspaceId}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  }, [svgContent, workspaceId]);

  return (
    <div className="space-y-4 animate-fade-in">

      {/* Header card */}
      <div className="card">
        <div className="flex items-start sm:items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <GitBranch className="h-5 w-5 text-spider-400" />
              Infrastructure Map
            </h2>
            <p className="text-sm text-dark-400 mt-0.5">
              Visual topology of workspace targets and associated scans.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              className="btn-secondary text-xs flex items-center gap-1.5"
              onClick={() => setShowSrc((v) => !v)}
            >
              <GitBranch className="h-3.5 w-3.5" />
              {showSrc ? 'Hide' : 'Show'} Source
            </button>
            <button
              className="btn-secondary text-xs flex items-center gap-1.5"
              onClick={handleCopy}
            >
              {copied
                ? <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />
                : <Copy className="h-3.5 w-3.5" />}
              {copied ? 'Copied!' : 'Copy Mermaid'}
            </button>
            <button
              className="btn-secondary text-xs flex items-center gap-1.5"
              onClick={handleDownloadSVG}
              disabled={!svgContent}
            >
              <Download className="h-3.5 w-3.5" />
              Export SVG
            </button>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="card py-3">
        <p className="text-xs text-dark-500 mb-2">Legend</p>
        <div className="flex flex-wrap gap-3">
          {LEGEND.map(({ bg, label }) => (
            <span key={label} className="flex items-center gap-1.5 text-xs">
              <span className={`w-3 h-3 rounded-sm ${bg} inline-block flex-shrink-0`} />
              <span className="text-dark-300">{label}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card text-center">
          <p className="text-2xl font-bold text-foreground">{targets.length}</p>
          <p className="text-xs text-dark-400 mt-1">Targets</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-foreground">{scans.length}</p>
          <p className="text-xs text-dark-400 mt-1">Scans</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-foreground">
            {scans.filter((s) => {
              const st = (s.status ?? '').toUpperCase();
              return STATUS_CLASS[st] === 'sfFinished';
            }).length}
          </p>
          <p className="text-xs text-dark-400 mt-1">Completed</p>
        </div>
      </div>

      {/* Mermaid diagram */}
      <div className="card overflow-hidden">
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 text-spider-400 animate-spin" />
          </div>
        )}
        {renderErr && (
          <div className="py-8 text-center">
            <p className="text-red-400 font-medium text-sm">Diagram render error</p>
            <p className="text-xs mt-1 font-mono text-dark-400 max-w-lg mx-auto break-all">{renderErr}</p>
          </div>
        )}
        {!loading && !renderErr && (
          <div
            ref={containerRef}
            className="overflow-x-auto p-2 [&_svg]:max-w-full [&_svg]:h-auto"
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        )}
      </div>

      {/* Raw Mermaid source */}
      {showSrc && (
        <div className="card">
          <h3 className="text-sm font-semibold text-foreground mb-3">Mermaid Source</h3>
          <pre className="overflow-x-auto text-xs text-dark-300 bg-dark-900/60 rounded-lg p-4 font-mono whitespace-pre leading-relaxed">
            {source}
          </pre>
          <p className="text-xs text-dark-500 mt-2">
            Paste into{' '}
            <a
              href="https://mermaid.live"
              target="_blank"
              rel="noreferrer"
              className="text-spider-400 hover:text-spider-300 underline"
            >
              mermaid.live
            </a>{' '}
            to edit or share.
          </p>
        </div>
      )}
    </div>
  );
}

export default memo(WorkspaceIaCTab);
