import { useState } from 'react';
import { scanApi } from '../../lib/api';
import { Download, FileText, Share2 } from 'lucide-react';
import { DropdownMenu, DropdownItem, type ToastType } from '../ui';

export default function ExportDropdown({ scanId, scanName, onToast }: { scanId: string; scanName: string; onToast: (t: { type: ToastType; message: string }) => void }) {
  const [exporting, setExporting] = useState<string | null>(null);

  const download = async (type: string) => {
    setExporting(type);
    try {
      const resp = await scanApi.exportEvents(scanId, { filetype: type });
      const blob = resp.data as Blob;
      if (!blob || blob.size === 0) {
        onToast({ type: 'error', message: `Export returned empty data` });
        return;
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${scanName || scanId}.${type}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      onToast({ type: 'success', message: `${type.toUpperCase()} export downloaded` });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      onToast({ type: 'error', message: `Export failed: ${msg}` });
    } finally {
      setExporting(null);
    }
  };

  return (
    <DropdownMenu trigger={<button className="btn-secondary"><Download className="h-4 w-4" /> Export</button>}>
      <DropdownItem icon={FileText} onClick={() => download('csv')}>
        {exporting === 'csv' ? 'Exporting...' : 'CSV'}
      </DropdownItem>
      <DropdownItem icon={FileText} onClick={() => download('xlsx')}>
        {exporting === 'xlsx' ? 'Exporting...' : 'Excel (XLSX)'}
      </DropdownItem>
      <DropdownItem icon={FileText} onClick={() => download('json')}>
        {exporting === 'json' ? 'Exporting...' : 'JSON'}
      </DropdownItem>
      <DropdownItem icon={Share2} onClick={() => download('gexf')}>
        {exporting === 'gexf' ? 'Exporting...' : 'GEXF (Graph)'}
      </DropdownItem>
    </DropdownMenu>
  );
}
