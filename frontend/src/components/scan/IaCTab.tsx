import { memo, useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  iacApi,
  type IaCRequest, type IaCResponse, type IaCValidationResult,
  type IaCReviewData, type IaCReviewIssue,
} from '../../lib/api';
import {
  Server, CheckCircle2, XCircle, AlertTriangle, Download,
  ChevronDown, ChevronRight, Loader2, Code2, RefreshCw,
  Bot, Shield, ThumbsUp,
} from 'lucide-react';

// ── Helpers ──────────────────────────────────────────────────

const PROVIDERS = [
  { value: 'aws', label: 'Amazon Web Services (AWS)' },
  { value: 'azure', label: 'Microsoft Azure' },
  { value: 'gcp', label: 'Google Cloud Platform (GCP)' },
  { value: 'digitalocean', label: 'DigitalOcean' },
  { value: 'vmware', label: 'VMware vSphere' },
] as const;

type Provider = (typeof PROVIDERS)[number]['value'];

const CATEGORY_LABELS: Record<string, string> = {
  terraform: 'Terraform',
  ansible: 'Ansible',
  docker: 'Docker Compose',
  packer: 'Packer',
  docs: 'Documentation',
};

const CATEGORY_COLORS: Record<string, string> = {
  terraform: 'text-purple-400',
  ansible: 'text-red-400',
  docker: 'text-blue-400',
  packer: 'text-yellow-400',
  docs: 'text-dark-300',
};

function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadAllFiles(bundle: IaCResponse['bundle'], provider: string) {
  // Build a simple zip-like text archive (concatenated files with headers)
  let archive = `# SpiderFoot IaC Bundle — Provider: ${provider}\n`;
  archive += `# Generated: ${new Date().toISOString()}\n\n`;
  for (const [category, files] of Object.entries(bundle)) {
    if (!files || typeof files !== 'object') continue;
    for (const [filename, content] of Object.entries(files)) {
      archive += `${'='.repeat(60)}\n# ${category}/${filename}\n${'='.repeat(60)}\n`;
      archive += content + '\n\n';
    }
  }
  downloadText(`spiderfoot-iac-${provider}-${Date.now()}.txt`, archive);
}

// ── Sub-components ────────────────────────────────────────────

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <div
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-9 h-5 rounded-full transition-colors ${
          checked ? 'bg-spider-500' : 'bg-dark-700'
        } cursor-pointer`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
            checked ? 'translate-x-4' : 'translate-x-0'
          }`}
        />
      </div>
      <span className="text-sm text-dark-200">{label}</span>
    </label>
  );
}

function ValidationBadge({ result }: { result: IaCValidationResult }) {
  return (
    <div className={`flex items-start gap-2 text-xs rounded-lg px-3 py-2 ${
      result.valid ? 'bg-green-900/20 border border-green-800/30' : 'bg-red-900/20 border border-red-800/30'
    }`}>
      {result.valid
        ? <CheckCircle2 className="h-3.5 w-3.5 text-green-400 mt-0.5 flex-shrink-0" />
        : <XCircle className="h-3.5 w-3.5 text-red-400 mt-0.5 flex-shrink-0" />
      }
      <div>
        <span className={`font-mono font-medium ${result.valid ? 'text-green-300' : 'text-red-300'}`}>
          {result.artifact_type}/{result.file_name}
        </span>
        {result.errors.length > 0 && (
          <ul className="mt-1 space-y-0.5">
            {result.errors.map((e, i) => (
              <li key={i} className="text-red-400">{e}</li>
            ))}
          </ul>
        )}
        {result.warnings.length > 0 && (
          <ul className="mt-1 space-y-0.5">
            {result.warnings.map((w, i) => (
              <li key={i} className="text-yellow-400 flex gap-1">
                <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />{w}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── AI Review helpers ────────────────────────────────────────

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
  const color = score >= 80 ? 'text-green-400' : score >= 50 ? 'text-yellow-400' : 'text-red-400';
  const ringColor = score >= 80 ? 'stroke-green-500' : score >= 50 ? 'stroke-yellow-500' : 'stroke-red-500';
  const r = 28;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
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
      <button
        className={`w-full flex items-center gap-2 px-3 py-2.5 text-sm text-left ${s.bg} hover:brightness-110 transition-all`}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <ChevronDown className="h-3.5 w-3.5 text-dark-400 flex-shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 text-dark-400 flex-shrink-0" />}
        <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${s.bg} ${s.text} border ${s.border} flex-shrink-0`}>
          {s.label}
        </span>
        <span className="font-mono text-xs text-dark-400 flex-shrink-0">{issue.file}</span>
        <span className={`text-xs font-medium ${s.text} flex-1 truncate`}>{issue.description}</span>
        <span className="text-xs text-dark-500 capitalize flex-shrink-0">{issue.category.replace('_', ' ')}</span>
      </button>
      {open && (
        <div className={`px-4 py-3 text-xs space-y-2 ${s.bg} border-t ${s.border}`}>
          <p className="text-dark-200">{issue.description}</p>
          <div className="mt-2">
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
      {/* Header */}
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

      {/* Summary */}
      {review.summary && (
        <p className="text-sm text-dark-300 leading-relaxed">{review.summary}</p>
      )}

      {/* Issue counters */}
      {review.issues.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {[
            { key: 'critical', label: 'Critical', color: 'text-red-400 bg-red-900/20 border-red-800/30' },
            { key: 'high',     label: 'High',     color: 'text-orange-400 bg-orange-900/20 border-orange-800/30' },
            { key: 'medium',   label: 'Medium',   color: 'text-yellow-400 bg-yellow-900/20 border-yellow-800/30' },
            { key: 'low',      label: 'Low',      color: 'text-blue-400 bg-blue-900/20 border-blue-800/30' },
          ].map(({ key, label, color }) => {
            const cnt = review.issues.filter((i) => i.severity === key).length;
            if (!cnt) return null;
            return (
              <span key={key} className={`text-xs font-semibold px-2 py-1 rounded-full border ${color}`}>
                {cnt} {label}
              </span>
            );
          })}
        </div>
      )}

      {/* Issues */}
      {review.issues.length > 0 && (
        <div className="space-y-2">
          {review.issues.map((issue, i) => <IssueCard key={i} issue={issue} />)}
        </div>
      )}

      {/* Positive findings */}
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

      {/* Compliance notes */}
      {review.compliance_notes && (
        <div className="flex items-start gap-2 text-xs text-dark-400 bg-dark-800 rounded-lg px-3 py-2">
          <Shield className="h-3.5 w-3.5 text-spider-400 mt-0.5 flex-shrink-0" />
          <span>{review.compliance_notes}</span>
        </div>
      )}
    </div>
  );
}

// ── File card ─────────────────────────────────────────────────

function FileCard({ category, filename, content }: { category: string; filename: string; content: string }) {
  const [open, setOpen] = useState(false);
  const color = CATEGORY_COLORS[category] ?? 'text-dark-300';

  return (
    <div className="border border-dark-700 rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-3 py-2 text-sm bg-dark-800 hover:bg-dark-750 transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="flex items-center gap-2">
          {open ? <ChevronDown className="h-4 w-4 text-dark-400" /> : <ChevronRight className="h-4 w-4 text-dark-400" />}
          <span className={`font-mono text-xs font-medium ${color}`}>{category}/</span>
          <span className="font-mono text-xs text-dark-200">{filename}</span>
        </span>
        <button
          className="text-dark-400 hover:text-dark-100 transition-colors p-1 rounded"
          title={`Download ${filename}`}
          onClick={(e) => { e.stopPropagation(); downloadText(filename, content); }}
        >
          <Download className="h-3.5 w-3.5" />
        </button>
      </button>
      {open && (
        <pre className="p-3 text-xs text-dark-200 bg-dark-900 overflow-x-auto max-h-96 font-mono whitespace-pre leading-relaxed">
          {content}
        </pre>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────

interface IaCTabProps {
  scanId: string;
  scanTarget?: string;
}

function IaCTab({ scanId, scanTarget }: IaCTabProps) {
  const [provider, setProvider] = useState<Provider>('aws');
  const [includeTerraform, setIncludeTerraform] = useState(true);
  const [includeAnsible, setIncludeAnsible] = useState(true);
  const [includeDocker, setIncludeDocker] = useState(true);
  const [includePacker, setIncludePacker] = useState(false);
  const [runValidate, setRunValidate] = useState(true);
  const [result, setResult] = useState<IaCResponse | null>(null);
  const [review, setReview] = useState<IaCReviewData | null>(null);

  const generate = useMutation({
    mutationFn: (req: IaCRequest) => iacApi.generate(scanId, req),
    onSuccess: (data) => { setResult(data); setReview(null); },
  });

  const reviewMut = useMutation({
    mutationFn: (res: IaCResponse) => iacApi.review({
      scan_id: scanId,
      target: scanTarget ?? '',
      provider: res.provider,
      bundle: res.bundle,
      files: res.files,
    }),
    onSuccess: (data) => setReview(data.data),
  });

  const handleGenerate = useCallback(() => {
    generate.mutate({
      provider,
      include_terraform: includeTerraform,
      include_ansible: includeAnsible,
      include_docker: includeDocker,
      include_packer: includePacker,
      validate: runValidate,
    });
  }, [generate, provider, includeTerraform, includeAnsible, includeDocker, includePacker, runValidate]);

  // Flatten all files for rendering
  const allFiles: Array<{ category: string; filename: string; content: string }> = result
    ? Object.entries(result.bundle).flatMap(([category, files]) =>
        Object.entries(files ?? {}).map(([filename, content]) => ({ category, filename, content }))
      )
    : [];

  return (
    <div className="space-y-6">
      {/* Config Panel */}
      <div className="card p-5 space-y-5">
        <div className="flex items-center gap-2 mb-1">
          <Server className="h-4 w-4 text-spider-400" />
          <h3 className="font-semibold text-foreground">Infrastructure-as-Code Generator</h3>
        </div>
        <p className="text-sm text-dark-400">
          Generates Terraform, Ansible, Docker Compose, and Packer configurations that replicate
          the scanned target's discovered infrastructure.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {/* Provider selector */}
          <div>
            <label className="block text-xs font-medium text-dark-300 mb-1.5 uppercase tracking-wide">
              Cloud Provider
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as Provider)}
              className="input w-full text-sm"
            >
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>

          {/* Artifact toggles */}
          <div>
            <label className="block text-xs font-medium text-dark-300 mb-1.5 uppercase tracking-wide">
              Artifacts
            </label>
            <div className="space-y-2">
              <Toggle label="Terraform" checked={includeTerraform} onChange={setIncludeTerraform} />
              <Toggle label="Ansible Playbook" checked={includeAnsible} onChange={setIncludeAnsible} />
              <Toggle label="Docker Compose" checked={includeDocker} onChange={setIncludeDocker} />
              <Toggle label="Packer" checked={includePacker} onChange={setIncludePacker} />
              <Toggle label="Validate output" checked={runValidate} onChange={setRunValidate} />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button
            className="btn-primary flex items-center gap-2"
            onClick={handleGenerate}
            disabled={generate.isPending}
          >
            {generate.isPending
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <Code2 className="h-4 w-4" />
            }
            {generate.isPending ? 'Generating…' : 'Generate IaC'}
          </button>
          {result && (
            <>
              <button
                className="btn-secondary flex items-center gap-2 text-sm"
                onClick={handleGenerate}
                disabled={generate.isPending}
              >
                <RefreshCw className="h-4 w-4" /> Regenerate
              </button>
              <button
                className="btn-secondary flex items-center gap-2 text-sm"
                onClick={() => reviewMut.mutate(result)}
                disabled={reviewMut.isPending}
              >
                {reviewMut.isPending
                  ? <Loader2 className="h-4 w-4 animate-spin" />
                  : <Bot className="h-4 w-4" />
                }
                AI Review
              </button>
            </>
          )}
        </div>

        {generate.isError && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-900/20 border border-red-800/30 rounded-lg px-3 py-2">
            <XCircle className="h-4 w-4 flex-shrink-0" />
            {(generate.error as Error)?.message ?? 'IaC generation failed. Ensure the scan has finished and contains events.'}
          </div>
        )}
      </div>

      {/* No-events message */}
      {result?.message && !result.bundle && (
        <div className="card p-5 flex items-center gap-3 text-dark-400 text-sm">
          <AlertTriangle className="h-5 w-5 text-yellow-500 flex-shrink-0" />
          {result.message}
        </div>
      )}

      {/* Results */}
      {result && Object.keys(result.bundle ?? {}).length > 0 && (
        <>
          {/* Profile summary */}
          <div className="card p-5">
            <h4 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
              <Server className="h-4 w-4 text-spider-400" /> Target Profile
              <span className="ml-auto text-xs text-dark-400 font-normal capitalize">{result.provider}</span>
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {[
                { label: 'IP Addresses', value: result.profile_summary.ip_count },
                { label: 'Open Ports', value: result.profile_summary.port_count },
                { label: 'Services', value: result.profile_summary.service_count },
                { label: 'Web Server', value: result.profile_summary.web_server ?? '—' },
                { label: 'OS Detected', value: result.profile_summary.os_detected ?? '—' },
              ].map(({ label, value }) => (
                <div key={label} className="bg-dark-800 rounded-lg p-3 text-center">
                  <div className="text-lg font-bold text-foreground">{value}</div>
                  <div className="text-xs text-dark-400 mt-0.5">{label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Validation results */}
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
                  result.all_valid
                    ? 'bg-green-900/40 text-green-300'
                    : 'bg-red-900/40 text-red-300'
                }`}>
                  {result.validation.filter((v) => v.valid).length}/{result.validation.length} passed
                </span>
              </div>
              <div className="space-y-2">
                {result.validation.map((v, i) => (
                  <ValidationBadge key={i} result={v} />
                ))}
              </div>
            </div>
          )}

          {/* AI Review Panel */}
          {(reviewMut.isPending || review || reviewMut.isError) && (
            <div>
              {reviewMut.isPending && (
                <div className="card p-5 flex items-center gap-3 text-dark-400 text-sm">
                  <Loader2 className="h-4 w-4 animate-spin text-spider-400" />
                  IaC Advisor is reviewing the bundle…
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

          {/* File browser */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Code2 className="h-4 w-4 text-spider-400" /> Generated Files
                <span className="text-xs text-dark-400 font-normal">
                  {allFiles.length} file{allFiles.length !== 1 ? 's' : ''} across{' '}
                  {Object.keys(result.files).length} categories
                </span>
              </h4>
              <button
                className="btn-ghost text-xs flex items-center gap-1.5"
                onClick={() => downloadAllFiles(result.bundle, result.provider)}
              >
                <Download className="h-3.5 w-3.5" /> Download all
              </button>
            </div>

            {/* Category summary pills */}
            <div className="flex flex-wrap gap-2 mb-4">
              {Object.entries(result.files).map(([cat, files]) => (
                <span
                  key={cat}
                  className="text-xs px-2 py-0.5 rounded-full bg-dark-700 text-dark-200"
                >
                  <span className={CATEGORY_COLORS[cat] ?? 'text-dark-300'}>
                    {CATEGORY_LABELS[cat] ?? cat}
                  </span>
                  <span className="text-dark-400 ml-1">({files.length})</span>
                </span>
              ))}
            </div>

            {/* Expandable file list */}
            <div className="space-y-2">
              {allFiles.map(({ category, filename, content }) => (
                <FileCard
                  key={`${category}/${filename}`}
                  category={category}
                  filename={filename}
                  content={content}
                />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default memo(IaCTab);
