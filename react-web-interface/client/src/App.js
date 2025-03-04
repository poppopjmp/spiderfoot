import React, { useState, useEffect } from 'react';
import axios from 'axios';
import alertify from 'alertifyjs';
import 'bootstrap/dist/css/bootstrap.min.css';
import * as d3 from 'd3';
import $ from 'jquery';
import sigma from 'sigma';
import 'tablesorter';

import logo from './img/spiderfoot-icon.png';

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
  const [selectedModule, setSelectedModule] = useState('');
  const [apiBaseUrl, setApiBaseUrl] = useState(''); // Pb299

  useEffect(() => {
    const fetchApiBaseUrl = async () => {
      const baseUrl = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000';
      setApiBaseUrl(baseUrl);
    };

    fetchApiBaseUrl();
    fetchModules();
    fetchActiveScans();
    fetchScanHistory();
    fetchApiKeys();
  }, []);

  const fetchModules = async () => {
    try {
      const response = await axios.get(`${apiBaseUrl}/api/modules`);
      setAvailableModules(response.data.modules);
    } catch (error) {
      console.error('Error fetching modules:', error);
    }
  };

  const fetchActiveScans = async () => {
    try {
      const response = await axios.get(`${apiBaseUrl}/api/active_scans`);
      setActiveScans(response.data.active_scans);
    } catch (error) {
      console.error('Error fetching active scans:', error);
    }
  };

  const fetchScanHistory = async () => {
    try {
      const response = await axios.get(`${apiBaseUrl}/api/scan_history`);
      setScanHistory(response.data.history);
    } catch (error) {
      console.error('Error fetching scan history:', error);
    }
  };

  const fetchApiKeys = async () => {
    try {
      const response = await axios.get(`${apiBaseUrl}/api/export_api_keys`);
      setApiKeys(response.data.api_keys);
    } catch (error) {
      console.error('Error fetching API keys:', error);
    }
  };

  const startScan = async () => {
    try {
      const response = await axios.post(`${apiBaseUrl}/api/start_scan`, { target, modules });
      setScanId(response.data.scan_id);
      alertify.success('Scan started successfully');
    } catch (error) {
      console.error('Error starting scan:', error);
      alertify.error('Error starting scan');
    }
  };

  const stopScan = async () => {
    try {
      await axios.post(`${apiBaseUrl}/api/stop_scan`, { scan_id: scanId });
      setScanId('');
      alertify.success('Scan stopped successfully');
    } catch (error) {
      console.error('Error stopping scan:', error);
      alertify.error('Error stopping scan');
    }
  };

  const getScanResults = async () => {
    try {
      const response = await axios.get(`${apiBaseUrl}/api/scan_results/${scanId}`);
      setScanResults(response.data.results);
      alertify.success('Scan results fetched successfully');
    } catch (error) {
      console.error('Error fetching scan results:', error);
      alertify.error('Error fetching scan results');
    }
  };

  const getScanStatus = async () => {
    try {
      const response = await axios.get(`${apiBaseUrl}/api/scan_status/${scanId}`);
      setScanStatus(response.data.status);
      alertify.success('Scan status fetched successfully');
    } catch (error) {
      console.error('Error fetching scan status:', error);
      alertify.error('Error fetching scan status');
    }
  };

  const exportScanResults = async (format) => {
    try {
      const response = await axios.get(`${apiBaseUrl}/api/export_scan_results/${scanId}?format=${format}`);
      setExportedResults(response.data.exported_results);
      alertify.success('Scan results exported successfully');
    } catch (error) {
      console.error('Error exporting scan results:', error);
      alertify.error('Error exporting scan results');
    }
  };

  const importApiKey = async () => {
    try {
      await axios.post(`${apiBaseUrl}/api/import_api_key`, { module: selectedModule, key: apiKey });
      fetchApiKeys();
      alertify.success('API key imported successfully');
    } catch (error) {
      console.error('Error importing API key:', error);
      alertify.error('Error importing API key');
    }
  };

  const configureModule = async (module, config) => {
    try {
      await axios.post(`${apiBaseUrl}/api/configure_module`, { module, config });
      alertify.success('Module configured successfully');
    } catch (error) {
      console.error('Error configuring module:', error);
      alertify.error('Error configuring module');
    }
  };

  const handleModuleChange = (e) => {
    setSelectedModule(e.target.value);
  };

  return (
    <div className="container">
      <h1 className="text-center my-4">SpiderFoot React Web Interface</h1>
      <img src={logo} alt="Spiderfoot Logo" className="mx-auto d-block mb-4" />
      <div className="mb-4">
        <h2>Start Scan</h2>
        <input
          type="text"
          className="form-control mb-2"
          placeholder="Target"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
        <select multiple className="form-control mb-2" value={modules} onChange={(e) => setModules([...e.target.selectedOptions].map(option => option.value))}>
          {availableModules.map((module) => (
            <option key={module} value={module}>
              {module}
            </option>
          ))}
        </select>
        <button className="btn btn-primary" onClick={startScan}>Start Scan</button>
      </div>
      <div className="mb-4">
        <h2>Stop Scan</h2>
        <input
          type="text"
          className="form-control mb-2"
          placeholder="Scan ID"
          value={scanId}
          onChange={(e) => setScanId(e.target.value)}
        />
        <button className="btn btn-danger" onClick={stopScan}>Stop Scan</button>
      </div>
      <div className="mb-4">
        <h2>Scan Results</h2>
        <button className="btn btn-info mb-2" onClick={getScanResults}>Get Scan Results</button>
        <div id="scan-results">
          <pre>{JSON.stringify(scanResults, null, 2)}</pre>
        </div>
        <div id="sigma-container" style={{ height: '500px', width: '100%' }}>
          <sigma
            graph={scanResults}
            settings={{
              drawEdges: true,
              drawNodes: true,
              defaultNodeColor: '#ec5148',
              defaultEdgeColor: '#c0c0c0',
              edgeColor: 'default',
              nodeColor: 'default',
              labelThreshold: 10,
              defaultLabelColor: '#000000',
              defaultLabelSize: 14,
              defaultLabelBGColor: '#ffffff',
              defaultLabelHoverColor: '#ff0000',
              defaultLabelHoverBGColor: '#ffffff',
              defaultLabelActiveColor: '#00ff00',
              defaultLabelActiveBGColor: '#ffffff',
              defaultLabelAlignment: 'center',
              defaultLabelWeight: 'normal',
              defaultLabelWeightHover: 'bold',
              defaultLabelWeightActive: 'bold',
              defaultLabelWeightBGColor: '#ffffff',
              defaultLabelWeightHoverBGColor: '#ffffff',
              defaultLabelWeightActiveBGColor: '#ffffff',
              defaultLabelWeightAlignment: 'center',
              defaultLabelWeightHoverAlignment: 'center',
              defaultLabelWeightActiveAlignment: 'center',
              defaultLabelWeightHoverSize: 14,
              defaultLabelWeightActiveSize: 14,
              defaultLabelWeightColor: '#000000',
              defaultLabelWeightHoverColor: '#ff0000',
              defaultLabelWeightActiveColor: '#00ff00',
              defaultLabelWeightBGColor: '#ffffff'
            }}
          />
        </div>
      </div>
      <div className="mb-4">
        <h2>Scan Status</h2>
        <button className="btn btn-info mb-2" onClick={getScanStatus}>Get Scan Status</button>
        <pre>{scanStatus}</pre>
      </div>
      <div className="mb-4">
        <h2>Export Scan Results</h2>
        <button onClick={() => exportScanResults('csv')} className="btn btn-info mb-2">Export as CSV</button>
        <button onClick={() => exportScanResults('json')} className="btn btn-info mb-2">Export as JSON</button>
        <pre>{exportedResults}</pre>
      </div>
      <div className="mb-4">
        <h2>API Keys</h2>
        <input
          type="text"
          className="form-control mb-2"
          placeholder="API Key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
        <button className="btn btn-info mb-2" onClick={importApiKey}>Import API Key</button>
        <pre>{JSON.stringify(apiKeys, null, 2)}</pre>
      </div>
      <div className="mb-4">
        <h2>Active Scans</h2>
        <pre>{JSON.stringify(activeScans, null, 2)}</pre>
      </div>
      <div className="mb-4">
        <h2>Scan History</h2>
        <pre>{JSON.stringify(scanHistory, null, 2)}</pre>
      </div>
      <div className="mb-4">
        <h2>Configure Module</h2>
        <select className="form-control mb-2" value={selectedModule} onChange={handleModuleChange}>
          <option value="">Select a module</option>
          {availableModules.map((module) => (
            <option key={module} value={module}>
              {module}
            </option>
          ))}
        </select>
        <button className="btn btn-info mb-2" onClick={() => configureModule(selectedModule, { key: apiKey })}>Configure Module</button>
      </div>
    </div>
  );
};

export default App;
