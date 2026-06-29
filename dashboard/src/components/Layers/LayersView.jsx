import LayerCard from './LayerCard.jsx';

export default function LayersView({ layers, pendingLayer, onPressLayer }) {
  return (
    <section className="view-container">
      <div className="view-heading compact-view-heading">
        <div>
          <h2>Zvuky</h2>
        </div>
      </div>
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