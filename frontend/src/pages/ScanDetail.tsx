import { useQuery } from '@tanstack/react-query';
import { useParams, Link } from 'react-router-dom';
import { scanApi } from '../lib/api';
import { ArrowLeft, StopCircle, Download } from 'lucide-react';

export default function ScanDetailPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const { data: scan, isLoading } = useQuery({
    queryKey: ['scan', scanId],
    queryFn: () => scanApi.get(scanId!),
    enabled: !!scanId,
  });

  if (isLoading) {
    return <p className="text-dark-400">Loading scan details...</p>;
  }

  if (!scan) {
    return <p className="text-dark-400">Scan not found.</p>;
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Link to="/scans" className="text-dark-400 hover:text-white">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <h1 className="text-2xl font-bold text-white">{scan.name}</h1>
        <StatusBadge status={scan.status} />
      </div>

      {/* Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <InfoCard label="Target" value={scan.target} />
        <InfoCard label="Events" value={String(scan.event_count)} />
        <InfoCard label="Started" value={scan.started || '—'} />
      </div>

      {/* Actions */}
      <div className="flex gap-3 mb-6">
        {scan.status === 'RUNNING' && (
          <button className="btn-danger flex items-center gap-2">
            <StopCircle className="h-4 w-4" /> Abort
          </button>
        )}
        <button className="btn-secondary flex items-center gap-2">
          <Download className="h-4 w-4" /> Export
        </button>
      </div>

      {/* Modules */}
      {scan.modules && scan.modules.length > 0 && (
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-white mb-3">Modules</h2>
          <div className="flex flex-wrap gap-2">
            {scan.modules.map((m: string) => (
              <span key={m} className="badge badge-info">
                {m}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Event data placeholder */}
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-3">Event Data</h2>
        <p className="text-dark-400">
          Browse scan events and data in the interactive data explorer. Event listing will be
          populated with detailed findings from this scan.
        </p>
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <p className="text-sm text-dark-400 mb-1">{label}</p>
      <p className="text-white font-medium">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    RUNNING: 'badge-success',
    FINISHED: 'badge-info',
    ABORTED: 'badge-high',
    FAILED: 'badge-critical',
    STARTING: 'badge-low',
  };
  return <span className={`badge ${map[status] || 'badge-info'}`}>{status}</span>;
}
