import React, { useState, useEffect } from 'react';

const NewScan = () => {
  const [scanName, setScanName] = useState('');
  const [scanTarget, setScanTarget] = useState('');

  const handleScanNameChange = (e) => {
    setScanName(e.target.value);
  };

  const handleScanTargetChange = (e) => {
    setScanTarget(e.target.value);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // Add logic to handle form submission
  };

  return (
    <div>
      <h2>New Scan</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="scanName">Scan Name</label>
          <input
            type="text"
            id="scanName"
            value={scanName}
            onChange={handleScanNameChange}
            placeholder="The name of this scan."
          />
        </div>
        <div>
          <label htmlFor="scanTarget">Scan Target</label>
          <input
            type="text"
            id="scanTarget"
            value={scanTarget}
            onChange={handleScanTargetChange}
            placeholder="The target of your scan."
          />
        </div>
        <button type="submit">Run Scan Now</button>
      </form>
    </div>
  );
};

export default NewScan;
