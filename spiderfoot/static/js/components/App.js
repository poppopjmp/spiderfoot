import React from 'react';
import { BrowserRouter as Router, Route, Switch } from 'react-router-dom';
import NewScan from './NewScan';
import ScanList from './ScanList';
import ScanInfo from './ScanInfo';
import Settings from './Settings';

const App = () => {
  return (
    <Router>
      <Switch>
        <Route path="/newscan" component={NewScan} />
        <Route path="/scanlist" component={ScanList} />
        <Route path="/scaninfo/:id" component={ScanInfo} />
        <Route path="/settings" component={Settings} />
      </Switch>
    </Router>
  );
};

export default App;
