import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { agentApi, type AgentMetrics } from '../lib/api';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import {
  Bot, Activity, AlertCircle, CheckCircle2,
  Clock, Zap, RefreshCw, XCircle,
} from 'lucide-react';
import {
  PageHeader, StatCard, EmptyState, Skeleton,
} from '../components/ui';

// ── Helpers ───────────────────────────────────────────────────

function displayName(snakeKey: string): string {
  return snakeKey
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function AgentStatusBadge({ healthy }: { healthy: boolean }) {
  return healthy ? (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-500/20 text-green-400 border border-green-500/30">
      <CheckCircle2 className="h-3 w-3" />
      Active
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-dark-700 text-dark-400 border border-dark-600">
      <XCircle className="h-3 w-3" />
      Idle
    </span>
  );
}

// ── Agent Card ────────────────────────────────────────────────

function AgentCard({ name, metrics }: { name: string; metrics: AgentMetrics }) {
  const errorRate = metrics.processed_total > 0
    ? ((metrics.errors_total / metrics.processed_total) * 100).toFixed(1)
    : '0.0';
  const hasErrors = metrics.errors_total > 0;
  const isActive = metrics.processed_total > 0;

  return (
    <div className="bg-dark-800 border border-dark-700 rounded-xl p-5 flex flex-col gap-4 hover:border-dark-600 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-10 w-10 rounded-lg bg-spider-600/20 border border-spider-600/30 flex items-center justify-center flex-shrink-0">
            <Bot className="h-5 w-5 text-spider-400" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-foreground truncate">{displayName(name)}</h3>
            <p className="text-xs text-dark-400 truncate">{name}</p>
          </div>
        </div>
        <AgentStatusBadge healthy={isActive} />
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-dark-900/60 rounded-lg p-3 text-center">
          <p className="text-xl font-bold text-foreground">{metrics.processed_total.toLocaleString()}</p>
          <p className="text-xs text-dark-400 mt-0.5">Processed</p>
        </div>
        <div className={`rounded-lg p-3 text-center ${hasErrors ? 'bg-red-900/20 border border-red-900/30' : 'bg-dark-900/60'}`}>
          <p className={`text-xl font-bold ${hasErrors ? 'text-red-400' : 'text-foreground'}`}>{metrics.errors_total}</p>
          <p className="text-xs text-dark-400 mt-0.5">Errors</p>
        </div>
        <div className="bg-dark-900/60 rounded-lg p-3 text-center">
          <p className="text-xl font-bold text-foreground">
            {metrics.avg_processing_time_ms > 0 ? metrics.avg_processing_time_ms.toFixed(0) : '—'}
          </p>
          <p className="text-xs text-dark-400 mt-0.5">Avg ms</p>
        </div>
      </div>

      {/* Error rate bar */}
      {metrics.processed_total > 0 && (
        <div>
          <div className="flex justify-between text-xs text-dark-400 mb-1">
            <span>Error rate</span>
            <span className={hasErrors ? 'text-red-400' : 'text-green-400'}>{errorRate}%</span>
          </div>
          <div className="h-1.5 bg-dark-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${hasErrors ? 'bg-red-500' : 'bg-green-500'}`}
              style={{ width: `${Math.min(parseFloat(errorRate), 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Last processed */}
      {metrics.last_processed && (
        <p className="text-xs text-dark-500 flex items-center gap-1.5">
          <Clock className="h-3 w-3" />
          Last: {new Date(metrics.last_processed).toLocaleString()}
        </p>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────

export default function AgentsPage() {
  useDocumentTitle('AI Agents');
  const [autoRefresh, setAutoRefresh] = useState(false);

  const {
    data: statusData,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['agents-status'],
    queryFn: ({ signal }) => agentApi.status(signal),
    refetchInterval: autoRefresh ? 5000 : false,
    retry: 1,
  });

  const agents = statusData?.agents ?? {};
  const totalAgents = statusData?.total_agents ?? 0;
  const agentEntries = Object.entries(agents);

  const totalProcessed = agentEntries.reduce((sum, [, m]) => sum + m.processed_total, 0);
  const totalErrors = agentEntries.reduce((sum, [, m]) => sum + m.errors_total, 0);
  const avgLatency = agentEntries.length > 0
    ? agentEntries.reduce((sum, [, m]) => sum + m.avg_processing_time_ms, 0) / agentEntries.length
    : 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="AI Agents"
        subtitle="Real-time status and metrics for all loaded SpiderFoot AI agents."
      >
        <label className="flex items-center gap-2 text-sm text-dark-300 cursor-pointer select-none">
          <input
            type="checkbox"
            className="rounded border-dark-600 bg-dark-700 text-spider-600 focus:ring-spider-500"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
          />
          Auto-refresh
        </label>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg bg-dark-700 hover:bg-dark-600 text-dark-200 border border-dark-600 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </PageHeader>

      {/* Stats summary */}
      {!isLoading && !isError && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard
            label="Active Agents"
            value={totalAgents}
            icon={Bot}
            color="text-spider-400"
          />
          <StatCard
            label="Events Processed"
            value={totalProcessed.toLocaleString()}
            icon={Activity}
            color="text-blue-400"
          />
          <StatCard
            label="Total Errors"
            value={totalErrors}
            icon={AlertCircle}
            color={totalErrors > 0 ? 'text-red-400' : 'text-green-400'}
          />
          <StatCard
            label="Avg Latency"
            value={avgLatency > 0 ? `${avgLatency.toFixed(0)} ms` : '—'}
            icon={Zap}
            color="text-yellow-400"
          />
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-dark-800 border border-dark-700 rounded-xl p-5 space-y-4">
              <Skeleton className="h-10 w-3/4" />
              <div className="grid grid-cols-3 gap-3">
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
              </div>
            </div>
          ))}
        </div>
      ) : isError ? (
        <EmptyState
          icon={AlertCircle}
          title="Agents service unavailable"
          description={
            error instanceof Error
              ? error.message
              : 'Could not reach the agents service. It may not be enabled or configured.'
          }
        />
      ) : agentEntries.length === 0 ? (
        <EmptyState
          icon={Bot}
          title="No agents loaded"
          description="No AI agents are currently active. Agents require an LLM to be configured (SF_LLM_MODEL / SF_OPENAI_API_KEY)."
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {agentEntries.map(([name, metrics]) => (
            <AgentCard key={name} name={name} metrics={metrics} />
          ))}
        </div>
      )}
    </div>
  );
}
