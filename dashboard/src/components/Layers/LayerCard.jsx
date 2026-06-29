import { Music2, Power } from 'lucide-react';
import Button from '../ui/Button.jsx';
import StatusBadge from '../ui/StatusBadge.jsx';

export default function LayerCard({ layer, pending, onPress }) {
  const defaultLabel = `Zvuk ${layer.instrument}`;
  const label = layer.label || defaultLabel;
  const hasCustomLabel = label !== defaultLabel;
  const disabled = pending || !layer.available;
  const buttonText = pending
    ? 'Pracujem'
    : layer.active
      ? 'Vypnúť zvuk'
      : 'Spustiť zvuk';

  return (
    <article className={`layer-card operator-layer-card ${layer.active ? 'is-active' : ''} ${layer.available ? '' : 'is-missing'}`}>
      <div className="layer-card-header">
        <div>
          {hasCustomLabel && <span className="layer-number">{defaultLabel}</span>}
          <h3>{label}</h3>
        </div>
        <StatusBadge tone={layer.active ? 'success' : layer.available ? 'neutral' : 'warning'}>
          {layer.active ? 'Hrá' : layer.available ? 'Čaká' : 'Chýba'}
        </StatusBadge>
      </div>

      <div className="layer-count">
        <Music2 size={18} />
        <span>{layer.stats_count} spustení</span>
      </div>

      <Button icon={Power} disabled={disabled} onClick={() => onPress(layer.instrument)}>
        {buttonText}
      </Button>
    </article>
  );
}