import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../services/api.js';

const LOG_POLL_MS = 2000;
const DEFAULT_LIMIT = 250;

export function useLogs() {
  const mountedRef = useRef(false);
  const [logs, setLogs] = useState([]);
  const [isConnected, setIsConnected] = useState(true);
  const [error, setError] = useState(null);

  const refreshLogs = useCallback(async () => {
    try {
      const payload = await api.getLogs({ limit: DEFAULT_LIMIT });
      if (!mountedRef.current) return;
      const history = Array.isArray(payload.logs) ? payload.logs : [];
      setLogs([...history].reverse());
      setIsConnected(true);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setIsConnected(false);
      setError(err?.message || 'Logy nie sú dostupné');
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    refreshLogs();
    const interval = window.setInterval(refreshLogs, LOG_POLL_MS);
    return () => {
      mountedRef.current = false;
      window.clearInterval(interval);
    };
  }, [refreshLogs]);

  const clearLogs = useCallback(async () => {
    setLogs([]);
    try {
      await api.clearLogs();
      await refreshLogs();
    } catch (err) {
      if (mountedRef.current) {
        setError(err?.message || 'Nepodarilo sa vyčistiť logy');
      }
    }
  }, [refreshLogs]);

  return { logs, isConnected, error, clearLogs, refreshLogs };
}