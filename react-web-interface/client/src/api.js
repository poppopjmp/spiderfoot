import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000';

export const fetchModules = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/modules`);
    return response.data.modules;
  } catch (error) {
    console.error('Error fetching modules:', error);
    throw error;
  }
};

export const fetchActiveScans = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/active_scans`);
    return response.data.active_scans;
  } catch (error) {
    console.error('Error fetching active scans:', error);
    throw error;
  }
};

export const fetchScanHistory = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/scan_history`);
    return response.data.history;
  } catch (error) {
    console.error('Error fetching scan history:', error);
    throw error;
  }
};

export const fetchApiKeys = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/export_api_keys`);
    return response.data.api_keys;
  } catch (error) {
    console.error('Error fetching API keys:', error);
    throw error;
  }
};

export const startScan = async (target, modules) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/start_scan`, { target, modules });
    return response.data.scan_id;
  } catch (error) {
    console.error('Error starting scan:', error);
    throw error;
  }
};

export const stopScan = async (scanId) => {
  try {
    await axios.post(`${API_BASE_URL}/stop_scan`, { scan_id: scanId });
  } catch (error) {
    console.error('Error stopping scan:', error);
    throw error;
  }
};

export const getScanResults = async (scanId) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/scan_results/${scanId}`);
    return response.data.results;
  } catch (error) {
    console.error('Error fetching scan results:', error);
    throw error;
  }
};

export const getScanStatus = async (scanId) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/scan_status/${scanId}`);
    return response.data.status;
  } catch (error) {
    console.error('Error fetching scan status:', error);
    throw error;
  }
};

export const exportScanResults = async (scanId, format) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/export_scan_results/${scanId}?format=${format}`);
    return response.data.exported_results;
  } catch (error) {
    console.error('Error exporting scan results:', error);
    throw error;
  }
};

export const importApiKey = async (module, key) => {
  try {
    await axios.post(`${API_BASE_URL}/import_api_key`, { module, key });
  } catch (error) {
    console.error('Error importing API key:', error);
    throw error;
  }
};

export const configureModule = async (module, config) => {
  try {
    await axios.post(`${API_BASE_URL}/configure_module`, { module, config });
  } catch (error) {
    console.error('Error configuring module:', error);
    throw error;
  }
};

export const fetchScanCorrelations = async (scanId) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/scan_correlations/${scanId}`);
    return response.data.correlations;
  } catch (error) {
    console.error('Error fetching scan correlations:', error);
    throw error;
  }
};

export const fetchScanLogs = async (scanId) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/scan_logs/${scanId}`);
    return response.data.logs;
  } catch (error) {
    console.error('Error fetching scan logs:', error);
    throw error;
  }
};

export const fetchScanSummary = async (scanId) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/scan_summary/${scanId}`);
    return response.data.summary;
  } catch (error) {
    console.error('Error fetching scan summary:', error);
    throw error;
  }
};
