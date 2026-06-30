import { Layers3 } from 'lucide-react';
import LayerCard from './LayerCard.jsx';
import PageHeader from '../ui/PageHeader.jsx';

export default function LayersView({ layers, pendingLayer, onPressLayer }) {
  return (
    <section className="view-container layers-view">
      <PageHeader
        title="Zvuky"
        subtitle="Spustenie vrstiev a stav tlačidiel"
        icon={Layers3}
      />
      <div className="layer-grid operator-layer-grid">
        {layers.map((layer) => (
          <LayerCard
            key={layer.instrument}
            layer={layer}
            pending={pendingLayer === layer.instrument}
            onPress={onPressLayer}
          />
        ))}
      </div>
    </section>
  );
}