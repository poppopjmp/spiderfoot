import React, { useState, useEffect } from 'react';
import axios from 'axios';

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
    fetchModules();
    fetchActiveScans();
    fetchScanHistory();
    fetchApiKeys();
  }, []);

  const fetchModules = async () => {
    try {
      const response = await axios.get('/api/modules');
      setAvailableModules(response.data.modules);
    } catch (error) {
      console.error('Error fetching modules:', error);
    }
  };

  const fetchActiveScans = async () => {
    try {
      const response = await axios.get('/api/active_scans');
      setActiveScans(response.data.active_scans);
    } catch (error) {
      console.error('Error fetching active scans:', error);
    }
  };

  const fetchScanHistory = async () => {
    try {
      const response = await axios.get('/api/scan_history');
      setScanHistory(response.data.history);
    } catch (error) {
      console.error('Error fetching scan history:', error);
    }
  };

  const fetchApiKeys = async () => {
    try {
      const response = await axios.get('/api/export_api_keys');
      setApiKeys(response.data.api_keys);
    } catch (error) {
      console.error('Error fetching API keys:', error);
    }
  };

  const startScan = async () => {
    try {
      const response = await axios.post('/api/start_scan', { target, modules });
      setScanId(response.data.scan_id);
    } catch (error) {
      console.error('Error starting scan:', error);
    }
  };

  const stopScan = async () => {
    try {
      await axios.post('/api/stop_scan', { scan_id: scanId });
      setScanId('');
    } catch (error) {
      console.error('Error stopping scan:', error);
    }
  };

  const getScanResults = async () => {
    try {
      const response = await axios.get(`/api/scan_results/${scanId}`);
      setScanResults(response.data.results);
    } catch (error) {
      console.error('Error fetching scan results:', error);
    }
  };

  const getScanStatus = async () => {
    try {
      const response = await axios.get(`/api/scan_status/${scanId}`);
      setScanStatus(response.data.status);
    } catch (error) {
      console.error('Error fetching scan status:', error);
    }
  };

  const exportScanResults = async (format) => {
    try {
      const response = await axios.get(`/api/export_scan_results/${scanId}?format=${format}`);
      setExportedResults(response.data.exported_results);
    } catch (error) {
      console.error('Error exporting scan results:', error);
    }
  };

  const importApiKey = async () => {
    try {
      await axios.post('/api/import_api_key', { module: 'module_name', key: apiKey });
      fetchApiKeys();
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
        <button onClick={startScan}>Start Scan</button>
      </div>
      <div>
        <h2>Stop Scan</h2>
        <input
          type="text"
          placeholder="Scan ID"
          value={scanId}
          onChange={(e) => setScanId(e.target.value)}
        />
        <button onClick={stopScan}>Stop Scan</button>
      </div>
      <div>
        <h2>Scan Results</h2>
        <button onClick={getScanResults}>Get Scan Results</button>
        <pre>{JSON.stringify(scanResults, null, 2)}</pre>
      </div>
      <div>
        <h2>Scan Status</h2>
        <button onClick={getScanStatus}>Get Scan Status</button>
        <pre>{scanStatus}</pre>
      </div>
      <div>
        <h2>Export Scan Results</h2>
        <button onClick={() => exportScanResults('csv')}>Export as CSV</button>
        <button onClick={() => exportScanResults('json')}>Export as JSON</button>
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
        <button onClick={importApiKey}>Import API Key</button>
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
