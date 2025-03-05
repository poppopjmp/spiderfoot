import React, { useState } from 'react';
import { stopScan } from '../api';

const StopScan = () => {
  const [scanId, setScanId] = useState('');

  const handleStopScan = async () => {
    try {
      await stopScan(scanId);
      alert('Scan stopped successfully');
    } catch (error) {
      console.error('Error stopping scan:', error);
      alert('Error stopping scan');
    }
  };

  return (
    <div>
      <h2>Stop Scan</h2>
      <input
        type="text"
        placeholder="Scan ID"
        value={scanId}
        onChange={(e) => setScanId(e.target.value)}
        className="form-control mb-2"
      />
      <button onClick={handleStopScan} className="btn btn-danger">Stop Scan</button>
    </div>
  );
};

export default StopScan;
