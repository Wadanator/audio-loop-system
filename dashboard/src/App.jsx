import { useState } from 'react';
import AppLayout from './components/Layout/AppLayout.jsx';
import RuntimeStatusBar from './components/Runtime/RuntimeStatusBar.jsx';
import OverviewView from './components/Overview/OverviewView.jsx';
import LayersView from './components/Layers/LayersView.jsx';
import { useDashboardData } from './hooks/useDashboardData.js';

export default function App() {
  const [activeView, setActiveView] = useState('overview');
  const dashboard = useDashboardData();

  return (
    <AppLayout activeView={activeView} onViewChange={setActiveView} offline={dashboard.offline}>
      <RuntimeStatusBar status={dashboard.status} offline={dashboard.offline} lastUpdated={dashboard.lastUpdated} />
      {activeView === 'overview' && (
        <OverviewView
          status={dashboard.status}
          layers={dashboard.layers}
          offline={dashboard.offline}
        />
      )}
      {activeView === 'layers' && (
        <LayersView
          layers={dashboard.layers}
          pendingLayer={dashboard.pendingLayer}
          onPressLayer={dashboard.pressLayer}
        />
      )}
    </AppLayout>
  );
}