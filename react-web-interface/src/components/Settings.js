import React, { useState, useEffect } from 'react';
import { fetchModules, importApiKey, fetchSettings, saveSettings } from '../api';

const Settings = () => {
  const [modules, setModules] = useState([]);
  const [apiKey, setApiKey] = useState('');
  const [settings, setSettings] = useState({});

  useEffect(() => {
    fetchModules().then(setModules);
    fetchSettings().then(setSettings);
  }, []);

  const handleImportApiKey = async () => {
    try {
      await importApiKey('module_name', apiKey);
      alert('API key imported successfully');
    } catch (error) {
      console.error('Error importing API key:', error);
      alert('Error importing API key');
    }
  };

  const handleSaveSettings = async () => {
    try {
      await saveSettings(settings);
      alert('Settings saved successfully');
    } catch (error) {
      console.error('Error saving settings:', error);
      alert('Error saving settings');
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setSettings((prevSettings) => ({
      ...prevSettings,
      [name]: value,
    }));
  };

  return (
    <div>
      <h2>Settings</h2>
      <div>
        <h3>Configure Modules</h3>
        <ul>
          {modules.map((module) => (
            <li key={module}>{module}</li>
          ))}
        </ul>
      </div>
      <div>
        <h3>Import API Key</h3>
        <input
          type="text"
          placeholder="API Key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
        <button onClick={handleImportApiKey}>Import API Key</button>
      </div>
      <div>
        <h3>Module Settings</h3>
        <form>
          {Object.keys(settings).map((key) => (
            <div key={key}>
              <label>{key}</label>
              <input
                type="text"
                name={key}
                value={settings[key]}
                onChange={handleChange}
              />
            </div>
          ))}
          <button type="button" onClick={handleSaveSettings}>Save Settings</button>
        </form>
      </div>
    </div>
  );
};

export default Settings;
