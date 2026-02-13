import { useQuery } from '@tanstack/react-query';
import { scanApi } from '../lib/api';
import { FileDown, FileJson, Shield, Bug, FileSpreadsheet, FileText } from 'lucide-react';
import { useState } from 'react';

export default function ExportPage() {
  const [selectedScan, setSelectedScan] = useState('');
  const { data: scans } = useQuery({ queryKey: ['scans'], queryFn: scanApi.list });

  const formats = [
    {
      id: 'csv', name: 'CSV', description: 'Comma-separated values for spreadsheet tools',
      icon: FileSpreadsheet, color: 'text-green-400 bg-green-600/20',
      endpoint: `/api/v1/scans/${selectedScan}/export/csv`,
    },
    {
      id: 'json', name: 'JSON', description: 'Structured JSON export of all scan data',
      icon: FileJson, color: 'text-blue-400 bg-blue-600/20',
      endpoint: `/api/v1/scans/${selectedScan}/export/json`,
    },
    {
      id: 'stix', name: 'STIX 2.1', description: 'Structured Threat Information Expression (TAXII compatible)',
      icon: Shield, color: 'text-purple-400 bg-purple-600/20',
      endpoint: `/api/v1/stix/bundle/${selectedScan}`,
    },
    {
      id: 'sarif', name: 'SARIF', description: 'Static Analysis Results Interchange Format (for GitHub/Azure DevOps)',
      icon: Bug, color: 'text-orange-400 bg-orange-600/20',
      endpoint: `/api/v1/sarif/report/${selectedScan}`,
    },
    {
      id: 'pdf', name: 'PDF Report', description: 'Formatted PDF report using custom templates',
      icon: FileText, color: 'text-red-400 bg-red-600/20',
      endpoint: `/api/v1/reports/generate`,
    },
  ];

  const handleExport = (format: typeof formats[0]) => {
    if (!selectedScan) return;
    window.open(format.endpoint, '_blank');
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Export & Integrations</h1>

      {/* Scan selector */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-white mb-3">Select Scan to Export</h2>
        <select
          className="input-field w-full max-w-md"
          value={selectedScan}
          onChange={(e) => setSelectedScan(e.target.value)}
        >
          <option value="">Choose a scan...</option>
          {scans?.map((s) => (
            <option key={s.id} value={s.id}>{s.name} — {s.target} ({s.status})</option>
          ))}
        </select>
      </div>

      {/* Export formats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {formats.map((f) => (
          <div key={f.id} className="card hover:border-spider-600 border border-transparent transition-colors">
            <div className="flex items-start gap-3 mb-4">
              <div className={`p-3 rounded-lg ${f.color.split(' ')[1]}`}>
                <f.icon className={`h-6 w-6 ${f.color.split(' ')[0]}`} />
              </div>
              <div>
                <h3 className="text-white font-semibold">{f.name}</h3>
                <p className="text-sm text-dark-400 mt-1">{f.description}</p>
              </div>
            </div>
            <button
              className="btn-primary w-full flex items-center justify-center gap-2"
              onClick={() => handleExport(f)}
              disabled={!selectedScan}
            >
              <FileDown className="h-4 w-4" /> Export {f.name}
            </button>
          </div>
        ))}
      </div>

      {/* Integration info */}
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-4">TAXII Server</h2>
        <p className="text-sm text-dark-400 mb-3">
          SpiderFoot includes a built-in TAXII 2.1 server for automated threat intelligence sharing.
        </p>
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-3 p-3 bg-dark-700/50 rounded-lg">
            <span className="text-dark-300 w-32">Discovery URL</span>
            <code className="text-spider-400 font-mono">/api/v1/taxii/discovery</code>
          </div>
          <div className="flex items-center gap-3 p-3 bg-dark-700/50 rounded-lg">
            <span className="text-dark-300 w-32">API Root</span>
            <code className="text-spider-400 font-mono">/api/v1/taxii/api-root</code>
          </div>
          <div className="flex items-center gap-3 p-3 bg-dark-700/50 rounded-lg">
            <span className="text-dark-300 w-32">Collections</span>
            <code className="text-spider-400 font-mono">/api/v1/taxii/collections</code>
          </div>
        </div>
      </div>
    </div>
  );
}
