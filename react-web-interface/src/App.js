import React, { useState, useEffect } from 'react';
import { fetchModules, fetchActiveScans, fetchScanHistory, fetchApiKeys, startScan, stopScan, getScanResults, getScanStatus, exportScanResults, importApiKey } from './api';

const App = () => {
  const [target, setTarget] = useState('');
  const [modules, setModules] = useState([]);
  const [scanId, setScanId] = useState('');
  const [scanResults, setScanResults] = useState([]);
  const [availableModules, setAvailableModules] = useState([]);
  const [activeScans, setActiveScans] = useState([]);
  const [scanStatus, setScanStatus] = useState('');
  const [scanHistory, setScanHistory] = useState([]);
  const [exportedResults, setExportedResults] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiKeys, setApiKeys] = useState([]);

  useEffect(() => {
    fetchModules().then(setAvailableModules);
    fetchActiveScans().then(setActiveScans);
    fetchScanHistory().then(setScanHistory);
    fetchApiKeys().then(setApiKeys);
  }, []);

  const handleStartScan = async () => {
    try {
      const scanId = await startScan(target, modules);
      setScanId(scanId);
    } catch (error) {
      console.error('Error starting scan:', error);
    }
  };

  const handleStopScan = async () => {
    try {
      await stopScan(scanId);
      setScanId('');
    } catch (error) {
      console.error('Error stopping scan:', error);
    }
  };

  const handleGetScanResults = async () => {
    try {
      const results = await getScanResults(scanId);
      setScanResults(results);
    } catch (error) {
      console.error('Error fetching scan results:', error);
    }
  };

  const handleGetScanStatus = async () => {
    try {
      const status = await getScanStatus(scanId);
      setScanStatus(status);
    } catch (error) {
      console.error('Error fetching scan status:', error);
    }
  };

  const handleExportScanResults = async (format) => {
    try {
      const exportedResults = await exportScanResults(scanId, format);
      setExportedResults(exportedResults);
    } catch (error) {
      console.error('Error exporting scan results:', error);
    }
  };

  const handleImportApiKey = async () => {
    try {
      await importApiKey('module_name', apiKey);
      fetchApiKeys().then(setApiKeys);
    } catch (error) {
      console.error('Error importing API key:', error);
    }
  };

  return (
    <div>
      <h1>SpiderFoot React Web Interface</h1>
      <div>
        <h2>Start Scan</h2>
        <input
          type="text"
          placeholder="Target"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
        <select multiple value={modules} onChange={(e) => setModules([...e.target.selectedOptions].map(option => option.value))}>
          {availableModules.map((module) => (
            <option key={module} value={module}>
              {module}
            </option>
          ))}
        </select>
        <button onClick={handleStartScan}>Start Scan</button>
      </div>
      <div>
        <h2>Stop Scan</h2>
        <input
          type="text"
          placeholder="Scan ID"
          value={scanId}
          onChange={(e) => setScanId(e.target.value)}
        />
        <button onClick={handleStopScan}>Stop Scan</button>
      </div>
      <div>
        <h2>Scan Results</h2>
        <button onClick={handleGetScanResults}>Get Scan Results</button>
        <pre>{JSON.stringify(scanResults, null, 2)}</pre>
      </div>
      <div>
        <h2>Scan Status</h2>
        <button onClick={handleGetScanStatus}>Get Scan Status</button>
        <pre>{scanStatus}</pre>
      </div>
      <div>
        <h2>Export Scan Results</h2>
        <button onClick={() => handleExportScanResults('csv')}>Export as CSV</button>
        <button onClick={() => handleExportScanResults('json')}>Export as JSON</button>
        <pre>{exportedResults}</pre>
      </div>
      <div>
        <h2>API Keys</h2>
        <input
          type="text"
          placeholder="API Key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
        <button onClick={handleImportApiKey}>Import API Key</button>
        <pre>{JSON.stringify(apiKeys, null, 2)}</pre>
      </div>
      <div>
        <h2>Active Scans</h2>
        <pre>{JSON.stringify(activeScans, null, 2)}</pre>
      </div>
      <div>
        <h2>Scan History</h2>
        <pre>{JSON.stringify(scanHistory, null, 2)}</pre>
      </div>
    </div>
  );
};

export default App;
