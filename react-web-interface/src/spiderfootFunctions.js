import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000';

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
    const response = await axios.post(`${API_BASE_URL}/stop_scan/${scanId}`);
    return response.data.message;
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

export const listModules = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/modules`);
    return response.data.modules;
  } catch (error) {
    console.error('Error listing modules:', error);
    throw error;
  }
};

export const listActiveScans = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/active_scans`);
    return response.data.active_scans;
  } catch (error) {
    console.error('Error listing active scans:', error);
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

export const listScanHistory = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/scan_history`);
    return response.data.history;
  } catch (error) {
    console.error('Error listing scan history:', error);
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
    const response = await axios.post(`${API_BASE_URL}/import_api_key`, { module, key });
    return response.data.message;
  } catch (error) {
    console.error('Error importing API key:', error);
    throw error;
  }
};

export const exportApiKeys = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/export_api_keys`);
    return response.data.api_keys;
  } catch (error) {
    console.error('Error exporting API keys:', error);
    throw error;
  }
};
