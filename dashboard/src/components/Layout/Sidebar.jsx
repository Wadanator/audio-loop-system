import { Home, Landmark, Layers3, LogOut, Moon, Settings, Sun } from 'lucide-react';
import Button from '../ui/Button.jsx';

const NAV_ITEMS = [
  { id: 'overview', label: 'Prehľad', icon: Home },
  { id: 'layers', label: 'Zvuky', icon: Layers3 },
  { id: 'system', label: 'Systém', icon: Settings },
];

export default function Sidebar({ activeView, onViewChange, onLogout, theme, onToggleTheme }) {
  const ThemeIcon = theme === 'dark' ? Sun : Moon;
  const themeLabel = theme === 'dark' ? 'Prepnúť na svetlý režim' : 'Prepnúť na tmavý režim';

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-icon">
          <Landmark size={24} />
        </div>
        <div className="brand-text">
          <h1>MUSEUM</h1>
          <span>Control System</span>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Navigácia dashboardu">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onViewChange(item.id)}
            >
              <Icon size={20} className="nav-icon" />
              <span className="nav-label">{item.label}</span>
              <div className="active-indicator" />
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="user-info">
          <div className="user-avatar">A</div>
          <div className="user-details">
            <span className="name">Admin</span>
            <span className="role">Správca</span>
          </div>
        </div>
        <div className="sidebar-actions">
          <Button
            onClick={onToggleTheme}
            variant="unstyled"
            size="small"
            icon={ThemeIcon}
            className="theme-toggle-btn"
            title={themeLabel}
            aria-label={themeLabel}
            cooldown={0}
          />
          <Button
            onClick={onLogout}
            variant="unstyled"
            size="small"
            icon={LogOut}
            className="logout-btn"
            title="Odhlásiť"
            aria-label="Odhlásiť"
            cooldown={0}
          />
        </div>
      </div>
    </aside>
  );
}