import { useQuery } from '@tanstack/react-query';
import { scanCompareApi, scanApi } from '../lib/api';
import { GitCompare, ArrowRight, TrendingUp, TrendingDown } from 'lucide-react';
import { useState } from 'react';

export default function ScanComparisonPage() {
  const [scanA, setScanA] = useState('');
  const [scanB, setScanB] = useState('');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const { data: scans } = useQuery({ queryKey: ['scans'], queryFn: scanApi.list });
  const { data: history } = useQuery({ queryKey: ['compare-history'], queryFn: scanCompareApi.history });
  const { data: categories } = useQuery({ queryKey: ['compare-categories'], queryFn: scanCompareApi.categories });

  const handleCompare = async () => {
    if (!scanA || !scanB) return;
    const res = await scanCompareApi.quick({ scan_a_id: scanA, scan_b_id: scanB });
    setResult(res);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Scan Comparison</h1>

      {/* Compare form */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Compare Two Scans</h2>
        <div className="flex items-center gap-4">
          <select className="input-field flex-1" value={scanA} onChange={(e) => setScanA(e.target.value)}>
            <option value="">Select Scan A</option>
            {scans?.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.target})</option>)}
          </select>
          <ArrowRight className="h-5 w-5 text-dark-400 flex-shrink-0" />
          <select className="input-field flex-1" value={scanB} onChange={(e) => setScanB(e.target.value)}>
            <option value="">Select Scan B</option>
            {scans?.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.target})</option>)}
          </select>
          <button className="btn-primary flex items-center gap-2" onClick={handleCompare} disabled={!scanA || !scanB}>
            <GitCompare className="h-4 w-4" /> Compare
          </button>
        </div>
      </div>

      {/* Result */}
      {result && (
        <div className="space-y-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="card">
              <p className="text-sm text-dark-400">Risk Delta</p>
              <p className={`text-2xl font-bold ${
                (result.risk_delta as number) > 0 ? 'text-red-400' :
                (result.risk_delta as number) < 0 ? 'text-green-400' : 'text-white'
              }`}>
                {(result.risk_delta as number) > 0 ? '+' : ''}{result.risk_delta as number}
                {(result.risk_delta as number) > 0 ? <TrendingUp className="h-4 w-4 inline ml-1" /> : <TrendingDown className="h-4 w-4 inline ml-1" />}
              </p>
            </div>
            <div className="card">
              <p className="text-sm text-dark-400">Risk Grade</p>
              <p className="text-2xl font-bold text-white">{result.risk_grade as string}</p>
            </div>
            <div className="card">
              <p className="text-sm text-dark-400">Events Changed</p>
              <p className="text-2xl font-bold text-white">
                <span className="text-green-400">+{(result.added as number) ?? 0}</span>
                {' / '}
                <span className="text-red-400">-{(result.removed as number) ?? 0}</span>
              </p>
            </div>
          </div>

          {/* Category breakdown */}
          {result.categories && (
            <div className="card">
              <h3 className="text-white font-semibold mb-3">Category Breakdown</h3>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {Object.entries(result.categories as Record<string, { added: number; removed: number }>).map(([cat, diff]) => (
                  <div key={cat} className="p-3 bg-dark-700/50 rounded-lg">
                    <p className="text-xs text-dark-400 capitalize">{cat}</p>
                    <p className="text-sm text-white">
                      <span className="text-green-400">+{diff.added}</span>
                      {' '}
                      <span className="text-red-400">-{diff.removed}</span>
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Available categories */}
      {categories?.categories && (
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-white mb-3">Event Categories</h2>
          <div className="flex flex-wrap gap-2">
            {(categories.categories as string[]).map((c) => (
              <span key={c} className="badge badge-info capitalize">{c}</span>
            ))}
          </div>
        </div>
      )}

      {/* History */}
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-4">Comparison History</h2>
        {(history?.history ?? []).length > 0 ? (
          <div className="space-y-2">
            {(history.history as { id: string; scan_a: string; scan_b: string; risk_delta: number; timestamp: string }[]).map((h) => (
              <div key={h.id} className="flex items-center justify-between p-3 bg-dark-700/30 rounded-lg text-sm">
                <span className="text-white">{h.scan_a} vs {h.scan_b}</span>
                <span className={`font-medium ${h.risk_delta > 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {h.risk_delta > 0 ? '+' : ''}{h.risk_delta}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-dark-400">No comparisons performed yet.</p>
        )}
      </div>
    </div>
  );
}
