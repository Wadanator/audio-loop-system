import { AudioLines, Gauge, Layers3 } from 'lucide-react';

const NAV_ITEMS = [
  { id: 'overview', label: 'Prehľad', icon: Gauge },
  { id: 'layers', label: 'Zvuky', icon: Layers3 },
];

export default function Sidebar({ activeView, onViewChange, offline }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-icon"><AudioLines size={22} /></div>
        <div className="brand-text">
          <h1>Audio miestnosť</h1>
          <span>Ovládanie vrstiev</span>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Navigácia dashboardu">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${activeView === item.id ? 'active' : ''}`}
              onClick={() => onViewChange(item.id)}
            >
              <Icon className="nav-icon" size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <span className={`sidebar-state-dot ${offline ? 'is-offline' : 'is-online'}`} />
        <span>{offline ? 'Backend nedostupný' : 'Backend pripojený'}</span>
      </div>
    </aside>
  );
}