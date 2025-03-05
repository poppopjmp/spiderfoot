import React, { useState } from 'react';
import { exportScanResults } from '../api';

const ExportScanResults = () => {
  const [scanId, setScanId] = useState('');
  const [exportedResults, setExportedResults] = useState('');

  const handleExport = async (format) => {
    try {
      const results = await exportScanResults(scanId, format);
      setExportedResults(results);
    } catch (error) {
      console.error('Error exporting scan results:', error);
    }
  };

  return (
    <div className="export-scan-results">
      <h2>Export Scan Results</h2>
      <input
        type="text"
        placeholder="Enter Scan ID"
        value={scanId}
        onChange={(e) => setScanId(e.target.value)}
        className="form-control mb-2"
      />
      <button onClick={() => handleExport('csv')} className="btn btn-primary mb-2">
        Export as CSV
      </button>
      <button onClick={() => handleExport('json')} className="btn btn-primary mb-2">
        Export as JSON
      </button>
      {exportedResults && (
        <div className="results">
          <pre>{JSON.stringify(exportedResults, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default ExportScanResults;
