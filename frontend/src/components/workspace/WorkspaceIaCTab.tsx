import { memo, useEffect, useRef, useState, useCallback } from 'react';
import mermaid from 'mermaid';
import { useMutation } from '@tanstack/react-query';
import {
  iacApi,
  type IaCRequest, type IaCResponse, type IaCValidationResult,
  type IaCReviewData, type IaCReviewIssue,
  type Workspace, type WorkspaceTarget, type Scan,
} from '../../lib/api';
import {
  GitBranch, Download, Copy, CheckCircle2, Loader2, Server,
  XCircle, AlertTriangle, ChevronDown, ChevronRight,
  Code2, RefreshCw, Bot, Shield, ThumbsUp,
} from 'lucide-react';

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

// ── IaC generator helpers ─────────────────────────────────────

const PROVIDERS = [
  { value: 'aws',          label: 'Amazon Web Services (AWS)' },
  { value: 'azure',        label: 'Microsoft Azure' },
  { value: 'gcp',          label: 'Google Cloud Platform (GCP)' },
  { value: 'digitalocean', label: 'DigitalOcean' },
  { value: 'vmware',       label: 'VMware vSphere' },
] as const;
type Provider = (typeof PROVIDERS)[number]['value'];

const CATEGORY_LABELS: Record<string, string> = {
  terraform: 'Terraform', ansible: 'Ansible',
  docker: 'Docker Compose', packer: 'Packer', docs: 'Documentation',
};
const CATEGORY_COLORS: Record<string, string> = {
  terraform: 'text-purple-400', ansible: 'text-red-400',
  docker: 'text-blue-400', packer: 'text-yellow-400', docs: 'text-dark-300',
};

function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function downloadAllFiles(bundle: IaCResponse['bundle'], provider: string) {
  let archive = `# SpiderFoot IaC Bundle — Provider: ${provider}\n# Generated: ${new Date().toISOString()}\n\n`;
  for (const [category, files] of Object.entries(bundle)) {
    if (!files || typeof files !== 'object') continue;
    for (const [filename, content] of Object.entries(files)) {
      archive += `${'='.repeat(60)}\n# ${category}/${filename}\n${'='.repeat(60)}\n${content}\n\n`;
    }
  }
  downloadText(`spiderfoot-iac-${provider}-${Date.now()}.txt`, archive);
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <div
        role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        className={`relative w-9 h-5 rounded-full transition-colors ${checked ? 'bg-spider-500' : 'bg-dark-700'} cursor-pointer`}
      >
        <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-4' : 'translate-x-0'}`} />
      </div>
      <span className="text-sm text-dark-200">{label}</span>
    </label>
  );
}

function ValidationBadge({ result }: { result: IaCValidationResult }) {
  return (
    <div className={`flex items-start gap-2 text-xs rounded-lg px-3 py-2 ${result.valid ? 'bg-green-900/20 border border-green-800/30' : 'bg-red-900/20 border border-red-800/30'}`}>
      {result.valid
        ? <CheckCircle2 className="h-3.5 w-3.5 text-green-400 mt-0.5 flex-shrink-0" />
        : <XCircle className="h-3.5 w-3.5 text-red-400 mt-0.5 flex-shrink-0" />
      }
      <div>
        <span className={`font-mono font-medium ${result.valid ? 'text-green-300' : 'text-red-300'}`}>{result.artifact_type}/{result.file_name}</span>
        {result.errors.map((e, i) => <p key={i} className="text-red-400 mt-0.5">{e}</p>)}
        {result.warnings.map((w, i) => (
          <p key={i} className="text-yellow-400 mt-0.5 flex gap-1"><AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />{w}</p>
        ))}
      </div>
    </div>
  );
}

const SEVERITY_STYLES: Record<string, { bg: string; text: string; border: string; label: string }> = {
  critical: { bg: 'bg-red-900/25',    text: 'text-red-300',    border: 'border-red-800/40',    label: 'CRITICAL' },
  high:     { bg: 'bg-orange-900/25', text: 'text-orange-300', border: 'border-orange-800/40', label: 'HIGH' },
  medium:   { bg: 'bg-yellow-900/25', text: 'text-yellow-300', border: 'border-yellow-800/40', label: 'MEDIUM' },
  low:      { bg: 'bg-blue-900/20',   text: 'text-blue-300',   border: 'border-blue-800/30',   label: 'LOW' },
  info:     { bg: 'bg-dark-800',      text: 'text-dark-300',   border: 'border-dark-700',      label: 'INFO' },
};
const STATUS_STYLES: Record<string, { color: string; label: string }> = {
  approved:      { color: 'text-green-400',  label: 'Approved' },
  needs_changes: { color: 'text-yellow-400', label: 'Needs Changes' },
  rejected:      { color: 'text-red-400',    label: 'Rejected' },
};

function ScoreDial({ score }: { score: number }) {
  const color     = score >= 80 ? 'text-green-400' : score >= 50 ? 'text-yellow-400' : 'text-red-400';
  const ringColor = score >= 80 ? 'stroke-green-500' : score >= 50 ? 'stroke-yellow-500' : 'stroke-red-500';
  const r = 28, circ = 2 * Math.PI * r, dash = (score / 100) * circ;
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="72" height="72" className="-rotate-90">
        <circle cx="36" cy="36" r={r} strokeWidth="6" className="stroke-dark-700" fill="none" />
        <circle cx="36" cy="36" r={r} strokeWidth="6" className={ringColor} fill="none"
          strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round" />
      </svg>
      <span className={`-mt-12 text-xl font-bold ${color}`}>{score}</span>
      <span className="text-xs text-dark-400 mt-1">Security Score</span>
    </div>
  );
}

function IssueCard({ issue }: { issue: IaCReviewIssue }) {
  const [open, setOpen] = useState(false);
  const s = SEVERITY_STYLES[issue.severity] ?? SEVERITY_STYLES.info;
  return (
    <div className={`border rounded-lg overflow-hidden ${s.border}`}>
      <button className={`w-full flex items-center gap-2 px-3 py-2.5 text-sm text-left ${s.bg} hover:brightness-110 transition-all`} onClick={() => setOpen(o => !o)}>
        {open ? <ChevronDown className="h-3.5 w-3.5 text-dark-400 flex-shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 text-dark-400 flex-shrink-0" />}
        <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${s.bg} ${s.text} border ${s.border} flex-shrink-0`}>{s.label}</span>
        <span className="font-mono text-xs text-dark-400 flex-shrink-0">{issue.file}</span>
        <span className={`text-xs font-medium ${s.text} flex-1 truncate`}>{issue.description}</span>
        <span className="text-xs text-dark-500 capitalize flex-shrink-0">{issue.category.replace('_', ' ')}</span>
      </button>
      {open && (
        <div className={`px-4 py-3 text-xs space-y-2 ${s.bg} border-t ${s.border}`}>
          <p className="text-dark-200">{issue.description}</p>
          <div>
            <p className="text-dark-400 font-semibold mb-1 uppercase tracking-wide text-xs">Suggested Fix</p>
            <pre className="whitespace-pre-wrap text-green-300 font-mono bg-dark-900/60 rounded p-2 leading-relaxed">{issue.fix}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewPanel({ review }: { review: IaCReviewData }) {
  const statusStyle = STATUS_STYLES[review.review_status] ?? STATUS_STYLES.needs_changes;
  return (
    <div className="card p-5 space-y-5 border-spider-700/40">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-spider-600/20 border border-spider-600/30 flex items-center justify-center flex-shrink-0">
            <Bot className="h-5 w-5 text-spider-400" />
          </div>
          <div>
            <h4 className="font-semibold text-foreground">IaC Advisor Review</h4>
            <p className={`text-sm font-medium ${statusStyle.color}`}>{statusStyle.label}</p>
          </div>
        </div>
        <ScoreDial score={review.security_score} />
      </div>
      {review.summary && <p className="text-sm text-dark-300 leading-relaxed">{review.summary}</p>}
      {review.issues.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {(['critical', 'high', 'medium', 'low'] as const).map((k) => {
            const cnt = review.issues.filter(i => i.severity === k).length;
            const styles: Record<string, string> = {
              critical: 'text-red-400 bg-red-900/20 border-red-800/30',
              high:     'text-orange-400 bg-orange-900/20 border-orange-800/30',
              medium:   'text-yellow-400 bg-yellow-900/20 border-yellow-800/30',
              low:      'text-blue-400 bg-blue-900/20 border-blue-800/30',
            };
            if (!cnt) return null;
            return <span key={k} className={`text-xs font-semibold px-2 py-1 rounded-full border ${styles[k]}`}>{cnt} {k.charAt(0).toUpperCase() + k.slice(1)}</span>;
          })}
        </div>
      )}
      {review.issues.length > 0 && (
        <div className="space-y-2">{review.issues.map((issue, i) => <IssueCard key={i} issue={issue} />)}</div>
      )}
      {review.positive_findings.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-dark-400 uppercase tracking-wide mb-2 flex items-center gap-1">
            <ThumbsUp className="h-3.5 w-3.5 text-green-400" /> What's done well
          </p>
          <ul className="space-y-1">
            {review.positive_findings.map((p, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-dark-300">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-400 mt-0.5 flex-shrink-0" /> {p}
              </li>
            ))}
          </ul>
        </div>
      )}
      {review.compliance_notes && (
        <div className="flex items-start gap-2 text-xs text-dark-400 bg-dark-800 rounded-lg px-3 py-2">
          <Shield className="h-3.5 w-3.5 text-spider-400 mt-0.5 flex-shrink-0" />
          <span>{review.compliance_notes}</span>
        </div>
      )}
    </div>
  );
}

function FileCard({ category, filename, content }: { category: string; filename: string; content: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-dark-700 rounded-lg overflow-hidden">
      <button className="w-full flex items-center justify-between px-3 py-2 text-sm bg-dark-800 hover:bg-dark-750 transition-colors" onClick={() => setOpen(o => !o)}>
        <span className="flex items-center gap-2">
          {open ? <ChevronDown className="h-4 w-4 text-dark-400" /> : <ChevronRight className="h-4 w-4 text-dark-400" />}
          <span className={`font-mono text-xs font-medium ${CATEGORY_COLORS[category] ?? 'text-dark-300'}`}>{category}/</span>
          <span className="font-mono text-xs text-dark-200">{filename}</span>
        </span>
        <button className="text-dark-400 hover:text-dark-100 p-1 rounded" title={`Download ${filename}`}
          onClick={(e) => { e.stopPropagation(); downloadText(filename, content); }}>
          <Download className="h-3.5 w-3.5" />
        </button>
      </button>
      {open && (
        <pre className="p-3 text-xs text-dark-200 bg-dark-900 overflow-x-auto max-h-96 font-mono whitespace-pre leading-relaxed">{content}</pre>
      )}
    </div>
  );
}

// ── Workspace IaC helpers ─────────────────────────────────────

function sanitizeTarget(s: string): string {
  return (s || 'target')
    .replace(/[^a-zA-Z0-9]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 20)
    .toLowerCase() || 'target';
}

interface ScanPair { scan: Scan; data: IaCResponse }
interface ScanFail { scan: Scan; error: string }
interface MergedResult {
  provider:    string;
  scan_count:  number;
  bundle:      IaCResponse['bundle'];
  files:       IaCResponse['files'];
  validation:  IaCValidationResult[];
  all_valid:   boolean;
  profile_summary: {
    ip_count: number; port_count: number; service_count: number;
    web_server?: string; os_detected?: string;
  };
}

function buildMerged(pairs: ScanPair[], provider: string): MergedResult {
  const bundle: IaCResponse['bundle'] = {};
  const files:  IaCResponse['files']  = {};
  const validations: IaCValidationResult[] = [];
  const summaries: IaCResponse['profile_summary'][] = [];

  for (const { scan, data } of pairs) {
    const pfx = sanitizeTarget(scan.target ?? scan.name ?? scan.scan_id);
    for (const [cat, catFiles] of Object.entries(data.bundle ?? {})) {
      bundle[cat] ??= {};
      files[cat]  ??= [];
      for (const [fname, content] of Object.entries(catFiles ?? {})) {
        const nfn = `${pfx}__${fname}`;
        bundle[cat][nfn] = content;
        files[cat].push(nfn);
      }
    }
    for (const v of data.validation ?? [])
      validations.push({ ...v, file_name: `${pfx}__${v.file_name}` });
    summaries.push(data.profile_summary);
  }

  const ws = [...new Set(summaries.map(s => s.web_server).filter(Boolean) as string[])];
  const os = [...new Set(summaries.map(s => s.os_detected).filter(Boolean) as string[])];
  return {
    provider,
    scan_count: pairs.length,
    bundle, files,
    validation: validations,
    all_valid:  validations.length === 0 || validations.every(v => v.valid),
    profile_summary: {
      ip_count:      summaries.reduce((a, p) => a + (p.ip_count      ?? 0), 0),
      port_count:    summaries.reduce((a, p) => a + (p.port_count    ?? 0), 0),
      service_count: summaries.reduce((a, p) => a + (p.service_count ?? 0), 0),
      web_server:    ws.join(' / ') || undefined,
      os_detected:   os.join(' / ') || undefined,
    },
  };
}

// ── Workspace IaC panel ────────────────────────────────────────

function WorkspaceIaCPanel({ scans }: { scans: Scan[] }) {
  const [provider,         setProvider]         = useState<Provider>('aws');
  const [includeTerraform, setIncludeTerraform] = useState(true);
  const [includeAnsible,   setIncludeAnsible]   = useState(true);
  const [includeDocker,    setIncludeDocker]    = useState(true);
  const [includePacker,    setIncludePacker]    = useState(false);
  const [runValidate,      setRunValidate]      = useState(true);
  const [includedIds,      setIncludedIds]      = useState<Set<string>>(
    () => new Set(scans.map(s => s.scan_id))
  );
  const [generating, setGenerating] = useState(false);
  const [progress,   setProgress]   = useState({ done: 0, total: 0 });
  const [result,     setResult]     = useState<MergedResult | null>(null);
  const [successes,  setSuccesses]  = useState<ScanPair[]>([]);
  const [failures,   setFailures]   = useState<ScanFail[]>([]);
  const [review,     setReview]     = useState<IaCReviewData | null>(null);

  const reviewMut = useMutation({
    mutationFn: (r: MergedResult) => iacApi.review({
      provider: r.provider, bundle: r.bundle, files: r.files,
    }),
    onSuccess: (data) => setReview(data.data),
  });

  const included = scans.filter(s => includedIds.has(s.scan_id));

  const handleGenerate = useCallback(async () => {
    if (included.length === 0) return;
    setGenerating(true);
    setProgress({ done: 0, total: included.length });
    setResult(null); setSuccesses([]); setFailures([]); setReview(null);

    const req: IaCRequest = {
      provider, include_terraform: includeTerraform, include_ansible: includeAnsible,
      include_docker: includeDocker, include_packer: includePacker, validate: runValidate,
    };

    const settled = await Promise.allSettled(
      included.map(scan =>
        iacApi.generate(scan.scan_id, req).then(data => {
          setProgress(p => ({ ...p, done: p.done + 1 }));
          return { scan, data };
        })
      )
    );

    const ok: ScanPair[] = [];
    const err: ScanFail[] = [];
    settled.forEach((r, i) => {
      if (r.status === 'fulfilled') ok.push(r.value);
      else err.push({ scan: included[i], error: (r.reason as Error)?.message ?? 'Generation failed' });
    });

    setSuccesses(ok); setFailures(err);
    if (ok.length > 0) setResult(buildMerged(ok, provider));
    setGenerating(false);
  }, [included, provider, includeTerraform, includeAnsible, includeDocker, includePacker, runValidate]);

  const toggleScan = (scanId: string) =>
    setIncludedIds(prev => { const n = new Set(prev); n.has(scanId) ? n.delete(scanId) : n.add(scanId); return n; });

  const allFiles = result
    ? Object.entries(result.bundle).flatMap(([cat, catFiles]) =>
        Object.entries(catFiles ?? {}).map(([filename, content]) => ({ category: cat, filename, content })))
    : [];

  return (
    <div className="space-y-4">
      {/* Config card */}
      <div className="card p-5 space-y-5">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-spider-400" />
          <h4 className="font-semibold text-foreground">Workspace IaC Generator</h4>
          <span className="ml-auto text-xs text-dark-400 bg-dark-800 rounded px-2 py-0.5">
            {included.length}/{scans.length} scan{scans.length !== 1 ? 's' : ''} included
          </span>
        </div>
        <p className="text-sm text-dark-400">
          Runs IaC generation across all selected scans in parallel and merges the results into a
          single unified bundle. Files are namespaced by target to avoid naming collisions.
        </p>

        {/* Scan inclusion list */}
        <div>
          <label className="block text-xs font-medium text-dark-300 mb-2 uppercase tracking-wide">Include Scans</label>
          <div className="space-y-1 max-h-44 overflow-y-auto pr-1">
            {scans.map(s => {
              const finished = ['FINISHED', 'COMPLETE', 'COMPLETED'].includes((s.status ?? '').toUpperCase());
              return (
                <label key={s.scan_id} className="flex items-center gap-2.5 cursor-pointer text-sm py-1.5 px-2 rounded hover:bg-dark-800 transition-colors">
                  <input
                    type="checkbox"
                    checked={includedIds.has(s.scan_id)}
                    onChange={() => toggleScan(s.scan_id)}
                    className="accent-spider-500 flex-shrink-0"
                  />
                  <span className="flex-1 text-dark-200 truncate min-w-0">{s.name || 'Untitled'}</span>
                  <span className="text-dark-500 text-xs font-mono truncate max-w-[160px]">{s.target}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 ${
                    finished ? 'bg-green-900/30 text-green-400' : 'bg-yellow-900/30 text-yellow-400'
                  }`}>{s.status ?? 'unknown'}</span>
                </label>
              );
            })}
          </div>
          <div className="flex gap-3 mt-2 text-xs">
            <button className="text-spider-400 hover:text-spider-300"
              onClick={() => setIncludedIds(new Set(scans.map(s => s.scan_id)))}>
              Select all
            </button>
            <span className="text-dark-600">·</span>
            <button className="text-spider-400 hover:text-spider-300"
              onClick={() => setIncludedIds(new Set(
                scans.filter(s => ['FINISHED','COMPLETE','COMPLETED'].includes((s.status ?? '').toUpperCase())).map(s => s.scan_id)
              ))}>
              Completed only
            </button>
            <span className="text-dark-600">·</span>
            <button className="text-dark-500 hover:text-dark-400" onClick={() => setIncludedIds(new Set())}>Clear</button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div>
            <label className="block text-xs font-medium text-dark-300 mb-1.5 uppercase tracking-wide">Cloud Provider</label>
            <select value={provider} onChange={e => setProvider(e.target.value as Provider)} className="input w-full text-sm">
              {PROVIDERS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-dark-300 mb-1.5 uppercase tracking-wide">Artifacts</label>
            <div className="space-y-2">
              <Toggle label="Terraform"        checked={includeTerraform} onChange={setIncludeTerraform} />
              <Toggle label="Ansible Playbook" checked={includeAnsible}   onChange={setIncludeAnsible} />
              <Toggle label="Docker Compose"   checked={includeDocker}    onChange={setIncludeDocker} />
              <Toggle label="Packer"           checked={includePacker}    onChange={setIncludePacker} />
              <Toggle label="Validate output"  checked={runValidate}      onChange={setRunValidate} />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 pt-1 flex-wrap">
          <button
            className="btn-primary flex items-center gap-2"
            onClick={handleGenerate}
            disabled={generating || included.length === 0}
          >
            {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Code2 className="h-4 w-4" />}
            {generating
              ? `Generating… ${progress.done}/${progress.total}`
              : `Generate Workspace IaC (${included.length} scan${included.length !== 1 ? 's' : ''})`
            }
          </button>
          {result && !generating && (
            <>
              <button className="btn-secondary flex items-center gap-2 text-sm" onClick={handleGenerate}>
                <RefreshCw className="h-4 w-4" /> Regenerate
              </button>
              <button
                className="btn-secondary flex items-center gap-2 text-sm"
                onClick={() => reviewMut.mutate(result)}
                disabled={reviewMut.isPending}
              >
                {reviewMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
                AI Review
              </button>
            </>
          )}
        </div>

        {/* Progress bar */}
        {generating && (
          <div>
            <div className="flex justify-between text-xs text-dark-400 mb-1">
              <span>Processing scans in parallel…</span>
              <span>{progress.done}/{progress.total}</span>
            </div>
            <div className="h-1.5 bg-dark-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-spider-500 rounded-full transition-all duration-300"
                style={{ width: progress.total > 0 ? `${(progress.done / progress.total) * 100}%` : '0%' }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Per-scan result badges */}
      {(successes.length > 0 || failures.length > 0) && !generating && (
        <div className="card p-4">
          <p className="text-xs font-medium text-dark-400 uppercase tracking-wide mb-3">Scan Results</p>
          <div className="flex flex-wrap gap-2">
            {successes.map(({ scan }) => (
              <span key={scan.scan_id} className="flex items-center gap-1.5 text-xs bg-green-900/20 border border-green-800/30 text-green-300 rounded-full px-2.5 py-1">
                <CheckCircle2 className="h-3 w-3 flex-shrink-0" />
                {scan.target ?? scan.name ?? 'Untitled'}
              </span>
            ))}
            {failures.map(({ scan, error }) => (
              <span key={scan.scan_id} title={error} className="flex items-center gap-1.5 text-xs bg-red-900/20 border border-red-800/30 text-red-300 rounded-full px-2.5 py-1">
                <XCircle className="h-3 w-3 flex-shrink-0" />
                {scan.target ?? scan.name ?? 'Untitled'}
              </span>
            ))}
          </div>
          {failures.length > 0 && (
            <div className="mt-3 space-y-1">
              {failures.map(({ scan, error }) => (
                <p key={scan.scan_id} className="text-xs text-red-400">
                  <span className="font-mono">{scan.target ?? scan.name}</span>: {error}
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {result && Object.keys(result.bundle ?? {}).length > 0 && (
        <>
          {/* Aggregated profile */}
          <div className="card p-5">
            <h4 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
              <Server className="h-4 w-4 text-spider-400" /> Aggregated Profile
              <span className="ml-auto text-xs text-dark-400 font-normal">
                {result.scan_count} scan{result.scan_count !== 1 ? 's' : ''} · {result.provider}
              </span>
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {[
                { label: 'IP Addresses', value: result.profile_summary.ip_count },
                { label: 'Open Ports',   value: result.profile_summary.port_count },
                { label: 'Services',     value: result.profile_summary.service_count },
                { label: 'Web Servers',  value: result.profile_summary.web_server ?? '—' },
                { label: 'OS Detected',  value: result.profile_summary.os_detected ?? '—' },
              ].map(({ label, value }) => (
                <div key={label} className="bg-dark-800 rounded-lg p-3 text-center">
                  <div className="text-lg font-bold text-foreground">{value}</div>
                  <div className="text-xs text-dark-400 mt-0.5">{label}</div>
                </div>
              ))}
            </div>
          </div>

          {result.validation.length > 0 && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  {result.all_valid
                    ? <CheckCircle2 className="h-4 w-4 text-green-400" />
                    : <XCircle className="h-4 w-4 text-red-400" />
                  }
                  Validation Results
                </h4>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                  result.all_valid ? 'bg-green-900/40 text-green-300' : 'bg-red-900/40 text-red-300'
                }`}>
                  {result.validation.filter(v => v.valid).length}/{result.validation.length} passed
                </span>
              </div>
              <div className="space-y-2">
                {result.validation.map((v, i) => <ValidationBadge key={i} result={v} />)}
              </div>
            </div>
          )}

          {(reviewMut.isPending || review || reviewMut.isError) && (
            <div>
              {reviewMut.isPending && (
                <div className="card p-5 flex items-center gap-3 text-dark-400 text-sm">
                  <Loader2 className="h-4 w-4 animate-spin text-spider-400" />
                  IaC Advisor is reviewing the workspace bundle…
                </div>
              )}
              {reviewMut.isError && (
                <div className="card p-5 flex items-center gap-2 text-sm text-red-400 bg-red-900/20 border border-red-800/30">
                  <XCircle className="h-4 w-4 flex-shrink-0" />
                  {(reviewMut.error as Error)?.message ?? 'AI review failed — IaC Advisor agent may not be available.'}
                </div>
              )}
              {review && <ReviewPanel review={review} />}
            </div>
          )}

          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Code2 className="h-4 w-4 text-spider-400" /> Generated Files
                <span className="text-xs text-dark-400 font-normal">
                  {allFiles.length} file{allFiles.length !== 1 ? 's' : ''} across {Object.keys(result.files).length} categories
                </span>
              </h4>
              <button className="btn-ghost text-xs flex items-center gap-1.5" onClick={() => downloadAllFiles(result.bundle, result.provider)}>
                <Download className="h-3.5 w-3.5" /> Download all
              </button>
            </div>
            <div className="flex flex-wrap gap-2 mb-4">
              {Object.entries(result.files).map(([cat, catFiles]) => (
                <span key={cat} className="text-xs px-2 py-0.5 rounded-full bg-dark-700 text-dark-200">
                  <span className={CATEGORY_COLORS[cat] ?? 'text-dark-300'}>{CATEGORY_LABELS[cat] ?? cat}</span>
                  <span className="text-dark-400 ml-1">({catFiles.length})</span>
                </span>
              ))}
            </div>
            <div className="space-y-2">
              {allFiles.map(({ category, filename, content }) => (
                <FileCard key={`${category}/${filename}`} category={category} filename={filename} content={content} />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────

function WorkspaceIaCTab({ workspace, workspaceId, targets, scans }: WorkspaceIaCTabProps) {
  const containerRef              = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState('');
  const [renderErr, setRenderErr]   = useState<string | null>(null);
  const [loading, setLoading]       = useState(true);
  const [copied,  setCopied]        = useState(false);
  const [showSrc, setShowSrc] = useState(false);

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

      {/* ── Section 2: Workspace IaC Package Generator ── */}
      <div className="border-t border-dark-700 pt-6">
        <div className="flex items-center gap-2 mb-2">
          <Server className="h-5 w-5 text-spider-400" />
          <h2 className="text-lg font-semibold text-foreground">IaC Package Generator</h2>
        </div>
        <p className="text-sm text-dark-400 mb-5">
          Generates a single unified Terraform / Ansible / Docker / Packer bundle by running IaC
          generation across every selected scan in this workspace in parallel and merging the
          results. Includes deterministic validation and an optional LLM-powered security review.
        </p>

        {scans.length === 0 ? (
          <div className="card text-center py-10">
            <Server className="h-10 w-10 text-dark-600 mx-auto mb-3" />
            <p className="text-dark-400">No scans in this workspace yet.</p>
            <p className="text-dark-500 text-sm mt-1">Run a scan first, then come back to generate IaC.</p>
          </div>
        ) : (
          <WorkspaceIaCPanel key={workspaceId} scans={scans} />
        )}
      </div>
    </div>
  );
}

export default memo(WorkspaceIaCTab);
