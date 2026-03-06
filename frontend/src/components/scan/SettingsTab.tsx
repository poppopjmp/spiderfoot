import { memo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { scanApi, formatEpoch, formatDuration, type Scan } from '../../lib/api';
import { TableSkeleton, Expandable } from '../ui';

function SettingsTab({ scanId, scan }: { scanId: string; scan?: Scan }) {
  const { data: options, isLoading } = useQuery({
    queryKey: ['scan-options', scanId],
    queryFn: ({ signal }) => scanApi.options(scanId, signal),
  });

  const scanOptions = options?.options ?? options ?? {};

  const globalEntries = Object.entries(scanOptions).filter(([k]) => !k.includes(':'));
  const moduleEntries = Object.entries(scanOptions).filter(([k]) => k.includes(':'));
  const moduleGroups = new Map<string, [string, unknown][]>();
  moduleEntries.forEach(([k, v]) => {
    const [mod] = k.split(':');
    if (!moduleGroups.has(mod)) moduleGroups.set(mod, []);
    moduleGroups.get(mod)!.push([k.split(':').slice(1).join(':'), v]);
  });

  return (
    <div className="space-y-6">
      <div className="card">
        <h3 className="text-sm font-semibold text-foreground mb-4">Scan Information</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {[
            ['Scan ID', scanId],
            ['Name', scan?.name],
            ['Target', scan?.target],
            ['Status', scan?.status],
            ['Profile', scan?.profile],
            ['Created', formatEpoch(scan?.created ?? 0)],
            ['Started', formatEpoch(scan?.started ?? 0)],
            ['Ended', formatEpoch(scan?.ended ?? 0)],
            ['Duration', formatDuration(scan?.started ?? 0, scan?.ended ?? 0)],
            ['Results', scan?.result_count?.toString()],
          ].filter(([, val]) => val != null).map(([label, val]) => (
            <div key={label as string}>
              <p className="text-xs text-dark-500">{label as string}</p>
              <p className="text-sm text-dark-200 font-mono break-all">{(val as string) || '—'}</p>
            </div>
          ))}
        </div>
      </div>

      {globalEntries.length > 0 && (
        <Expandable title={`Global Settings (${globalEntries.length})`} defaultOpen>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            {globalEntries.map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs">
                <span className="text-dark-400">{k}</span>
                <span className="text-dark-200 font-mono truncate ml-2 text-right max-w-[50%]">{String(v)}</span>
              </div>
            ))}
          </div>
        </Expandable>
      )}

      {[...moduleGroups.entries()].map(([mod, entries]) => (
        <Expandable key={mod} title={`${mod} (${entries.length} options)`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            {entries.map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs">
                <span className="text-dark-400">{k}</span>
                <span className="text-dark-200 font-mono truncate ml-2 text-right max-w-[50%]">{String(v)}</span>
              </div>
            ))}
          </div>
        </Expandable>
      ))}

      {isLoading && <TableSkeleton rows={4} cols={2} />}
    </div>
  );
}

export default memo(SettingsTab);
