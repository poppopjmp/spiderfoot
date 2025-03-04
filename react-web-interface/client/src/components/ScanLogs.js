import React, { useState, useEffect } from 'react';
import { fetchScanLogs } from '../api';

const ScanLogs = ({ scanId }) => {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    const getLogs = async () => {
      try {
        const data = await fetchScanLogs(scanId);
        setLogs(data);
      } catch (error) {
        console.error('Error fetching scan logs:', error);
      }
    };

    if (scanId) {
      getLogs();
    }
  }, [scanId]);

  return (
    <div>
      <h2>Scan Logs</h2>
      <pre>{JSON.stringify(logs, null, 2)}</pre>
    </div>
  );
};

export default ScanLogs;
