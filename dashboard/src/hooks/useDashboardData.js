import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../services/api.js';

const POLL_MS = 1000;

export function useDashboardData() {
  const mountedRef = useRef(false);
  const [status, setStatus] = useState(null);
  const [layers, setLayers] = useState([]);
  const [stats, setStats] = useState({});
  const [health, setHealth] = useState(null);
  const [offline, setOffline] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [pendingLayer, setPendingLayer] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [healthPayload, statusPayload, layersPayload, statsPayload] = await Promise.all([
        api.getHealth(),
        api.getStatus(),
        api.getLayers(),
        api.getStats(),
      ]);

      if (!mountedRef.current) return;
      setHealth(healthPayload);
      setStatus(statusPayload);
      setLayers(layersPayload.layers || []);
      setStats(statsPayload.stats || {});
      setOffline(false);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      if (!mountedRef.current) return;
      setOffline(true);
      setError(err.message || 'Dashboard API unavailable');
    }
  }, []);

  const pressLayer = useCallback(async (instrument) => {
    setPendingLayer(instrument);
    try {
      await api.pressLayer(instrument);
      await refresh();
    } finally {
      if (mountedRef.current) setPendingLayer(null);
    }
  }, [refresh]);

  useEffect(() => {
    mountedRef.current = true;
    refresh();
    const interval = window.setInterval(refresh, POLL_MS);
    return () => {
      mountedRef.current = false;
      window.clearInterval(interval);
    };
  }, [refresh]);

  return {
    status,
    layers,
    stats,
    health,
    offline,
    error,
    lastUpdated,
    pendingLayer,
    pressLayer,
    refresh,
  };
}