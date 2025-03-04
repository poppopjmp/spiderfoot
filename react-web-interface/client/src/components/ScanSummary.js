import React, { useState, useEffect } from 'react';
import { fetchScanSummary } from '../api';

const ScanSummary = ({ scanId }) => {
  const [summary, setSummary] = useState([]);

  useEffect(() => {
    const getSummary = async () => {
      try {
        const data = await fetchScanSummary(scanId);
        setSummary(data);
      } catch (error) {
        console.error('Error fetching scan summary:', error);
      }
    };

    if (scanId) {
      getSummary();
    }
  }, [scanId]);

  return (
    <div>
      <h2>Scan Summary</h2>
      <pre>{JSON.stringify(summary, null, 2)}</pre>
    </div>
  );
};

export default ScanSummary;
