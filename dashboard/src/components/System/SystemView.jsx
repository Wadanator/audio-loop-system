import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, HardDrive, Power, RefreshCw, Server, Settings, XCircle } from 'lucide-react';
import { useSystemActions } from '../../hooks/useSystemActions.js';
import Button from '../ui/Button.jsx';
import ButtonGroup from '../ui/ButtonGroup.jsx';
import Card from '../ui/Card.jsx';
import PageHeader from '../ui/PageHeader.jsx';

export default function SystemView({ status, offline = false }) {
  const [message, setMessage] = useState(null);

  useEffect(() => {
    if (!message) return undefined;
    const timeout = window.setTimeout(() => setMessage(null), 4200);
    return () => window.clearTimeout(timeout);
  }, [message]);

  const handleResult = useCallback((result) => {
    setMessage(result);
  }, []);

  const {
    pendingAction,
    restartService,
    rebootSystem,
    shutdownSystem,
  } = useSystemActions({ onResult: handleResult });

  const actionsAvailable = !offline && Boolean(status?.system_actions_enabled);
  const actionsDisabled = !actionsAvailable || Boolean(pendingAction);
  const ToastIcon = message?.type === 'success' ? CheckCircle2 : XCircle;

  return (
    <section className="view-container system-view">
      <PageHeader
        title="Systémové nastavenia"
        subtitle="Správa servera a hardvéru"
        icon={Settings}
      />

      {message && (
        <div className={`system-toast system-toast-${message.type}`} role="status" aria-live="polite">
          <ToastIcon size={20} />
          <span>{message.message}</span>
        </div>
      )}

      <div className="system-grid">
        <Card title="Aplikácia Múzeum" icon={Server} className="system-card">
          <p className="system-card-description">
            Ovládanie hlavnej služby Python backendu. Použite túto možnosť, ak aplikácia nereaguje, ale systém beží.
          </p>

          <div className="system-card-actions">
            <Button
              onClick={restartService}
              variant="secondary"
              icon={RefreshCw}
              className="btn-full-width"
              disabled={actionsDisabled}
              isLoading={pendingAction === 'restart_service'}
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
                onClick={rebootSystem}
                variant="secondary"
                icon={RefreshCw}
                className="btn-full-width"
                disabled={actionsDisabled}
                isLoading={pendingAction === 'reboot'}
              >
                Reštartovať RPi
              </Button>
              <Button
                onClick={shutdownSystem}
                variant="danger"
                icon={Power}
                className="btn-full-width"
                disabled={actionsDisabled}
                isLoading={pendingAction === 'shutdown'}
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
