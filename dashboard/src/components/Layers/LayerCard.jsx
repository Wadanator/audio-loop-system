import { Lightbulb, MousePointerClick, Music2, Power } from 'lucide-react';
import Button from '../ui/Button.jsx';
import StatusBadge from '../ui/StatusBadge.jsx';

function Indicator({ icon: Icon, label, active, mapped }) {
  const className = [
    'layer-indicator',
    mapped ? 'is-mapped' : 'is-unmapped',
    active ? 'is-on' : '',
  ].filter(Boolean).join(' ');
  const title = mapped
    ? `${label}: ${active ? 'aktívne' : 'neaktívne'}`
    : `${label}: nie je namapované`;

  return (
    <span className={className} title={title}>
      <Icon size={15} />
      <span>{label}</span>
    </span>
  );
}

export default function LayerCard({ layer, pending, onPress }) {
  const defaultLabel = `Zvuk ${layer.instrument}`;
  const label = layer.label || defaultLabel;
  const hasCustomLabel = label !== defaultLabel;
  const disabled = pending || !layer.available;
  const inputMapped = Boolean(layer.physical_input);
  const ledMapped = Boolean(layer.led_output);
  const inputPressed = Boolean(layer.input_state);
  const ledOn = Boolean(layer.led_state);
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

      <div className="layer-indicators" aria-label="Stav vstupu a LED">
        <Indicator icon={MousePointerClick} label="INPUT" active={inputPressed} mapped={inputMapped} />
        <Indicator icon={Lightbulb} label="LED" active={ledOn} mapped={ledMapped} />
      </div>

      <Button icon={Power} disabled={disabled} onClick={() => onPress(layer.instrument)}>
        {buttonText}
      </Button>
    </article>
  );
}