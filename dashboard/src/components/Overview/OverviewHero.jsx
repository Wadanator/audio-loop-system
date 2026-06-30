import { AlertTriangle, CheckCircle2, Clock3, Music2 } from 'lucide-react';

function moduleWarningText(status) {
  const modules = status?.modbus || {};
  const disconnected = status?.modbus_disconnected_modules?.length
    ? status.modbus_disconnected_modules
    : Object.entries(modules)
        .filter(([, module]) => !module?.connected)
        .map(([name]) => name);

  if (!disconnected.length) return '';

  const moduleText = disconnected.length === 1
    ? `Modul ${disconnected[0]} nie je pripojený.`
    : `Moduly ${disconnected.join(', ')} nie sú pripojené.`;

  if (disconnected.length === (status?.modbus_module_count || disconnected.length)) {
    return `${moduleText} Web ovládanie ostáva dostupné, fyzické tlačidlá sa obnovia po návrate Modbus spojenia.`;
  }

  return `${moduleText} Ostatné pripojené moduly a web ovládanie fungujú ďalej.`;
}

export default function OverviewHero({ status, layers, offline }) {
  const activeLayers = layers.filter((layer) => layer.active);
  const currentSong = status?.current_song?.name || 'Žiadna skladba';
  const activeText = activeLayers.length
    ? activeLayers.map((layer) => layer.label).join(', ')
    : 'Žiadny zvuk';
  const warningText = !offline ? moduleWarningText(status) : '';

  let icon = <CheckCircle2 size={56} />;
  let title = 'Systém pripravený';
  let description = 'Čaká sa na stlačenie tlačidla.';
  let stateClass = warningText ? 'ready warning' : 'ready';

  if (offline) {
    icon = <AlertTriangle size={56} />;
    title = 'Dashboard bez spojenia';
    description = 'Fyzické tlačidlá môžu fungovať ďalej, web len nevidí stav.';
    stateClass = 'error';
  } else if (status?.system_active) {
    icon = <Music2 size={56} />;
    title = 'Hudba hrá';
    description = activeLayers.length
      ? `Beží: ${activeText}`
      : 'Systém je aktívny, ale zatiaľ nehrá žiadna vrstva.';
    stateClass = 'running pulse';
  }

  return (
    <section className="hero-card compact-hero-card">
      <div className={`main-status ${stateClass}`}>
        <div className="status-icon">{icon}</div>
        <div className="status-text">{title}</div>
        <div className="status-description">{description}</div>
        {warningText && (
          <div className="status-module-warning" role="status" aria-live="polite">
            <AlertTriangle size={18} />
            <span>{warningText}</span>
          </div>
        )}
      </div>

      <div className="now-playing-panel compact-now-playing-panel">
        <div>
          <span className="panel-label">Aktuálna skladba</span>
          <strong>{currentSong}</strong>
        </div>
        <div>
          <span className="panel-label">Beží</span>
          <strong>{activeText}</strong>
        </div>
        <div>
          <span className="panel-label">Čas do ukončenia</span>
          <strong><Clock3 size={18} /> {Math.round(status?.time_until_timeout || 0)}s</strong>
        </div>
      </div>
    </section>
  );
}