import Sidebar from './Sidebar.jsx';

export default function AppLayout({ children, activeView, onViewChange, onLogout, theme, onToggleTheme }) {
  return (
    <div className="app-layout">
      <Sidebar
        activeView={activeView}
        onViewChange={onViewChange}
        onLogout={onLogout}
        theme={theme}
        onToggleTheme={onToggleTheme}
      />
      <main className="main-content">
        <div className="content-container">
          {children}
        </div>
      </main>
    </div>
  );
}