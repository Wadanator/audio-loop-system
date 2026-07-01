import { useMemo, useState } from 'react';
import { AlertCircle, Bug, ClipboardList, Download, Info, Terminal, Trash2 } from 'lucide-react';
import { api } from '../../services/api.js';
import { useLogs } from '../../hooks/useLogs.js';
import Button from '../ui/Button.jsx';
import Card from '../ui/Card.jsx';
import PageHeader from '../ui/PageHeader.jsx';
import StateNotice from '../ui/StateNotice.jsx';

const FILTERS = [
  { id: 'ALL', label: 'Všetky', className: '' },
  { id: 'INFO', label: 'Info', className: 'info' },
  { id: 'WARNING', label: 'Warning', className: 'warning' },
  { id: 'ERROR', label: 'Error', className: 'error' },
  { id: 'CRITICAL', label: 'Critical', className: 'error' },
];

function getLevelIcon(level) {
  switch (level) {
    case 'ERROR':
    case 'CRITICAL':
      return <AlertCircle size={12} />;
    case 'WARNING':
      return <AlertCircle size={12} />;
    case 'DEBUG':
      return <Bug size={12} />;
    default:
      return <Info size={12} />;
  }
}

function formatTime(timestamp) {
  return timestamp?.split(' ')[1] || '--:--:--';
}

export default function LogsView() {
  const { logs, isConnected, error, clearLogs } = useLogs();
  const [filter, setFilter] = useState('ALL');

  const filteredLogs = useMemo(() => (
    filter === 'ALL' ? logs : logs.filter((log) => log.level === filter)
  ), [filter, logs]);

  return (
    <section className="view-container logs-view">
      <PageHeader
        title="Logy systému"
        subtitle="Varovania, chyby a ručné zásahy z dashboardu"
        icon={ClipboardList}
      >
        <div className="filters" aria-label="Filtrovanie logov">
          {FILTERS.map((item) => (
            <Button
              key={item.id}
              variant="unstyled"
              className={`filter-btn ${item.className} ${filter === item.id ? 'active' : ''}`}
              onClick={() => setFilter(item.id)}
              cooldown={0}
            >
              {item.label}
            </Button>
          ))}
        </div>

        <Button
          onClick={() => { window.location.href = api.exportLogsUrl(); }}
          variant="toolbar"
          size="small"
          icon={Download}
          disabled={!logs.length}
          cooldown={0}
        >
          Export
        </Button>
        <Button onClick={clearLogs} variant="toolbar-danger" size="small" icon={Trash2} cooldown={0}>
          Vyčistiť
        </Button>
      </PageHeader>

      {!isConnected && (
        <div className="logs-connection-warning" role="status">
          <AlertCircle size={18} />
          <span>{error || 'Logy sa teraz nedajú načítať.'}</span>
        </div>
      )}

      <Card className="logs-console-card">
        <div className="logs-console">
          {filteredLogs.length === 0 ? (
            <StateNotice
              icon={Terminal}
              title="Žiadne záznamy"
              message={filter === 'ALL'
                ? 'Log konzola zatiaľ neobsahuje žiadne warningy, errory ani ručné zásahy.'
                : 'Pre zvolený filter nie sú dostupné žiadne záznamy.'}
              compact
              className="logs-empty-notice"
            />
          ) : (
            filteredLogs.map((log, index) => (
              <div key={`${log.timestamp}-${index}`} className={`log-row ${(log.level || 'info').toLowerCase()}`}>
                <span className="log-time">{formatTime(log.timestamp)}</span>
                <span className={`log-level ${(log.level || 'info').toLowerCase()}`}>
                  {getLevelIcon(log.level)} {log.level || 'INFO'}
                </span>
                <span className="log-module">{log.module || 'system'}</span>
                <span className="log-message">{log.message}</span>
              </div>
            ))
          )}
        </div>
      </Card>
    </section>
  );
}