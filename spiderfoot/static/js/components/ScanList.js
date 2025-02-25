import React, { useState, useEffect } from 'react';

const ScanList = () => {
  const [scans, setScans] = useState([]);

  useEffect(() => {
    fetch('/api/scans')
      .then(response => response.json())
      .then(data => setScans(data))
      .catch(error => console.error('Error fetching scans:', error));
  }, []);

  const handleDelete = (id) => {
    fetch(`/api/scans/${id}`, { method: 'DELETE' })
      .then(() => setScans(scans.filter(scan => scan.id !== id)))
      .catch(error => console.error('Error deleting scan:', error));
  };

  const handleStop = (id) => {
    fetch(`/api/scans/${id}/stop`, { method: 'POST' })
      .then(() => setScans(scans.map(scan => scan.id === id ? { ...scan, status: 'stopped' } : scan)))
      .catch(error => console.error('Error stopping scan:', error));
  };

  const handleRerun = (id) => {
    fetch(`/api/scans/${id}/rerun`, { method: 'POST' })
      .then(() => setScans(scans.map(scan => scan.id === id ? { ...scan, status: 'running' } : scan)))
      .catch(error => console.error('Error rerunning scan:', error));
  };

  return (
    <div>
      <h2>Scan List</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {scans.map(scan => (
            <tr key={scan.id}>
              <td>{scan.id}</td>
              <td>{scan.name}</td>
              <td>{scan.status}</td>
              <td>
                <button onClick={() => handleDelete(scan.id)}>Delete</button>
                <button onClick={() => handleStop(scan.id)}>Stop</button>
                <button onClick={() => handleRerun(scan.id)}>Rerun</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ScanList;
