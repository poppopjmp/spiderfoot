import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scanApi, type ScanCorrelation } from '../../lib/api';
import { AlertTriangle, Shield, Info, Loader2, RefreshCw } from 'lucide-react';
import { TableSkeleton, EmptyState, Expandable } from '../ui';

export default function CorrelationsTab({ scanId }: { scanId: string }) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['scan-correlations', scanId],
    queryFn: () => scanApi.correlations(scanId),
  });

  const runMut = useMutation({
    mutationFn: () => scanApi.runCorrelations(scanId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scan-correlations', scanId] }),
  });

  const correlations: ScanCorrelation[] = data?.correlations ?? [];

  const riskIcon = (risk: string) => {
    const r = risk?.toLowerCase();
    if (r === 'high' || r === 'critical') return <AlertTriangle className="h-4 w-4 corr-text-critical" />;
    if (r === 'medium') return <Info className="h-4 w-4 corr-text-medium" />;
    if (r === 'low') return <Shield className="h-4 w-4 corr-text-low" />;
    return <Info className="h-4 w-4 corr-text-info" />;
  };

  const riskBadge = (risk: string) => {
    const r = risk?.toLowerCase();
    if (r === 'high' || r === 'critical') return 'badge-critical';
    if (r === 'medium') return 'badge-medium';
    if (r === 'low') return 'badge-low';
    return 'badge-info';
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-dark-400">{correlations.length} correlation(s) found</p>
        <button
          className="btn-secondary"
          onClick={() => runMut.mutate()}
          disabled={runMut.isPending}
        >
          {runMut.isPending ? (
            <><Loader2 className="h-4 w-4 animate-spin" /> Running...</>
          ) : (
            <><RefreshCw className="h-4 w-4" /> Run Correlations</>
          )}
        </button>
      </div>

      {isLoading ? (
        <TableSkeleton rows={5} cols={4} />
      ) : correlations.length > 0 ? (
        <div className="space-y-3">
          {correlations.map((c, i) => (
            <Expandable
              key={c.id || i}
              title={c.rule_name || c.title}
              badge={<span className={`badge ${riskBadge(c.rule_risk)}`}>{c.rule_risk}</span>}
              className="animate-fade-in"
            >
              <div className="space-y-3 pt-2">
                <div className="flex items-start gap-2">
                  {riskIcon(c.rule_risk)}
                  <div>
                    <p className="text-sm text-dark-200">{c.rule_descr}</p>
                    <p className="text-xs text-dark-500 mt-1">Rule: {c.rule_id} · Events: {c.event_count}</p>
                    {c.rule_logic && (
                      <pre className="text-xs text-dark-500 mt-2 bg-dark-900/50 rounded p-2 overflow-x-auto">{c.rule_logic}</pre>
                    )}
                  </div>
                </div>
              </div>
            </Expandable>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Shield}
          title="No correlations yet"
          description="Click 'Run Correlations' to analyze the scan data for patterns and insights."
          action={
            <button className="btn-primary" onClick={() => runMut.mutate()} disabled={runMut.isPending}>
              <RefreshCw className="h-4 w-4" /> Run Now
            </button>
          }
        />
      )}
    </div>
  );
}
