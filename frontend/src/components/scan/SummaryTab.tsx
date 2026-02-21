import { memo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { scanApi, formatEpoch, formatDuration, type Scan, type EventSummaryDetail } from '../../lib/api';
import { Skeleton, TableSkeleton } from '../ui';
import MiniStat from './MiniStat';

function SummaryTab({ scanId, scan }: { scanId: string; scan?: Scan }) {
  const { data: summaryData, isLoading } = useQuery({
    queryKey: ['scan-summary', scanId],
    queryFn: () => scanApi.summary(scanId),
    enabled: !!scanId,
  });

  const { data: corrData } = useQuery({
    queryKey: ['scan-correlations-summary', scanId],
    queryFn: () => scanApi.correlationsSummary(scanId, 'risk'),
    enabled: !!scanId,
  });

  const details: EventSummaryDetail[] = summaryData?.details ?? [];
  const sorted = [...details].sort((a, b) => b.total - a.total);
  const totalEvents = sorted.reduce((sum, d) => sum + d.total, 0);

  /* Correlations summary */
  const corrRaw = corrData?.summary ?? [];
  const corrBreakdown: Record<string, number> = {};
  if (Array.isArray(corrRaw)) {
    corrRaw.forEach((item: { risk?: string; total?: number }) => {
      if (item.risk) corrBreakdown[item.risk] = item.total ?? 0;
    });
  } else if (typeof corrRaw === 'object') {
    Object.assign(corrBreakdown, corrRaw);
  }
  const corrTotal = Object.values(corrBreakdown).reduce((s, v) => s + v, 0);

  /* Simple doughnut - top 8 categories */
  const top8 = sorted.slice(0, 8);
  const colors = [
    '#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6',
    '#8b5cf6', '#ef4444', '#06b6d4',
  ];

  return (
    <div className="space-y-6">
      {/* Stat row */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <MiniStat label="Data Types" value={summaryData?.total_types ?? 0} />
        <MiniStat label="Total Events" value={totalEvents} />
        <MiniStat label="Unique Values" value={sorted.reduce((s, d) => s + d.unique_total, 0)} />
        <MiniStat label="Correlations" value={corrTotal} />
        <MiniStat label="Duration" value={formatDuration(scan?.started ?? 0, scan?.ended ?? 0)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Doughnut chart (CSS-based) */}
        <div className="card">
          <h3 className="text-sm font-semibold text-foreground mb-4">Event Distribution</h3>
          {isLoading ? (
            <Skeleton className="h-48 w-48 rounded-full mx-auto" />
          ) : top8.length > 0 ? (
            <div className="space-y-3">
              {top8.map((d, i) => {
                const pct = totalEvents > 0 ? (d.total / totalEvents) * 100 : 0;
                return (
                  <div key={d.key} className="flex items-center gap-3">
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: colors[i] }} />
                    <span className="text-xs text-dark-300 flex-1 truncate">{d.description || d.key}</span>
                    <span className="text-xs text-dark-500 tabular-nums w-8 text-right">{d.total}</span>
                    <div className="w-20">
                      <div className="progress-bar">
                        <div className="progress-fill animate-progress" style={{ width: `${pct}%`, backgroundColor: colors[i] }} />
                      </div>
                    </div>
                  </div>
                );
              })}
              {sorted.length > 8 && (
                <p className="text-xs text-dark-600 text-center">+{sorted.length - 8} more types</p>
              )}
            </div>
          ) : (
            <p className="text-dark-500 text-sm text-center py-8">No data yet</p>
          )}
        </div>

        {/* Full data types table */}
        <div className="lg:col-span-2 card">
          <h3 className="text-sm font-semibold text-foreground mb-4">Data Types ({sorted.length})</h3>
          {isLoading ? (
            <TableSkeleton rows={6} cols={4} />
          ) : (
            <div className="overflow-y-auto max-h-[500px] -mx-2">
              <table className="w-full">
                <thead className="sticky top-0 bg-dark-800">
                  <tr className="border-b border-dark-700/60">
                    <th className="table-header">Type</th>
                    <th className="table-header text-right">Total</th>
                    <th className="table-header text-right">Unique</th>
                    <th className="table-header text-right">Last Seen</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700/30">
                  {sorted.map((d, i) => (
                    <tr key={d.key} className="table-row animate-fade-in" style={{ animationDelay: `${i * 15}ms` }}>
                      <td className="table-cell text-foreground text-xs">{d.description || d.key}</td>
                      <td className="table-cell text-right tabular-nums text-dark-300">{d.total}</td>
                      <td className="table-cell text-right tabular-nums text-dark-400">{d.unique_total}</td>
                      <td className="table-cell text-right text-dark-500 text-xs whitespace-nowrap">{formatEpoch(d.last_in)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Correlation Risk Breakdown */}
      {corrTotal > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-foreground mb-4">Correlation Summary</h3>
          <div className="flex flex-wrap gap-4">
            {Object.entries(corrBreakdown).map(([risk, count]) => {
              const bgClass = risk.toLowerCase() === 'critical' || risk.toLowerCase() === 'high'
                ? 'corr-card-high'
                : risk.toLowerCase() === 'medium'
                ? 'corr-card-medium'
                : risk.toLowerCase() === 'low'
                ? 'corr-card-low'
                : 'corr-card-info';
              return (
                <div key={risk} className={`px-4 py-3 rounded-lg border ${bgClass} text-center min-w-[100px]`}>
                  <p className="text-lg font-bold">{count}</p>
                  <p className="text-xs opacity-80 capitalize">{risk}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default memo(SummaryTab);
