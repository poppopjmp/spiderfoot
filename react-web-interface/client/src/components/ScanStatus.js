import React, { useState } from 'react';
import { getScanStatus } from '../api';

const ScanStatus = () => {
  const [scanId, setScanId] = useState('');
  const [status, setStatus] = useState(null);

  const fetchStatus = async () => {
    try {
      const data = await getScanStatus(scanId);
      setStatus(data);
    } catch (error) {
      console.error('Error fetching scan status:', error);
    }
  };

  return (
    <div className="scan-status">
      <h2>Scan Status</h2>
      <input
        type="text"
        placeholder="Enter Scan ID"
        value={scanId}
        onChange={(e) => setScanId(e.target.value)}
        className="form-control mb-2"
      />
      <button onClick={fetchStatus} className="btn btn-primary mb-2">
        Fetch Scan Status
      </button>
      {status && (
        <div className="status">
          <pre>{JSON.stringify(status, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default ScanStatus;
