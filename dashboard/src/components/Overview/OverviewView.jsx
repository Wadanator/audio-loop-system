import OverviewHero from './OverviewHero.jsx';

export default function OverviewView({ status, layers, offline }) {
  return (
    <section className="main-dashboard">
      <OverviewHero status={status} layers={layers} offline={offline} />
    </section>
  );
}