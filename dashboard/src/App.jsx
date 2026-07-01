import { useState } from 'react';
import AppLayout from './components/Layout/AppLayout.jsx';
import RuntimeStatusBar from './components/Runtime/RuntimeStatusBar.jsx';
import OverviewView from './components/Overview/OverviewView.jsx';
import LayersView from './components/Layers/LayersView.jsx';
import SystemView from './components/System/SystemView.jsx';
import LoginView from './components/Auth/LoginView.jsx';
import { AuthProvider, useAuth } from './context/AuthContext.jsx';
import { ConfirmProvider } from './context/ConfirmContext.jsx';
import { useDashboardData } from './hooks/useDashboardData.js';
import useTheme from './hooks/useTheme.js';

function DashboardShell() {
  const [activeView, setActiveView] = useState('overview');
  const dashboard = useDashboardData();
  const { logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <AppLayout
      activeView={activeView}
      onViewChange={setActiveView}
      onLogout={logout}
      theme={theme}
      onToggleTheme={toggleTheme}
    >
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
      {activeView === 'system' && <SystemView status={dashboard.status} offline={dashboard.offline} />}
    </AppLayout>
  );
}

function AuthenticatedApp() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <DashboardShell /> : <LoginView />;
}

export default function App() {
  return (
    <AuthProvider>
      <ConfirmProvider>
        <AuthenticatedApp />
      </ConfirmProvider>
    </AuthProvider>
  );
}
