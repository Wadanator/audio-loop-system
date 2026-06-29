import { AlertTriangle, CheckCircle2, Clock3, Music2 } from 'lucide-react';

export default function OverviewHero({ status, layers, offline }) {
  const activeLayers = layers.filter((layer) => layer.active);
  const currentSong = status?.current_song?.name || 'Žiadna skladba';
  const activeText = activeLayers.length
    ? activeLayers.map((layer) => layer.label).join(', ')
    : 'Žiadny zvuk';

  let icon = <CheckCircle2 size={56} />;
  let title = 'Systém pripravený';
  let description = 'Čaká sa na stlačenie tlačidla.';
  let stateClass = 'ready';

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