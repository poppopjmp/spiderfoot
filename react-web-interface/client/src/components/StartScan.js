import React, { useState, useEffect } from 'react';
import { fetchModules, startScan } from '../api';

const StartScan = () => {
  const [target, setTarget] = useState('');
  const [modules, setModules] = useState([]);
  const [availableModules, setAvailableModules] = useState([]);

  useEffect(() => {
    fetchModules().then(setAvailableModules);
  }, []);

  const handleStartScan = async () => {
    try {
      const scanId = await startScan(target, modules);
      alert(`Scan started with ID: ${scanId}`);
    } catch (error) {
      console.error('Error starting scan:', error);
      alert('Error starting scan');
    }
  };

  return (
    <div>
      <h2>Start Scan</h2>
      <input
        type="text"
        placeholder="Target"
        value={target}
        onChange={(e) => setTarget(e.target.value)}
        className="form-control mb-2"
      />
      <select
        multiple
        value={modules}
        onChange={(e) => setModules([...e.target.selectedOptions].map(option => option.value))}
        className="form-control mb-2"
      >
        {availableModules.map((module) => (
          <option key={module} value={module}>
            {module}
          </option>
        ))}
      </select>
      <button onClick={handleStartScan} className="btn btn-primary">Start Scan</button>
    </div>
  );
};

export default StartScan;
