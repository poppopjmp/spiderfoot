import 'bootstrap/dist/css/bootstrap.min.css';
import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';
import { BrowserRouter as Router, Route } from 'react-router-dom';
import StartScan from './components/StartScan';
import StopScan from './components/StopScan';
import ScanResults from './components/ScanResults';
import ScanStatus from './components/ScanStatus';
import ExportScanResults from './components/ExportScanResults';
import ApiKeys from './components/ApiKeys';
import ActiveScans from './components/ActiveScans';
import ScanHistory from './components/ScanHistory';

ReactDOM.render(
  <React.StrictMode>
    <Router>
      <div>
        <Route path="/" component={App} />
        <Route path="/start-scan" component={StartScan} />
        <Route path="/stop-scan" component={StopScan} />
        <Route path="/scan-results" component={ScanResults} />
        <Route path="/scan-status" component={ScanStatus} />
        <Route path="/export-scan-results" component={ExportScanResults} />
        <Route path="/api-keys" component={ApiKeys} />
        <Route path="/active-scans" component={ActiveScans} />
        <Route path="/scan-history" component={ScanHistory} />
      </div>
    </Router>
  </React.StrictMode>,
  document.getElementById('root')
);
