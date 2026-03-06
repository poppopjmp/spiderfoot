import { memo, useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scanApi, formatEpoch, type ScanEvent, type EventSummaryDetail } from '../../lib/api';
import { Eye, EyeOff, List } from 'lucide-react';
import { SearchInput, EmptyState, TableSkeleton } from '../ui';

function BrowseTab({ scanId }: { scanId: string }) {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewUnique, setViewUnique] = useState(false);
  const [hideFP, setHideFP] = useState(false);
  const queryClient = useQueryClient();

  const { data: summaryData } = useQuery({
    queryKey: ['scan-summary', scanId],
    queryFn: ({ signal }) => scanApi.summary(scanId, undefined, signal),
  });

  const { data: eventsData, isLoading: eventsLoading } = useQuery({
    queryKey: ['scan-events', scanId, selectedType, false],
    queryFn: ({ signal }) => scanApi.events(scanId, { event_type: selectedType ?? undefined }, signal),
    enabled: !!selectedType && !viewUnique,
  });

  const { data: uniqueData, isLoading: uniqueLoading } = useQuery({
    queryKey: ['scan-events-unique', scanId, selectedType],
    queryFn: ({ signal }) => scanApi.eventsUnique(scanId, selectedType ?? undefined, signal),
    enabled: !!selectedType && viewUnique,
  });

  const details: EventSummaryDetail[] = summaryData?.details ?? [];
  const events: ScanEvent[] = eventsData?.events ?? [];
  const uniqueEvents = uniqueData?.events ?? [];

  /* False positive mutation */
  const fpMut = useMutation({
    mutationFn: ({ hashList, fp }: { hashList: string[]; fp: boolean }) =>
      scanApi.setFalsePositive(scanId, hashList, fp),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scan-events', scanId] });
    },
    onError: (err: Error) => {
      console.error('Failed to update false positive status:', err);
    },
  });

  const filteredEvents = useMemo(() => {
    let list = events;
    if (hideFP) list = list.filter((e: ScanEvent) => !e.false_positive);
    if (!searchQuery) return list;
    const q = searchQuery.toLowerCase();
    return list.filter(
      (e: ScanEvent) => e.data?.toLowerCase().includes(q) || e.module?.toLowerCase().includes(q) || e.source_data?.toLowerCase().includes(q),
    );
  }, [events, searchQuery, hideFP]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
      {/* Type list */}
      <div className="card p-0 overflow-hidden">
        <div className="p-3 border-b border-dark-700/50">
          <h3 className="text-sm font-semibold text-foreground">Data Types</h3>
        </div>
        <div className="overflow-y-auto max-h-[600px]">
          {details.sort((a, b) => b.total - a.total).map((d) => (
            <button
              key={d.key}
              onClick={() => { setSelectedType(d.key); setSearchQuery(''); }}
              className={`w-full flex items-center justify-between px-3 py-2.5 text-left text-sm transition-colors ${
                selectedType === d.key
                  ? 'bg-spider-600/10 text-spider-400 border-l-2 border-spider-500'
                  : 'text-dark-300 hover:bg-dark-700/30 border-l-2 border-transparent'
              }`}
            >
              <span className="truncate">{d.description || d.key}</span>
              <span className="text-xs text-dark-500 tabular-nums ml-2">{d.total}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Events */}
      <div className="lg:col-span-3 card">
        {selectedType ? (
          <>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-foreground">{selectedType}</h3>
              <div className="flex items-center gap-2">
                <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Filter events..." className="w-60" debounceMs={250} />
                <button
                  className={hideFP ? 'btn-primary text-xs' : 'btn-secondary text-xs'}
                  onClick={() => setHideFP(!hideFP)}
                  title={hideFP ? 'Show false positives' : 'Hide false positives'}
                >
                  {hideFP ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                  FP
                </button>
                <button
                  className={viewUnique ? 'btn-primary text-xs' : 'btn-secondary text-xs'}
                  onClick={() => setViewUnique(!viewUnique)}
                >
                  {viewUnique ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                  {viewUnique ? 'Unique' : 'All'}
                </button>
              </div>
            </div>

            {(eventsLoading || uniqueLoading) ? (
              <TableSkeleton rows={8} cols={4} />
            ) : viewUnique ? (
              uniqueEvents.length > 0 ? (
                <div className="overflow-y-auto max-h-[500px]">
                  <table className="w-full">
                    <thead className="sticky top-0 bg-dark-800">
                      <tr className="border-b border-dark-700/60">
                        <th className="table-header">Value</th>
                        <th className="table-header text-right">Count</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-700/30">
                      {uniqueEvents.map((e: { data: string; count: number }, i: number) => (
                        <tr key={i} className="table-row">
                          <td className="table-cell font-mono text-xs text-dark-200 break-all">{e.data}</td>
                          <td className="table-cell text-right tabular-nums text-dark-400">{e.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-dark-500 text-sm text-center py-8">No unique data</p>
              )
            ) : (
              filteredEvents.length > 0 ? (
                <div className="overflow-y-auto max-h-[500px]">
                  <table className="w-full">
                    <thead className="sticky top-0 bg-dark-800">
                      <tr className="border-b border-dark-700/60">
                        <th className="table-header">Data</th>
                        <th className="table-header">Module</th>
                        <th className="table-header">Source</th>
                        <th className="table-header text-right">Time</th>
                        <th className="table-header w-10 text-center" title="False Positive">FP</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-700/30">
                      {filteredEvents.map((e: ScanEvent, i: number) => (
                        <tr key={e.hash || i} className={`table-row ${e.false_positive ? 'opacity-40' : ''}`}>
                          <td className="table-cell font-mono text-xs text-dark-200 break-all max-w-md">
                            <span className={`line-clamp-3 ${e.false_positive ? 'line-through' : ''}`}>{e.data}</span>
                          </td>
                          <td className="table-cell text-dark-400 text-xs whitespace-nowrap">
                            {e.module?.replace('sfp_', '')}
                          </td>
                          <td className="table-cell text-dark-500 text-xs truncate max-w-xs">{e.source_data}</td>
                          <td className="table-cell text-right text-dark-500 text-xs whitespace-nowrap">
                            {formatEpoch(e.generated)}
                          </td>
                          <td className="table-cell text-center">
                            {e.hash && (
                              <button
                                onClick={() => fpMut.mutate({ hashList: [e.hash!], fp: !e.false_positive })}
                                className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                                  e.false_positive
                                    ? 'bg-yellow-900/30 text-yellow-400 hover:bg-yellow-900/50'
                                    : 'text-dark-600 hover:text-yellow-400 hover:bg-dark-700/50'
                                }`}
                                title={e.false_positive ? 'Unmark as false positive' : 'Mark as false positive'}
                              >
                                FP
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-dark-500 text-sm text-center py-8">
                  {searchQuery ? 'No matching events' : 'No events for this type'}
                </p>
              )
            )}
          </>
        ) : (
          <EmptyState
            icon={List}
            title="Select a data type"
            description="Choose a data type from the left panel to view its events."
            className="py-12"
          />
        )}
      </div>
    </div>
  );
}

export default memo(BrowseTab);
