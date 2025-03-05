import React, { useState, useEffect } from 'react';
import { fetchActiveScans } from '../api';

const ActiveScans = () => {
  const [activeScans, setActiveScans] = useState([]);

  useEffect(() => {
    const getActiveScans = async () => {
      try {
        const data = await fetchActiveScans();
        setActiveScans(data);
      } catch (error) {
        console.error('Error fetching active scans:', error);
      }
    };

    getActiveScans();
  }, []);

  return (
    <div>
      <h2>Active Scans</h2>
      <pre>{JSON.stringify(activeScans, null, 2)}</pre>
    </div>
  );
};

export default ActiveScans;
