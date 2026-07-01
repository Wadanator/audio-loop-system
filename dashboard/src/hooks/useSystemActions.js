import { useCallback, useState } from 'react';
import { useConfirm } from '../context/ConfirmContext.jsx';
import { api } from '../services/api.js';

export function useSystemActions({ onResult } = {}) {
  const { confirm } = useConfirm();
  const [pendingAction, setPendingAction] = useState(null);

  const performAction = useCallback(async ({ key, actionFn, title, message, successText }) => {
    const accepted = await confirm({
      title,
      message,
      confirmText: 'Vykonať',
      type: 'danger',
    });

    if (!accepted) return;

    setPendingAction(key);
    try {
      await actionFn();
      onResult?.({ type: 'success', message: successText });
    } catch (error) {
      onResult?.({ type: 'error', message: `Chyba: ${error?.message || 'akcia zlyhala'}` });
    } finally {
      setPendingAction(null);
    }
  }, [confirm, onResult]);

  return {
    pendingAction,
    restartService: () => performAction({
      key: 'restart_service',
      actionFn: api.restartService,
      title: 'Reštartovať službu?',
      message: 'Audio Loop backend sa reštartuje. Výpadok potrvá pár sekúnd.',
      successText: 'Služba sa reštartuje...',
    }),
    rebootSystem: () => performAction({
      key: 'reboot',
      actionFn: api.rebootSystem,
      title: 'Reštartovať Raspberry Pi?',
      message: 'Celý systém sa reštartuje. Toto potrvá cca 1-2 minúty.',
      successText: 'Raspberry Pi sa reštartuje...',
    }),
    shutdownSystem: () => performAction({
      key: 'shutdown',
      actionFn: api.shutdownSystem,
      title: 'Vypnúť Raspberry Pi?',
      message: 'Systém sa úplne vypne. Na zapnutie bude potrebné odpojiť a pripojiť napájanie.',
      successText: 'Raspberry Pi sa vypína...',
    }),
  };
}
