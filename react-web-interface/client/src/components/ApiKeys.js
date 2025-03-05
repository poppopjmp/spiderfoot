import React, { useState, useEffect } from 'react';
import { fetchApiKeys, importApiKey } from '../api';

const ApiKeys = () => {
  const [apiKey, setApiKey] = useState('');
  const [moduleName, setModuleName] = useState('');
  const [apiKeys, setApiKeys] = useState([]);

  useEffect(() => {
    fetchApiKeys().then(setApiKeys);
  }, []);

  const handleImportApiKey = async () => {
    try {
      await importApiKey(moduleName, apiKey);
      fetchApiKeys().then(setApiKeys);
      alert('API key imported successfully');
    } catch (error) {
      console.error('Error importing API key:', error);
      alert('Error importing API key');
    }
  };

  return (
    <div>
      <h2>API Keys</h2>
      <input
        type="text"
        placeholder="Module Name"
        value={moduleName}
        onChange={(e) => setModuleName(e.target.value)}
        className="form-control mb-2"
      />
      <input
        type="text"
        placeholder="API Key"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        className="form-control mb-2"
      />
      <button onClick={handleImportApiKey} className="btn btn-primary mb-2">
        Import API Key
      </button>
      <div>
        <h3>Imported API Keys</h3>
        <pre>{JSON.stringify(apiKeys, null, 2)}</pre>
      </div>
    </div>
  );
};

export default ApiKeys;
