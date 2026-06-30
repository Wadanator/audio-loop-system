import { useEffect, useState } from 'react';
import { HardDrive, Power, RefreshCw, Server, Settings, XCircle } from 'lucide-react';
import Button from '../ui/Button.jsx';
import ButtonGroup from '../ui/ButtonGroup.jsx';
import Card from '../ui/Card.jsx';
import PageHeader from '../ui/PageHeader.jsx';

export default function SystemView() {
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!message) return undefined;
    const timeout = window.setTimeout(() => setMessage(''), 3200);
    return () => window.clearTimeout(timeout);
  }, [message]);

  const handlePreparedAction = (label) => {
    setMessage(`${label}: backend endpoint ešte nie je napojený`);
  };

  return (
    <section className="view-container system-view">
      <PageHeader
        title="Systémové nastavenia"
        subtitle="Správa servera a hardvéru"
        icon={Settings}
      />

      {message && (
        <div className="system-toast" role="status" aria-live="polite">
          <XCircle size={20} />
          <span>{message}</span>
        </div>
      )}

      <div className="system-grid">
        <Card title="Aplikácia Múzeum" icon={Server} className="system-card">
          <p className="system-card-description">
            Ovládanie hlavnej služby Python backendu. Použite túto možnosť, ak aplikácia nereaguje, ale systém beží.
          </p>

          <div className="system-card-actions">
            <Button
              onClick={() => handlePreparedAction('Reštartovať Backend službu')}
              variant="secondary"
              icon={RefreshCw}
              className="btn-full-width"
            >
              Reštartovať Backend službu
            </Button>
          </div>
        </Card>

        <Card title="Napájanie Zariadenia" icon={HardDrive} className="system-card">
          <p className="system-card-description">
            Fyzické ovládanie počítača (Raspberry Pi). Reštart trvá cca 2 minúty.
          </p>

          <div className="system-card-actions">
            <ButtonGroup>
              <Button
                onClick={() => handlePreparedAction('Reštartovať RPi')}
                variant="secondary"
                icon={RefreshCw}
                className="btn-full-width"
              >
                Reštartovať RPi
              </Button>
              <Button
                onClick={() => handlePreparedAction('Vypnúť')}
                variant="danger"
                icon={Power}
                className="btn-full-width"
              >
                Vypnúť
              </Button>
            </ButtonGroup>
          </div>
        </Card>
      </div>
    </section>
  );
}
