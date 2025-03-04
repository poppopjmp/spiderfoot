import 'bootstrap/dist/css/bootstrap.min.css';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { BrowserRouter as Router, Route } from 'react-router-dom';
import Settings from './components/Settings';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Router>
      <div>
        <Route path="/" component={App} />
        <Route path="/settings" component={Settings} />
      </div>
    </Router>
  </React.StrictMode>
);
