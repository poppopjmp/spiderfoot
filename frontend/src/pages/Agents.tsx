import { useQuery, useMutation } from '@tanstack/react-query';
import { aiConfigApi, agentsApi } from '../lib/api';
import {
  Bot, Cpu, Sparkles, Zap, Loader2, RefreshCw,
  Shield, FileSearch, AlertTriangle, Clock, ChevronDown, ChevronUp,
  Star, BarChart3, Lock, Eye, Layers,
} from 'lucide-react';
import { useState } from 'react';
import { Toast, type ToastType } from '../components/ui';

/* ── Types ──────────────────────────────────────────────── */

interface Preset {
  id: string;
  name: string;
  description: string;
  estimated_time: string;
  module_count: string;
  stealth: string;
}

interface RecModule {
  module: string;
  enabled: boolean;
  priority: number;
  reason: string;
  category: string;
}

interface Recommendation {
  id: string;
  target: string;
  target_type: string;
  objective: string;
  stealth_level: string;
  confidence: number;
  modules: RecModule[];
  module_count: number;
  timing: Record<string, number>;
  scope: { max_depth: number; follow_redirects: boolean; include_subdomains: boolean; include_affiliates: boolean };
  estimates: { duration_minutes: number; events: number; api_calls: number };
  warnings: string[];
  notes: string[];
  created_at: string;
  engine_version: string;
}

interface AgentMetrics {
  agent_name: string;
  status: string;
  processed_total: number;
  errors_total: number;
  avg_processing_time_ms: number;
}

/* ── Agent icon/color mapping ─────────────────────────── */

const AGENT_META: Record<string, { icon: typeof Bot; label: string; color: string; description: string }> = {
  finding_validator: {
    icon: Shield, label: 'Finding Validator', color: 'text-green-400 bg-green-600/20',
    description: 'Validates and deduplicates scan findings, reducing false positives.',
  },
  credential_analyzer: {
    icon: Lock, label: 'Credential Analyzer', color: 'text-red-400 bg-red-600/20',
    description: 'Analyzes discovered credentials for severity and exposure risk.',
  },
  text_summarizer: {
    icon: FileSearch, label: 'Text Summarizer', color: 'text-blue-400 bg-blue-600/20',
    description: 'Generates concise summaries of large text payloads and documents.',
  },
  report_generator: {
    icon: Layers, label: 'Report Generator', color: 'text-purple-400 bg-purple-600/20',
    description: 'Creates executive and technical reports with AI-powered narratives.',
  },
  document_analyzer: {
    icon: Eye, label: 'Document Analyzer', color: 'text-orange-400 bg-orange-600/20',
    description: 'Extracts intelligence from uploaded documents and file metadata.',
  },
  threat_intel: {
    icon: AlertTriangle, label: 'Threat Intel Analyzer', color: 'text-yellow-400 bg-yellow-600/20',
    description: 'Correlates findings against threat intelligence databases and IOCs.',
  },
};

/* ── Component ────────────────────────────────────────── */

export default function AgentsPage() {
  const [target, setTarget] = useState('');
  const [targetType, setTargetType] = useState('domain');
  const [objective, setObjective] = useState('recon');
  const [stealth, setStealth] = useState('low');
  const [includeApiKeyModules, setIncludeApiKeyModules] = useState(true);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showModules, setShowModules] = useState(false);
  const [feedbackRating, setFeedbackRating] = useState(0);
  const [toast, setToast] = useState<{ type: ToastType; message: string } | null>(null);

  /* ── Queries ─────────────────────────────────────────── */

  const { data: agentStatus, isLoading: agentsLoading, refetch: refetchAgents } = useQuery({
    queryKey: ['agents-status'],
    queryFn: agentsApi.status,
    refetchInterval: 30000,
  });

  const { data: presetsData } = useQuery({
    queryKey: ['ai-presets'],
    queryFn: aiConfigApi.presets,
  });

  const { data: targetTypesData } = useQuery({
    queryKey: ['ai-target-types'],
    queryFn: aiConfigApi.targetTypes,
  });

  const { data: stealthData } = useQuery({
    queryKey: ['ai-stealth-levels'],
    queryFn: aiConfigApi.stealthLevels,
  });

  const presets: Preset[] = presetsData?.presets ?? [];
  const targetTypes = targetTypesData?.target_types ?? [];
  const stealthLevels = stealthData?.stealth_levels ?? [];
  const agents: [string, AgentMetrics][] = agentStatus?.agents
    ? Object.entries(agentStatus.agents)
    : [];

  /* ── Mutations ───────────────────────────────────────── */

  const recommendMutation = useMutation({
    mutationFn: (data: Parameters<typeof aiConfigApi.recommend>[0]) => aiConfigApi.recommend(data),
    onSuccess: (data) => {
      setRecommendation(data.recommendation);
      setFeedbackRating(0);
    },
    onError: () => setToast({ type: 'error', message: 'Failed to generate recommendation. Check target and settings.' }),
  });

  const feedbackMutation = useMutation({
    mutationFn: (data: Parameters<typeof aiConfigApi.feedback>[0]) => aiConfigApi.feedback(data),
    onSuccess: () => setToast({ type: 'success', message: 'Feedback submitted — thank you!' }),
    onError: () => setToast({ type: 'error', message: 'Failed to submit feedback.' }),
  });

  /* ── Helpers ──────────────────────────────────────────── */

  function handlePresetClick(preset: Preset) {
    setObjective(preset.id);
    setStealth(preset.stealth);
  }

  function handleRecommend() {
    if (!target.trim()) {
      setToast({ type: 'error', message: 'Enter a target.' });
      return;
    }
    recommendMutation.mutate({
      target: target.trim(),
      target_type: targetType,
      objective,
      stealth,
      include_api_key_modules: includeApiKeyModules,
    });
  }

  function handleFeedback(rating: number) {
    if (!recommendation) return;
    setFeedbackRating(rating);
    feedbackMutation.mutate({ recommendation_id: recommendation.id, rating });
  }

  /* ── Render ───────────────────────────────────────────── */

  return (
    <div>
      {toast && <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} />}

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-foreground">AI Agents & Scan Intelligence</h1>
        <span className="badge badge-info flex items-center gap-1">
          <Sparkles className="h-3 w-3" /> {agentStatus?.total_agents ?? 0} Agents Online
        </span>
      </div>

      {/* ── Live Agent Status ──────────────────────────── */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Live Agent Status</h2>
          <button className="text-dark-400 hover:text-foreground transition" onClick={() => refetchAgents()}>
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>

        {agentsLoading ? (
          <div className="flex items-center gap-2 text-dark-400 py-8 justify-center">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading agents…
          </div>
        ) : agents.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map(([key, a]) => {
              const meta = AGENT_META[key] ?? { icon: Bot, label: key, color: 'text-dark-400 bg-dark-700', description: '' };
              const Icon = meta.icon;
              return (
                <div key={key} className="card hover:border-spider-600/40 border border-transparent transition">
                  <div className="flex items-center gap-3 mb-3">
                    <div className={`p-2 rounded-lg ${meta.color.split(' ')[1]}`}>
                      <Icon className={`h-5 w-5 ${meta.color.split(' ')[0]}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-foreground text-sm">{meta.label}</h3>
                      <span className={`text-xs ${a.status === 'idle' ? 'text-green-400' : 'text-yellow-400'}`}>
                        {a.status}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-dark-400 mb-3">{meta.description}</p>
                  <div className="flex items-center gap-4 text-xs text-dark-500">
                    <span title="Processed">
                      <BarChart3 className="h-3 w-3 inline mr-1" />{a.processed_total}
                    </span>
                    <span title="Errors" className={a.errors_total > 0 ? 'text-red-400' : ''}>
                      <AlertTriangle className="h-3 w-3 inline mr-1" />{a.errors_total}
                    </span>
                    <span title="Avg time">
                      <Clock className="h-3 w-3 inline mr-1" />{a.avg_processing_time_ms.toFixed(0)}ms
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="card text-center py-8">
            <Bot className="h-12 w-12 text-dark-600 mx-auto mb-3" />
            <p className="text-dark-400">No agents responding.</p>
            <p className="text-dark-500 text-sm mt-1">The agents service may be starting up.</p>
          </div>
        )}
      </div>

      {/* ── Scan Presets ───────────────────────────────── */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-foreground mb-4">Scan Presets</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {presets.map((p) => (
            <button
              key={p.id}
              onClick={() => handlePresetClick(p)}
              className={`card text-left transition hover:border-spider-600/50 border ${
                objective === p.id ? 'border-spider-500 bg-spider-600/10' : 'border-transparent'
              }`}
            >
              <h3 className="font-semibold text-foreground text-sm mb-1">{p.name}</h3>
              <p className="text-xs text-dark-400 mb-2 line-clamp-2">{p.description}</p>
              <div className="flex items-center gap-3 text-[10px] text-dark-500">
                <span><Clock className="h-3 w-3 inline mr-0.5" />{p.estimated_time}</span>
                <span><Cpu className="h-3 w-3 inline mr-0.5" />{p.module_count} modules</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* ── AI Recommendation Form ─────────────────────── */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-foreground mb-4">AI Scan Recommendation</h2>
        <div className="card">
          <p className="text-sm text-dark-300 mb-4">
            Get an AI-powered module selection and scan configuration optimized for your target and objective.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            {/* Target */}
            <div>
              <label className="block text-sm text-dark-300 mb-1">Target *</label>
              <input
                className="input-field w-full"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="e.g. example.com, 192.168.1.0/24, user@email.com"
              />
            </div>

            {/* Target Type */}
            <div>
              <label className="block text-sm text-dark-300 mb-1">Target Type</label>
              <select className="input-field w-full" value={targetType} onChange={(e) => setTargetType(e.target.value)}>
                {targetTypes.length > 0
                  ? targetTypes.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)
                  : <option value="domain">Domain</option>}
              </select>
            </div>

            {/* Objective */}
            <div>
              <label className="block text-sm text-dark-300 mb-1">Objective</label>
              <select className="input-field w-full" value={objective} onChange={(e) => setObjective(e.target.value)}>
                {presets.length > 0
                  ? presets.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)
                  : <option value="recon">Reconnaissance</option>}
              </select>
            </div>

            {/* Stealth */}
            <div>
              <label className="block text-sm text-dark-300 mb-1">Stealth Level</label>
              <select className="input-field w-full" value={stealth} onChange={(e) => setStealth(e.target.value)}>
                {stealthLevels.length > 0
                  ? stealthLevels.map((s) => (
                      <option key={s.id} value={s.id}>{s.name} — {s.description}</option>
                    ))
                  : <option value="low">Low</option>}
              </select>
            </div>
          </div>

          {/* Advanced toggle */}
          <button
            className="text-sm text-dark-400 hover:text-foreground flex items-center gap-1 mb-4"
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            Advanced Options
          </button>

          {showAdvanced && (
            <div className="mb-4 p-3 bg-dark-700/30 rounded-lg space-y-3">
              <label className="flex items-center gap-2 text-sm text-dark-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeApiKeyModules}
                  onChange={(e) => setIncludeApiKeyModules(e.target.checked)}
                  className="rounded border-dark-600"
                />
                Include modules requiring API keys
              </label>
            </div>
          )}

          <button
            className="btn-primary flex items-center gap-2"
            disabled={!target.trim() || recommendMutation.isPending}
            onClick={handleRecommend}
          >
            {recommendMutation.isPending ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Analyzing…</>
            ) : (
              <><Zap className="h-4 w-4" /> Get Recommendation</>
            )}
          </button>

          {recommendMutation.isError && (
            <p className="text-red-400 text-sm mt-2">Failed to generate recommendation. Check target and settings.</p>
          )}
        </div>
      </div>

      {/* ── Recommendation Result ──────────────────────── */}
      {recommendation && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-foreground mb-4">Recommendation Result</h2>
          <div className="card border border-spider-600/30">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-foreground font-semibold flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-spider-400" />
                  {recommendation.target}
                </h3>
                <p className="text-xs text-dark-400 mt-1">
                  ID: {recommendation.id} · Objective: {recommendation.objective} ·
                  Stealth: {recommendation.stealth_level} · Engine: {recommendation.engine_version}
                </p>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-spider-400">{(recommendation.confidence * 100).toFixed(0)}%</div>
                <div className="text-[10px] text-dark-500">Confidence</div>
              </div>
            </div>

            {/* Estimates */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              <div className="bg-dark-700/50 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-foreground">{recommendation.module_count}</div>
                <div className="text-[10px] text-dark-500">Modules</div>
              </div>
              <div className="bg-dark-700/50 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-foreground">{recommendation.estimates.duration_minutes}m</div>
                <div className="text-[10px] text-dark-500">Est. Duration</div>
              </div>
              <div className="bg-dark-700/50 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-foreground">{recommendation.estimates.events.toLocaleString()}</div>
                <div className="text-[10px] text-dark-500">Est. Events</div>
              </div>
              <div className="bg-dark-700/50 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-foreground">{recommendation.estimates.api_calls}</div>
                <div className="text-[10px] text-dark-500">API Calls</div>
              </div>
            </div>

            {/* Scope */}
            <div className="flex flex-wrap gap-2 mb-4">
              <span className="badge badge-info text-xs">Depth: {recommendation.scope.max_depth}</span>
              {recommendation.scope.follow_redirects && <span className="badge badge-info text-xs">Follow Redirects</span>}
              {recommendation.scope.include_subdomains && <span className="badge badge-info text-xs">Subdomains</span>}
              {recommendation.scope.include_affiliates && <span className="badge badge-info text-xs">Affiliates</span>}
            </div>

            {/* Warnings */}
            {recommendation.warnings.length > 0 && (
              <div className="mb-4 p-3 bg-yellow-600/10 border border-yellow-600/30 rounded-lg">
                <p className="text-yellow-400 text-sm font-medium mb-1 flex items-center gap-1">
                  <AlertTriangle className="h-4 w-4" /> Warnings
                </p>
                <ul className="text-xs text-yellow-300/80 space-y-1">
                  {recommendation.warnings.map((w, i) => <li key={i}>• {w}</li>)}
                </ul>
              </div>
            )}

            {/* Notes */}
            {recommendation.notes.length > 0 && (
              <div className="mb-4 p-3 bg-dark-700/30 rounded-lg">
                <p className="text-dark-300 text-sm font-medium mb-1">Notes</p>
                <ul className="text-xs text-dark-400 space-y-1">
                  {recommendation.notes.map((n, i) => <li key={i}>• {n}</li>)}
                </ul>
              </div>
            )}

            {/* Module list toggle */}
            <button
              className="text-sm text-dark-400 hover:text-foreground flex items-center gap-1 mb-3"
              onClick={() => setShowModules(!showModules)}
            >
              {showModules ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              {recommendation.module_count} Recommended Modules
            </button>

            {showModules && (
              <div className="space-y-2 max-h-80 overflow-y-auto mb-4">
                {recommendation.modules
                  .sort((a, b) => b.priority - a.priority)
                  .map((m) => (
                    <div
                      key={m.module}
                      className="flex items-center justify-between p-2 bg-dark-700/40 rounded-lg"
                    >
                      <div className="flex-1 min-w-0">
                        <span className="text-sm text-foreground font-mono">{m.module}</span>
                        <p className="text-[10px] text-dark-400 truncate">{m.reason}</p>
                      </div>
                      <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                        <span className="badge text-[10px] bg-dark-600 text-dark-300">{m.category}</span>
                        <span className="text-xs text-dark-500">P{m.priority}</span>
                      </div>
                    </div>
                  ))}
              </div>
            )}

            {/* Timing */}
            {recommendation.timing && (
              <div className="mb-4">
                <p className="text-sm text-dark-400 mb-2">Timing Config</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(recommendation.timing).map(([k, v]) => (
                    <span key={k} className="text-[10px] bg-dark-700 text-dark-400 px-2 py-1 rounded font-mono">
                      {k}: {v}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Feedback */}
            <div className="flex items-center gap-3 pt-3 border-t border-dark-700/50">
              <span className="text-sm text-dark-400">Rate this recommendation:</span>
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map((s) => (
                  <button
                    key={s}
                    onClick={() => handleFeedback(s)}
                    disabled={feedbackMutation.isPending}
                    className="transition"
                  >
                    <Star
                      className={`h-5 w-5 ${
                        s <= feedbackRating
                          ? 'text-yellow-400 fill-yellow-400'
                          : 'text-dark-600 hover:text-yellow-400/50'
                      }`}
                    />
                  </button>
                ))}
              </div>
              {feedbackRating > 0 && (
                <span className="text-xs text-green-400">Submitted!</span>
              )}
            </div>

            {/* Raw JSON toggle */}
            <details className="mt-3">
              <summary className="text-xs text-dark-500 cursor-pointer hover:text-dark-300">
                Raw JSON
              </summary>
              <pre className="mt-2 p-3 bg-dark-800 rounded text-xs text-dark-300 overflow-auto max-h-40">
                {JSON.stringify(recommendation, null, 2)}
              </pre>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}
