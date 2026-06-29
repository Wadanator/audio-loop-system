import Sidebar from './Sidebar.jsx';

export default function AppLayout({ children, activeView, onViewChange, offline, onLogout }) {
  return (
    <div className="app-layout">
      <Sidebar activeView={activeView} onViewChange={onViewChange} offline={offline} onLogout={onLogout} />
      <main className="main-content">
        <div className="content-container">
          {children}
        </div>
      </main>
    </div>
  );
}