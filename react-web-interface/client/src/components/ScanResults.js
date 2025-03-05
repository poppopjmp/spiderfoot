import React, { useState } from 'react';
import { getScanResults } from '../api';

const ScanResults = () => {
  const [scanId, setScanId] = useState('');
  const [results, setResults] = useState(null);

  const fetchResults = async () => {
    try {
      const data = await getScanResults(scanId);
      setResults(data);
    } catch (error) {
      console.error('Error fetching scan results:', error);
    }
  };

  return (
    <div className="scan-results">
      <h2>Scan Results</h2>
      <input
        type="text"
        placeholder="Enter Scan ID"
        value={scanId}
        onChange={(e) => setScanId(e.target.value)}
        className="form-control mb-2"
      />
      <button onClick={fetchResults} className="btn btn-primary mb-2">
        Fetch Scan Results
      </button>
      {results && (
        <div className="results">
          <pre>{JSON.stringify(results, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default ScanResults;
