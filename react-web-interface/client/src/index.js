import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';
import logo from './logo.png';

ReactDOM.render(
  <React.StrictMode>
    <div>
      <img src={logo} alt="Spiderfoot Logo" />
      <App />
    </div>
  </React.StrictMode>,
  document.getElementById('root')
);
