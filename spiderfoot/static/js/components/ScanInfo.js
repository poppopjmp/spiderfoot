import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';

const ScanInfo = () => {
  const { id } = useParams();
  const [scanDetails, setScanDetails] = useState(null);

  useEffect(() => {
    fetch(`/api/scans/${id}`)
      .then(response => response.json())
      .then(data => setScanDetails(data))
      .catch(error => console.error('Error fetching scan details:', error));
  }, [id]);

  if (!scanDetails) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h2>Scan Details</h2>
      <p><strong>Status:</strong> {scanDetails.status}</p>
      <p><strong>Logs:</strong></p>
      <ul>
        {scanDetails.logs.map((log, index) => (
          <li key={index}>{log}</li>
        ))}
      </ul>
      <p><strong>Event Data:</strong></p>
      <ul>
        {scanDetails.eventData.map((event, index) => (
          <li key={index}>{event}</li>
        ))}
      </ul>
    </div>
  );
};

export default ScanInfo;
