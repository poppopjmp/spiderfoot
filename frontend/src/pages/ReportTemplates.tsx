import { useQuery } from '@tanstack/react-query';
import { reportTemplateApi } from '../lib/api';
import { FileText, Download, Eye, Plus, Copy } from 'lucide-react';

export default function ReportTemplatesPage() {
  const { data, isLoading } = useQuery({ queryKey: ['report-templates'], queryFn: reportTemplateApi.list });

  const templates = data?.templates ?? [];
  const categoryColors: Record<string, string> = {
    executive: 'badge-critical',
    technical: 'badge-info',
    vulnerability: 'badge-high',
    compliance: 'badge-medium',
    asset: 'badge-low',
    custom: 'badge-success',
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Report Templates</h1>
        <button className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> Create Template
        </button>
      </div>

      {isLoading ? (
        <p className="text-dark-400">Loading templates...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(templates.length > 0 ? templates : [
            { id: 'exec-summary', name: 'Executive Summary', category: 'executive', format: 'html', description: 'High-level overview for leadership and stakeholders', built_in: true },
            { id: 'tech-detail', name: 'Technical Detail', category: 'technical', format: 'markdown', description: 'Comprehensive technical findings with evidence', built_in: true },
            { id: 'vuln-report', name: 'Vulnerability Report', category: 'vulnerability', format: 'html', description: 'Prioritized vulnerability assessment with remediation', built_in: true },
            { id: 'asset-inventory', name: 'Asset Inventory', category: 'asset', format: 'markdown', description: 'Complete discovered asset listing with metadata', built_in: true },
            { id: 'compliance', name: 'Compliance Report', category: 'compliance', format: 'html', description: 'Regulatory compliance status and gap analysis', built_in: true },
          ]).map((t: { id: string; name: string; category: string; format: string; description: string; built_in?: boolean }) => (
            <div key={t.id} className="card hover:border-spider-600 border border-transparent transition">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-spider-600/20 rounded-lg">
                  <FileText className="h-5 w-5 text-spider-400" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-white">{t.name}</h3>
                  <div className="flex gap-2 mt-1">
                    <span className={`badge ${categoryColors[t.category] || 'badge-info'}`}>{t.category}</span>
                    <span className="badge badge-info">{t.format}</span>
                    {t.built_in && <span className="badge badge-low">built-in</span>}
                  </div>
                </div>
              </div>
              <p className="text-sm text-dark-300 mb-4">{t.description}</p>
              <div className="flex gap-2">
                <button className="text-spider-400 hover:text-spider-300 text-sm flex items-center gap-1">
                  <Eye className="h-3.5 w-3.5" /> Preview
                </button>
                <button className="text-spider-400 hover:text-spider-300 text-sm flex items-center gap-1">
                  <Copy className="h-3.5 w-3.5" /> Clone
                </button>
                <button className="text-spider-400 hover:text-spider-300 text-sm flex items-center gap-1">
                  <Download className="h-3.5 w-3.5" /> Export
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
