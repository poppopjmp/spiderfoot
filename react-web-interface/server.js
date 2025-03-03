const express = require('express');
const axios = require('axios');
const path = require('path');
const app = express();
const port = 5000;

app.use(express.json());

app.use(express.static(path.join(__dirname, 'client/build')));

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'client/build', 'index.html'));
});

app.post('/api/start_scan', async (req, res) => {
  try {
    const response = await axios.post('http://127.0.0.1:8000/start_scan', req.body);
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/stop_scan', async (req, res) => {
  try {
    const response = await axios.post(`http://127.0.0.1:8000/stop_scan/${req.body.scan_id}`);
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/scan_results/:scan_id', async (req, res) => {
  try {
    const response = await axios.get(`http://127.0.0.1:8000/scan_results/${req.params.scan_id}`);
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/modules', async (req, res) => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/modules');
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/active_scans', async (req, res) => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/active_scans');
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/scan_status/:scan_id', async (req, res) => {
  try {
    const response = await axios.get(`http://127.0.0.1:8000/scan_status/${req.params.scan_id}`);
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/scan_history', async (req, res) => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/scan_history');
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/export_scan_results/:scan_id', async (req, res) => {
  try {
    const response = await axios.get(`http://127.0.0.1:8000/export_scan_results/${req.params.scan_id}?format=${req.query.format}`);
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/import_api_key', async (req, res) => {
  try {
    const response = await axios.post('http://127.0.0.1:8000/import_api_key', req.body);
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/export_api_keys', async (req, res) => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/export_api_keys');
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.listen(port, () => {
  console.log(`Server is running on http://localhost:${port}`);
});
