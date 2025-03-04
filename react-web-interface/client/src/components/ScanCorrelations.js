import React, { useState, useEffect } from 'react';
import { fetchScanCorrelations } from '../api';

const ScanCorrelations = ({ scanId }) => {
  const [correlations, setCorrelations] = useState([]);

  useEffect(() => {
    const getCorrelations = async () => {
      try {
        const data = await fetchScanCorrelations(scanId);
        setCorrelations(data);
      } catch (error) {
        console.error('Error fetching scan correlations:', error);
      }
    };

    if (scanId) {
      getCorrelations();
    }
  }, [scanId]);

  return (
    <div>
      <h2>Scan Correlations</h2>
      <pre>{JSON.stringify(correlations, null, 2)}</pre>
    </div>
  );
};

export default ScanCorrelations;
