import React, { useState, useEffect } from 'react';

const Settings = () => {
  const [settings, setSettings] = useState({});
  const [formValues, setFormValues] = useState({});

  useEffect(() => {
    fetch('/api/settings')
      .then(response => response.json())
      .then(data => {
        setSettings(data);
        setFormValues(data);
      })
      .catch(error => console.error('Error fetching settings:', error));
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormValues({
      ...formValues,
      [name]: value,
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    fetch('/api/settings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(formValues),
    })
      .then(response => response.json())
      .then(data => {
        setSettings(data);
        alert('Settings updated successfully');
      })
      .catch(error => console.error('Error updating settings:', error));
  };

  return (
    <div>
      <h2>Settings</h2>
      <form onSubmit={handleSubmit}>
        {Object.keys(settings).map((key) => (
          <div key={key}>
            <label htmlFor={key}>{key}</label>
            <input
              type="text"
              id={key}
              name={key}
              value={formValues[key] || ''}
              onChange={handleInputChange}
            />
          </div>
        ))}
        <button type="submit">Save Settings</button>
      </form>
    </div>
  );
};

export default Settings;
