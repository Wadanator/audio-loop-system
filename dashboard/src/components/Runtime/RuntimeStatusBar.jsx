import { Clock3, Radio, Server } from 'lucide-react';

function formatTime(date) {
  if (!date) return 'nikdy';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function RuntimeStatusBar({ status, offline, lastUpdated }) {
  const activeCount = status?.active_instruments?.length || 0;
  const availableCount = status?.available_instruments?.length || 0;
  const timeout = Math.round(status?.time_until_timeout || 0);
  const modbus = `${status?.modbus_connected_modules || 0}/${status?.modbus_module_count || 0}`;

  return (
    <section className={`runtime-status-bar ${status?.system_active ? 'is-running' : ''}`}>
      <div className="runtime-status-main">
        <span className={`runtime-status-dot ${status?.system_active && !offline ? 'pulse' : ''}`} />
        <span className="runtime-status-title">{offline ? 'Dashboard je offline' : status?.current_song?.name || 'Žiadna skladba'}</span>
        <span className="runtime-status-state">{status?.system_active ? 'hrá' : 'čaká'}</span>
      </div>

      <div className="runtime-status-metrics">
        <span className={`runtime-metric ${activeCount ? 'is-on' : ''}`}><Radio size={14} /> {activeCount}/{availableCount}</span>
        <span className={`runtime-metric ${timeout < 10 && status?.system_active ? 'is-warning' : ''}`}><Clock3 size={14} /> {timeout}s</span>
        <span className={`runtime-metric ${status?.modbus_connected ? 'is-on' : 'is-warning'}`}><Server size={14} /> {modbus}</span>
        <span className={`runtime-metric ${offline ? 'is-warning' : 'is-on'}`}>{formatTime(lastUpdated)}</span>
      </div>
    </section>
  );
}