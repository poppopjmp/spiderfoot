import React, { useState, useEffect } from 'react';
import { fetchScanHistory } from '../api';

const ScanHistory = () => {
  const [scanHistory, setScanHistory] = useState([]);

  useEffect(() => {
    const getScanHistory = async () => {
      try {
        const data = await fetchScanHistory();
        setScanHistory(data);
      } catch (error) {
        console.error('Error fetching scan history:', error);
      }
    };

    getScanHistory();
  }, []);

  return (
    <div>
      <h2>Scan History</h2>
      <pre>{JSON.stringify(scanHistory, null, 2)}</pre>
    </div>
  );
};

export default ScanHistory;
