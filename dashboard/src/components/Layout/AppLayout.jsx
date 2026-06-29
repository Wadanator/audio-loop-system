import Sidebar from './Sidebar.jsx';

export default function AppLayout({ children, activeView, onViewChange, offline }) {
  return (
    <div className="app-layout">
      <Sidebar activeView={activeView} onViewChange={onViewChange} offline={offline} />
      <main className="main-content">
        <div className="content-container">{children}</div>
      </main>
    </div>
  );
}